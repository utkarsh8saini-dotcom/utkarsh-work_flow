import os
import time
from datetime import datetime

import httpx

from agent.models import FlightOffer
from agent.providers.base import FlightProvider

_SANDBOX_BASE = "https://test.api.amadeus.com"
_PROD_BASE = "https://api.amadeus.com"

_AIRLINE_NAMES: dict[str, str] = {
    "AA": "American Airlines", "DL": "Delta", "UA": "United",
    "BA": "British Airways", "LH": "Lufthansa", "AF": "Air France",
    "EK": "Emirates", "QR": "Qatar Airways", "SQ": "Singapore Airlines",
    "AI": "Air India", "6E": "IndiGo", "IX": "Air India Express",
}


def _resolve_airline(code: str) -> str:
    return _AIRLINE_NAMES.get(code, code)


def _parse_duration(iso: str) -> str:
    """Convert PT2H30M → 2h 30m"""
    iso = iso.replace("PT", "")
    result = iso.replace("H", "h ").replace("M", "m").strip()
    return result


class AmadeusProvider(FlightProvider):
    def __init__(self):
        self._client_id = os.environ["AMADEUS_CLIENT_ID"]
        self._client_secret = os.environ["AMADEUS_CLIENT_SECRET"]
        env = os.getenv("AMADEUS_ENV", "test").lower()
        self._base = _SANDBOX_BASE if env == "test" else _PROD_BASE
        self._token: str | None = None
        self._token_expiry: float = 0.0

    @property
    def name(self) -> str:
        return "Amadeus"

    def _get_token(self) -> str:
        if self._token and time.time() < self._token_expiry - 60:
            return self._token
        resp = httpx.post(
            f"{self._base}/v1/security/oauth2/token",
            data={
                "grant_type": "client_credentials",
                "client_id": self._client_id,
                "client_secret": self._client_secret,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        self._token = data["access_token"]
        self._token_expiry = time.time() + data["expires_in"]
        return self._token

    def search(
        self,
        origin: str,
        destination: str,
        date: str,
        adults: int = 1,
        currency: str = "USD",
    ) -> list[FlightOffer]:
        token = self._get_token()
        resp = httpx.get(
            f"{self._base}/v2/shopping/flight-offers",
            params={
                "originLocationCode": origin.upper(),
                "destinationLocationCode": destination.upper(),
                "departureDate": date,
                "adults": adults,
                "currencyCode": currency,
                "max": 20,
            },
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()

        offers: list[FlightOffer] = []
        now = datetime.now()
        for item in data.get("data", []):
            price = float(item["price"]["grandTotal"])
            itinerary = item["itineraries"][0]
            segments = itinerary["segments"]
            first_seg = segments[0]
            last_seg = segments[-1]
            airline_code = first_seg["carrierCode"]

            dep = datetime.fromisoformat(first_seg["departure"]["at"])
            arr = datetime.fromisoformat(last_seg["arrival"]["at"])

            offers.append(FlightOffer(
                airline=_resolve_airline(airline_code),
                price=price,
                currency=currency,
                departure_time=dep,
                arrival_time=arr,
                duration=_parse_duration(itinerary["duration"]),
                stops=len(segments) - 1,
                origin=origin.upper(),
                destination=destination.upper(),
                recorded_at=now,
            ))

        return sorted(offers, key=lambda o: o.price)
