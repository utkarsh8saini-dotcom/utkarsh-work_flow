import os
from datetime import datetime

from agent.models import FlightOffer
from agent.providers.base import FlightProvider


class SerpApiProvider(FlightProvider):
    def __init__(self):
        self._api_key = os.environ["SERPAPI_KEY"]

    @property
    def name(self) -> str:
        return "SerpApi (Google Flights)"

    def search(
        self,
        origin: str,
        destination: str,
        date: str,
        adults: int = 1,
        currency: str = "USD",
    ) -> list[FlightOffer]:
        try:
            from serpapi import GoogleSearch
        except ImportError:
            raise RuntimeError("serpapi package not installed. Run: pip install serpapi")

        params = {
            "engine": "google_flights",
            "departure_id": origin.upper(),
            "arrival_id": destination.upper(),
            "outbound_date": date,
            "adults": adults,
            "currency": currency,
            "api_key": self._api_key,
        }
        results = GoogleSearch(params).get_dict()
        offers: list[FlightOffer] = []
        now = datetime.now()

        for flight in results.get("best_flights", []) + results.get("other_flights", []):
            legs = flight.get("flights", [])
            if not legs:
                continue
            first_leg = legs[0]
            last_leg = legs[-1]

            dep_str = first_leg.get("departure_airport", {}).get("time", "")
            arr_str = last_leg.get("arrival_airport", {}).get("time", "")

            try:
                dep = datetime.strptime(dep_str, "%Y-%m-%d %H:%M")
                arr = datetime.strptime(arr_str, "%Y-%m-%d %H:%M")
            except (ValueError, TypeError):
                dep = arr = now

            total_minutes = flight.get("total_duration", 0)
            hours, mins = divmod(total_minutes, 60)
            duration = f"{hours}h {mins}m" if mins else f"{hours}h"

            offers.append(FlightOffer(
                airline=first_leg.get("airline", "Unknown"),
                price=float(flight.get("price", 0)),
                currency=currency,
                departure_time=dep,
                arrival_time=arr,
                duration=duration,
                stops=len(legs) - 1,
                origin=origin.upper(),
                destination=destination.upper(),
                recorded_at=now,
                booking_url=None,
            ))

        return sorted(offers, key=lambda o: o.price)
