import time
from datetime import date, datetime

from rich.console import Console

from agent.models import FlightOffer
from agent.providers.base import FlightProvider
from agent.storage import PriceStorage
from agent.display import print_daily_cheapest, print_alert, print_poll_status

console = Console()


class PriceTracker:
    def __init__(self, provider: FlightProvider, storage: PriceStorage):
        self._provider = provider
        self._storage = storage

    def track(
        self,
        origin: str,
        destination: str,
        dates: list[str],
        threshold: float | None = None,
        interval_minutes: int = 30,
        adults: int = 1,
        currency: str = "USD",
    ) -> None:
        span = dates[0] if len(dates) == 1 else f"{dates[0]} → {dates[-1]} ({len(dates)} days)"
        console.print(
            f"\n[bold blue]Starting price monitor[/bold blue]: "
            f"[cyan]{origin}[/cyan] → [cyan]{destination}[/cyan]  |  "
            f"Dates: [yellow]{span}[/yellow]  |  "
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
                # Drop travel dates that are now in the past
                today = date.today().isoformat()
                dates = [d for d in dates if d >= today]
                if not dates:
                    console.print("[yellow]All travel dates have passed — stopping monitor.[/yellow]")
                    break

                cheapest_by_date: dict[str, FlightOffer] = {}
                for d in dates:
                    try:
                        offers = self._provider.search(origin, destination, d, adults, currency)
                    except Exception as exc:
                        console.print(f"[red]Poll #{cycle} {d} failed: {exc}[/red]")
                        continue
                    if not offers:
                        continue
                    self._storage.append_offers(offers)
                    cheapest_by_date[d] = offers[0]

                if cheapest_by_date:
                    best = min(cheapest_by_date.values(), key=lambda o: o.price)
                    if session_cheapest is None or best.price < session_cheapest.price:
                        session_cheapest = best
                    if threshold and best.price <= threshold and best.price not in alerted_prices:
                        print_alert(best, threshold)
                        alerted_prices.add(best.price)

                print_poll_status(cycle, origin, destination, session_cheapest)

                if cheapest_by_date and (cycle == 1 or cycle % 5 == 0):
                    print_daily_cheapest(cheapest_by_date, origin, destination)

                console.print(
                    f"[dim]Data saved to {self._storage.path}  |  "
                    f"next poll ~{interval_minutes}m from {datetime.now().strftime('%H:%M')}[/dim]\n"
                )
                time.sleep(interval_minutes * 60)

        except KeyboardInterrupt:
            console.print("\n[yellow]Monitoring stopped by user.[/yellow]")
            if session_cheapest:
                console.print(
                    f"[bold]Session cheapest:[/bold] {session_cheapest.display_price()} "
                    f"on {session_cheapest.airline} "
                    f"(fly {session_cheapest.departure_time.strftime('%Y-%m-%d')})"
                )
