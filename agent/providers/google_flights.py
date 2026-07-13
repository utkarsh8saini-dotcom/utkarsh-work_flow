import json
import os
import time
from datetime import datetime

from fast_flights import FlightQuery, Passengers, create_query, fetch_flights_html
from fast_flights.model import Airport, CarbonEmission, Flights, SimpleDatetime, SingleFlight
from selectolax.lexbor import LexborHTMLParser

from agent.models import FlightOffer
from agent.providers.base import FlightProvider

_FETCH_ATTEMPTS = 3


def _fetch_html_with_retry(query, proxy) -> str:
    """Fetch the Google Flights HTML, retrying transient network/fetch failures."""
    last_exc: Exception | None = None
    for attempt in range(_FETCH_ATTEMPTS):
        try:
            return fetch_flights_html(query, proxy=proxy)
        except Exception as exc:
            last_exc = exc
            if attempt < _FETCH_ATTEMPTS - 1:
                time.sleep(1.0)
    raise last_exc  # type: ignore[misc]


def _parse_flights(html: str) -> list[Flights]:
    """Tolerant reimplementation of fast_flights' parser.

    Google occasionally returns an entry with a missing price/field; the upstream
    parser dies on the first one (IndexError at ``price = k[1][0][1]``), which drops
    the whole day. Here each entry is guarded, so one malformed row is skipped rather
    than losing every flight for that date.
    """
    tree = LexborHTMLParser(html)
    script = tree.css_first(r"script.ds\:1")
    if script is None:
        return []
    try:
        data = script.text().split("data:", 1)[1].rsplit(",", 1)[0]
    except IndexError:
        return []
    if data.rstrip().endswith("errorHasStatus: true"):
        return []
    try:
        entries = json.loads(data)[3][0]
    except (ValueError, IndexError, KeyError, TypeError):
        return []
    if not entries:
        return []

    flights: list[Flights] = []
    for k in entries:
        try:
            flight = k[0]
            price = k[1][0][1]
            legs = [
                SingleFlight(
                    from_airport=Airport(code=sf[3], name=sf[4]),
                    to_airport=Airport(code=sf[6], name=sf[5]),
                    departure=SimpleDatetime(date=sf[20], time=sf[8]),
                    arrival=SimpleDatetime(date=sf[21], time=sf[10]),
                    duration=sf[11],
                    plane_type=sf[17],
                )
                for sf in flight[2]
            ]
            flights.append(Flights(
                type=flight[0], price=price, airlines=flight[1],
                flights=legs, carbon=CarbonEmission(typical_on_route=0, emission=0),
            ))
        except (IndexError, KeyError, TypeError):
            continue  # skip a malformed entry, keep the rest of the day
    return flights


def _to_datetime(sdt) -> datetime | None:
    """Convert a fast-flights SimpleDatetime (date=[y, m, d], time=[h, m]) to a datetime.

    Google omits trailing zeros, so a whole-hour time arrives as ``[4]`` rather than
    ``[4, 0]``; index defensively. Returns None when the date is missing so callers
    can fall back.
    """
    date_parts = list(getattr(sdt, "date", None) or [])
    time_parts = list(getattr(sdt, "time", None) or [])
    if len(date_parts) < 3 or date_parts[0] is None:
        return None

    def _at(seq: list, i: int) -> int:
        return int(seq[i]) if i < len(seq) and seq[i] is not None else 0

    try:
        return datetime(
            _at(date_parts, 0), _at(date_parts, 1), _at(date_parts, 2),
            _at(time_parts, 0), _at(time_parts, 1),
        )
    except (TypeError, ValueError):
        return None


def _format_duration(legs) -> str:
    """Total journey time: per-leg airborne minutes (TZ-correct, from Google) + layovers."""
    minutes = sum(
        int(leg.duration) for leg in legs
        if isinstance(getattr(leg, "duration", None), (int, float))
    )
    for prev, nxt in zip(legs, legs[1:]):
        arr, dep = _to_datetime(prev.arrival), _to_datetime(nxt.departure)
        if arr and dep and dep > arr:
            minutes += int((dep - arr).total_seconds() // 60)
    if minutes <= 0:
        return ""
    hours, mins = divmod(minutes, 60)
    return f"{hours}h {mins}m" if hours else f"{mins}m"


def _format_airlines(names) -> str:
    """Join airline names, de-duplicated and order-preserving (codeshares repeat)."""
    seen: list[str] = []
    for name in names or []:
        if name and name not in seen:
            seen.append(name)
    return ", ".join(seen) if seen else "Unknown"


class GoogleFlightsProvider(FlightProvider):
    """Keyless provider — scrapes Google Flights via the fast-flights library."""

    @property
    def name(self) -> str:
        return "Google Flights (fast-flights, no API key)"

    def search(
        self,
        origin: str,
        destination: str,
        date: str,
        adults: int = 1,
        currency: str = "USD",
    ) -> list[FlightOffer]:
        query = create_query(
            flights=[FlightQuery(date=date, from_airport=origin.upper(),
                                 to_airport=destination.upper())],
            trip="one-way",
            seat="economy",
            passengers=Passengers(adults=adults),
            currency=currency,
        )
        html = _fetch_html_with_retry(query, os.environ.get("HTTPS_PROXY") or None)
        return self._offers_from_html(html, origin, destination, currency)

    def search_roundtrip(
        self,
        origin: str,
        destination: str,
        out_date: str,
        return_date: str,
        adults: int = 1,
        currency: str = "USD",
    ) -> list[FlightOffer]:
        """Round-trip search. Google's first page lists outbound options priced at the
        full round-trip total, so each offer's price is the whole trip and its times are
        the outbound leg; the chosen return date is attached as ``return_date``."""
        query = create_query(
            flights=[
                FlightQuery(date=out_date, from_airport=origin.upper(), to_airport=destination.upper()),
                FlightQuery(date=return_date, from_airport=destination.upper(), to_airport=origin.upper()),
            ],
            trip="round-trip",
            seat="economy",
            passengers=Passengers(adults=adults),
            currency=currency,
        )
        html = _fetch_html_with_retry(query, os.environ.get("HTTPS_PROXY") or None)
        return self._offers_from_html(html, origin, destination, currency, return_date=return_date)

    def _offers_from_html(self, html, origin, destination, currency, return_date=None):
        now = datetime.now()
        offers: list[FlightOffer] = []
        for flight in _parse_flights(html):
            price = getattr(flight, "price", None)
            if not isinstance(price, (int, float)) or price <= 0:
                continue  # "Price unavailable" rows come through as 0

            legs = getattr(flight, "flights", None) or []
            departure = (_to_datetime(legs[0].departure) if legs else None) or now
            arrival = (_to_datetime(legs[-1].arrival) if legs else None) or now

            offers.append(FlightOffer(
                airline=_format_airlines(getattr(flight, "airlines", None)),
                price=float(price),
                currency=currency,
                departure_time=departure,
                arrival_time=arrival,
                duration=_format_duration(legs),
                stops=max(0, len(legs) - 1),
                origin=origin.upper(),
                destination=destination.upper(),
                recorded_at=now,
                return_date=return_date,
            ))

        return sorted(offers, key=lambda o: o.price)
