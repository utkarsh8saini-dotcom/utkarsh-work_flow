import time
from datetime import datetime

from rich.console import Console

from agent.models import FlightOffer
from agent.providers.base import FlightProvider
from agent.storage import PriceStorage
from agent.display import print_offers_table, print_alert, print_poll_status

console = Console()


class PriceTracker:
    def __init__(self, provider: FlightProvider, storage: PriceStorage):
        self._provider = provider
        self._storage = storage

    def track(
        self,
        origin: str,
        destination: str,
        date: str,
        threshold: float | None = None,
        interval_minutes: int = 30,
        adults: int = 1,
        currency: str = "USD",
    ) -> None:
        console.print(
            f"\n[bold blue]Starting price monitor[/bold blue]: "
            f"[cyan]{origin}[/cyan] → [cyan]{destination}[/cyan]  |  "
            f"Date: [yellow]{date}[/yellow]  |  "
            f"Interval: [yellow]{interval_minutes}m[/yellow]"
            + (f"  |  Alert threshold: [green]{currency} {threshold:,.2f}[/green]" if threshold else "")
        )
        console.print("[dim]Press Ctrl+C to stop.[/dim]\n")

        cycle = 0
        session_cheapest: FlightOffer | None = None
        alerted_prices: set[float] = set()

        try:
            while True:
                cycle += 1
                try:
                    offers = self._provider.search(origin, destination, date, adults, currency)
                except Exception as exc:
                    console.print(f"[red]Poll #{cycle} failed: {exc}[/red]")
                    time.sleep(interval_minutes * 60)
                    continue

                if offers:
                    self._storage.append_offers(offers)
                    cheapest = offers[0]

                    if session_cheapest is None or cheapest.price < session_cheapest.price:
                        session_cheapest = cheapest

                    if threshold and cheapest.price <= threshold and cheapest.price not in alerted_prices:
                        print_alert(cheapest, threshold)
                        alerted_prices.add(cheapest.price)

                print_poll_status(cycle, origin, destination, session_cheapest)

                if cycle == 1 or cycle % 5 == 0:
                    print_offers_table(offers[:5], title=f"Top 5 Flights — Poll #{cycle}")

                console.print(
                    f"[dim]Data saved to {self._storage.path}  |  "
                    f"Next poll in {interval_minutes}m at "
                    f"{datetime.now().strftime('%H:%M')} + {interval_minutes}m[/dim]\n"
                )
                time.sleep(interval_minutes * 60)

        except KeyboardInterrupt:
            console.print("\n[yellow]Monitoring stopped by user.[/yellow]")
            if session_cheapest:
                console.print(
                    f"[bold]Session cheapest:[/bold] {session_cheapest.display_price()} "
                    f"on {session_cheapest.airline}"
                )
