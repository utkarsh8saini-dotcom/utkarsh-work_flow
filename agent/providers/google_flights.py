import os
import re
from datetime import datetime

from fast_flights import FlightQuery, Passengers, create_query, get_flights

from agent.models import FlightOffer
from agent.providers.base import FlightProvider

_PRICE_RE = re.compile(r"[\d,]+(?:\.\d+)?")


def _parse_price(text: str) -> float | None:
    """'$1,234' / '₹45,230' / 'INR 45,230' → 1234.0 / 45230.0"""
    match = _PRICE_RE.search(str(text))
    if not match:
        return None
    return float(match.group().replace(",", ""))


def _parse_stops(value) -> int:
    if isinstance(value, int):
        return value
    text = str(value).lower()
    if "nonstop" in text or "direct" in text:
        return 0
    match = re.search(r"\d+", text)
    return int(match.group()) if match else 0


def _parse_time(text: str, fallback: datetime) -> datetime:
    """Parse times like '2:30 PM on Sat, Aug 15' — best effort, fallback if unknown."""
    for fmt in ("%Y-%m-%d %H:%M", "%I:%M %p on %a, %b %d"):
        try:
            parsed = datetime.strptime(str(text).strip(), fmt)
            if parsed.year == 1900:
                parsed = parsed.replace(year=fallback.year)
            return parsed
        except (ValueError, TypeError):
            continue
    return fallback


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
        results = get_flights(query, proxy=os.environ.get("HTTPS_PROXY") or None)

        now = datetime.now()
        offers: list[FlightOffer] = []
        for flight in results:
            price = _parse_price(getattr(flight, "price", ""))
            if price is None or price <= 0:
                continue
            offers.append(FlightOffer(
                airline=getattr(flight, "name", "Unknown"),
                price=price,
                currency=currency,
                departure_time=_parse_time(getattr(flight, "departure", ""), now),
                arrival_time=_parse_time(getattr(flight, "arrival", ""), now),
                duration=str(getattr(flight, "duration", "")),
                stops=_parse_stops(getattr(flight, "stops", 0)),
                origin=origin.upper(),
                destination=destination.upper(),
                recorded_at=now,
            ))

        return sorted(offers, key=lambda o: o.price)
