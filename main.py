#!/usr/bin/env python3
"""Flight Price Tracker Agent — CLI entry point."""

import argparse
import os
import sys

from dotenv import load_dotenv


def _force_utf8_output() -> None:
    """Ensure Unicode output works on consoles whose default encoding isn't UTF-8.

    Windows consoles default to cp1252, which can't encode characters like the
    "→" used in route labels, so Rich would raise UnicodeEncodeError. Forcing
    stdio to UTF-8 here — before any Rich Console is created — avoids that.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8")
            except (ValueError, OSError):
                pass


_force_utf8_output()
load_dotenv()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="flight-tracker",
        description="Track and analyze flight prices in near-realtime.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # ── search ────────────────────────────────────────────────────────────────
    s = sub.add_parser("search", help="One-shot search for the cheapest flights")
    s.add_argument("--from", dest="origin", required=True, metavar="IATA",
                   help="Origin airport code, e.g. DEL")
    s.add_argument("--to", dest="destination", required=True, metavar="IATA",
                   help="Destination airport code, e.g. LHR")
    s.add_argument("--date", default=None, metavar="YYYY-MM-DD",
                   help="Departure date / range start (default: today)")
    s.add_argument("--end-date", default=None, metavar="YYYY-MM-DD",
                   help="Range end, inclusive (default: last day of the start date's month; "
                        "pass the same value as --date for a single-day search)")
    s.add_argument("--adults", type=int, default=1, metavar="N")
    s.add_argument("--currency", default=os.getenv("DEFAULT_CURRENCY", "USD"))
    s.add_argument("--weekend", action="store_true",
                   help="Only Thu/Fri departures, returning the next Sunday (round-trip)")

    # ── monitor ───────────────────────────────────────────────────────────────
    m = sub.add_parser("monitor", help="Continuously poll prices and alert on drops")
    m.add_argument("--from", dest="origin", required=True, metavar="IATA")
    m.add_argument("--to", dest="destination", required=True, metavar="IATA")
    m.add_argument("--date", default=None, metavar="YYYY-MM-DD",
                   help="Departure date / range start (default: today)")
    m.add_argument("--end-date", default=None, metavar="YYYY-MM-DD",
                   help="Range end, inclusive (default: last day of the start date's month)")
    m.add_argument("--threshold", type=float, default=None, metavar="PRICE",
                   help="Alert when price falls below this value")
    m.add_argument("--interval", type=int,
                   default=int(os.getenv("POLL_INTERVAL_MINUTES", "30")),
                   metavar="MINUTES",
                   help="Poll interval in minutes (default: 30)")
    m.add_argument("--adults", type=int, default=1, metavar="N")
    m.add_argument("--currency", default=os.getenv("DEFAULT_CURRENCY", "USD"))

    # ── analyze ───────────────────────────────────────────────────────────────
    a = sub.add_parser("analyze", help="Analyze historical price data from Excel")
    a.add_argument("--from", dest="origin", required=True, metavar="IATA")
    a.add_argument("--to", dest="destination", required=True, metavar="IATA")

    # ── serve ─────────────────────────────────────────────────────────────────
    srv = sub.add_parser("serve", help="Launch the local web UI to browse and verify fares")
    srv.add_argument("--host", default="127.0.0.1", help="Bind host (default: 127.0.0.1)")
    srv.add_argument("--port", type=int, default=8000, help="Port (default: 8000)")

    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if args.command == "serve":
        from web.server import run
        run(host=args.host, port=args.port)
        return

    try:
        from agent.flight_agent import FlightAgent
        agent = FlightAgent()
    except RuntimeError as exc:
        print(f"\nError: {exc}\n", file=sys.stderr)
        sys.exit(1)

    try:
        _dispatch(agent, args)
    except KeyboardInterrupt:
        pass
    except Exception as exc:
        print(f"\nRequest failed: {exc}\n"
              "Check your internet connection and that the airport codes/date are valid.",
              file=sys.stderr)
        sys.exit(1)


def _dispatch(agent, args) -> None:
    if args.command == "search":
        from agent.dates import build_date_range
        if args.weekend:
            agent.search_weekends(
                origin=args.origin,
                destination=args.destination,
                start=args.date,
                end=args.end_date,
                adults=args.adults,
                currency=args.currency,
            )
        else:
            agent.search_cheapest(
                origin=args.origin,
                destination=args.destination,
                dates=build_date_range(args.date, args.end_date),
                adults=args.adults,
                currency=args.currency,
            )
    elif args.command == "monitor":
        from agent.dates import build_date_range
        agent.monitor(
            origin=args.origin,
            destination=args.destination,
            dates=build_date_range(args.date, args.end_date),
            threshold=args.threshold,
            interval_minutes=args.interval,
            adults=args.adults,
            currency=args.currency,
        )
    elif args.command == "analyze":
        agent.analyze(origin=args.origin, destination=args.destination)


if __name__ == "__main__":
    main()
