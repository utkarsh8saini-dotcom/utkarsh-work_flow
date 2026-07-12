import os

from dotenv import load_dotenv
from rich.console import Console

from agent.providers.base import FlightProvider
from agent.storage import PriceStorage
from agent.analyzer import PriceAnalyzer
from agent.tracker import PriceTracker
from agent.display import print_offers_table, print_analysis, print_daily_cheapest
from agent.models import FlightOffer

load_dotenv()
console = Console()


def _select_provider() -> FlightProvider:
    if os.getenv("SERPAPI_KEY"):
        from agent.providers.serpapi import SerpApiProvider
        provider = SerpApiProvider()
    else:
        from agent.providers.google_flights import GoogleFlightsProvider
        provider = GoogleFlightsProvider()
    console.print(f"[dim]Provider: {provider.name}[/dim]")
    return provider


class FlightAgent:
    def __init__(self):
        self._provider: FlightProvider = _select_provider()
        data_dir = os.getenv("DATA_DIR", "data")
        self._storage = PriceStorage(data_dir)
        self._analyzer = PriceAnalyzer(self._storage)

    def search_dates(
        self,
        origin: str,
        destination: str,
        dates: list[str],
        adults: int = 1,
        currency: str = "USD",
    ) -> dict[str, FlightOffer]:
        """Search each date, save all offers, return the cheapest offer per date."""
        cheapest_by_date: dict[str, FlightOffer] = {}
        for d in dates:
            try:
                offers = self._provider.search(origin, destination, d, adults, currency)
            except Exception as exc:
                console.print(f"[red]{d}: search failed ({exc})[/red]")
                continue
            if offers:
                self._storage.append_offers(offers)
                cheapest_by_date[d] = offers[0]
                console.print(
                    f"[dim]{d}: {len(offers)} flights, cheapest "
                    f"{offers[0].display_price()} ({offers[0].airline})[/dim]"
                )
            else:
                console.print(f"[dim]{d}: no flights found[/dim]")
        return cheapest_by_date

    def search_cheapest(
        self,
        origin: str,
        destination: str,
        dates: list[str],
        adults: int = 1,
        currency: str = "USD",
    ) -> None:
        span = dates[0] if len(dates) == 1 else f"{dates[0]} → {dates[-1]} ({len(dates)} days)"
        console.print(f"\n[bold]Searching flights:[/bold] {origin} → {destination}  ({span})\n")

        if len(dates) == 1:
            # Single date: show the full ranked table for that day
            offers = self._provider.search(origin, destination, dates[0], adults, currency)
            if not offers:
                console.print("[yellow]No flights found.[/yellow]")
                return
            self._storage.append_offers(offers)
            print_offers_table(offers, title=f"Flights: {origin} → {destination} on {dates[0]}")
        else:
            cheapest_by_date = self.search_dates(origin, destination, dates, adults, currency)
            if not cheapest_by_date:
                console.print("[yellow]No flights found.[/yellow]")
                return
            print_daily_cheapest(cheapest_by_date, origin, destination)
        console.print(f"[dim]Results saved to {self._storage.path}[/dim]")

    def monitor(
        self,
        origin: str,
        destination: str,
        dates: list[str],
        threshold: float | None = None,
        interval_minutes: int = 30,
        adults: int = 1,
        currency: str = "USD",
    ) -> None:
        tracker = PriceTracker(self._provider, self._storage)
        tracker.track(origin, destination, dates, threshold, interval_minutes, adults, currency)

    def analyze(self, origin: str, destination: str) -> None:
        summary = self._analyzer.summary(origin, destination)
        print_analysis(summary, origin, destination)
