from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

from agent.models import FlightOffer

console = Console()


def print_offers_table(offers: list[FlightOffer], title: str = "Flight Results") -> None:
    if not offers:
        console.print("[yellow]No flights found.[/yellow]")
        return

    table = Table(
        title=title,
        box=box.ROUNDED,
        show_header=True,
        header_style="bold white on dark_blue",
        highlight=True,
    )
    table.add_column("#", style="dim", width=3, justify="right")
    table.add_column("Airline", style="cyan", min_width=18)
    table.add_column("Price", style="bold green", justify="right", min_width=12)
    table.add_column("Departure", min_width=16)
    table.add_column("Arrival", min_width=16)
    table.add_column("Duration", justify="center", min_width=10)
    table.add_column("Stops", justify="center", min_width=6)

    for i, o in enumerate(offers, 1):
        stops_label = "Direct" if o.stops == 0 else f"{o.stops} stop{'s' if o.stops > 1 else ''}"
        stops_style = "green" if o.stops == 0 else "yellow" if o.stops == 1 else "red"
        table.add_row(
            str(i),
            o.airline,
            o.display_price(),
            o.departure_time.strftime("%d %b %H:%M"),
            o.arrival_time.strftime("%d %b %H:%M"),
            o.duration,
            f"[{stops_style}]{stops_label}[/{stops_style}]",
        )

    console.print(table)
    console.print(f"[dim]Cheapest: {offers[0].display_price()} on {offers[0].airline}[/dim]")


def print_alert(offer: FlightOffer, threshold: float) -> None:
    console.print(Panel(
        f"[bold green]PRICE DROP ALERT![/bold green]\n\n"
        f"  Airline:   [cyan]{offer.airline}[/cyan]\n"
        f"  Price:     [bold green]{offer.display_price()}[/bold green]  (threshold: {offer.currency} {threshold:,.2f})\n"
        f"  Route:     {offer.origin} → {offer.destination}\n"
        f"  Departure: {offer.departure_time.strftime('%d %b %Y %H:%M')}\n"
        f"  Arrival:   {offer.arrival_time.strftime('%d %b %Y %H:%M')}\n"
        f"  Duration:  {offer.duration}  |  Stops: {offer.stops}",
        title="[bold red]✈  Flight Alert[/bold red]",
        border_style="green",
    ))


def print_poll_status(cycle: int, origin: str, destination: str, cheapest: FlightOffer | None) -> None:
    status = f"[dim]Poll #{cycle} — {origin} → {destination}[/dim]"
    if cheapest:
        status += f"  |  Cheapest so far: [bold green]{cheapest.display_price()}[/bold green] ({cheapest.airline})"
    console.print(status)


def print_analysis(summary: dict, origin: str, destination: str) -> None:
    console.rule(f"[bold blue]Price Analysis: {origin} → {destination}[/bold blue]")

    # Day of week table
    day_avg = summary.get("day_avg", {})
    if day_avg:
        table = Table(title="Average Price by Day of Week", box=box.SIMPLE_HEAVY)
        table.add_column("Day", style="cyan")
        table.add_column("Avg Price", justify="right", style="green")
        best_day = min(day_avg, key=lambda d: day_avg[d] or float("inf"))
        for day, price in day_avg.items():
            marker = " ★" if day == best_day else ""
            table.add_row(day + marker, f"{price:.2f}" if price else "—")
        console.print(table)

    # Hour of day table
    hour_avg = summary.get("hour_avg", {})
    if hour_avg:
        table = Table(title="Average Price by Hour (when fetched)", box=box.SIMPLE_HEAVY)
        table.add_column("Hour", style="cyan")
        table.add_column("Avg Price", justify="right", style="green")
        best_hour = min(hour_avg, key=hour_avg.get)
        for hour, price in sorted(hour_avg.items()):
            marker = " ★" if hour == best_hour else ""
            table.add_row(f"{hour:02d}:00{marker}", f"{price:.2f}")
        console.print(table)

    # Daily min trend
    daily_min = summary.get("daily_min", {})
    if daily_min:
        table = Table(title="Daily Minimum Price (last 7 days)", box=box.SIMPLE_HEAVY)
        table.add_column("Date", style="cyan")
        table.add_column("Min Price", justify="right", style="green")
        for date, price in daily_min.items():
            table.add_row(str(date), f"{price:.2f}")
        console.print(table)

    # Recommendation
    rec = summary.get("recommendation", "")
    if rec:
        console.print(Panel(rec, title="[bold green]Recommendation[/bold green]", border_style="blue"))
