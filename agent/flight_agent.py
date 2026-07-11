import os

from dotenv import load_dotenv
from rich.console import Console

from agent.providers.base import FlightProvider
from agent.storage import PriceStorage
from agent.analyzer import PriceAnalyzer
from agent.tracker import PriceTracker
from agent.display import print_offers_table, print_analysis

load_dotenv()
console = Console()


def _select_provider() -> FlightProvider:
    if os.getenv("AMADEUS_CLIENT_ID") and os.getenv("AMADEUS_CLIENT_SECRET"):
        from agent.providers.amadeus import AmadeusProvider
        provider = AmadeusProvider()
        console.print(f"[dim]Provider: {provider.name}[/dim]")
        return provider
    if os.getenv("SERPAPI_KEY"):
        from agent.providers.serpapi import SerpApiProvider
        provider = SerpApiProvider()
        console.print(f"[dim]Provider: {provider.name}[/dim]")
        return provider
    raise RuntimeError(
        "No API credentials found.\n"
        "Set AMADEUS_CLIENT_ID + AMADEUS_CLIENT_SECRET  (free at developers.amadeus.com)\n"
        "or SERPAPI_KEY  (free trial at serpapi.com)\n"
        "in a .env file."
    )


class FlightAgent:
    def __init__(self):
        self._provider: FlightProvider = _select_provider()
        data_dir = os.getenv("DATA_DIR", "data")
        self._storage = PriceStorage(data_dir)
        self._analyzer = PriceAnalyzer(self._storage)

    def search_cheapest(
        self,
        origin: str,
        destination: str,
        date: str,
        adults: int = 1,
        currency: str = "USD",
    ) -> None:
        console.print(f"\n[bold]Searching flights:[/bold] {origin} → {destination}  ({date})\n")
        offers = self._provider.search(origin, destination, date, adults, currency)
        if offers:
            self._storage.append_offers(offers)
            print_offers_table(offers, title=f"Flights: {origin} → {destination} on {date}")
            console.print(f"[dim]Results saved to {self._storage.path}[/dim]")
        else:
            console.print("[yellow]No flights found.[/yellow]")

    def monitor(
        self,
        origin: str,
        destination: str,
        date: str,
        threshold: float | None = None,
        interval_minutes: int = 30,
        adults: int = 1,
        currency: str = "USD",
    ) -> None:
        tracker = PriceTracker(self._provider, self._storage)
        tracker.track(origin, destination, date, threshold, interval_minutes, adults, currency)

    def analyze(self, origin: str, destination: str) -> None:
        summary = self._analyzer.summary(origin, destination)
        print_analysis(summary, origin, destination)
