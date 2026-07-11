#!/usr/bin/env python3
"""Flight Price Tracker Agent — CLI entry point."""

import argparse
import os
import sys

from dotenv import load_dotenv

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
    s.add_argument("--date", required=True, metavar="YYYY-MM-DD",
                   help="Departure date")
    s.add_argument("--adults", type=int, default=1, metavar="N")
    s.add_argument("--currency", default=os.getenv("DEFAULT_CURRENCY", "USD"))

    # ── monitor ───────────────────────────────────────────────────────────────
    m = sub.add_parser("monitor", help="Continuously poll prices and alert on drops")
    m.add_argument("--from", dest="origin", required=True, metavar="IATA")
    m.add_argument("--to", dest="destination", required=True, metavar="IATA")
    m.add_argument("--date", required=True, metavar="YYYY-MM-DD")
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

    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    try:
        from agent.flight_agent import FlightAgent
        agent = FlightAgent()
    except RuntimeError as exc:
        print(f"\nError: {exc}\n", file=sys.stderr)
        sys.exit(1)

    if args.command == "search":
        agent.search_cheapest(
            origin=args.origin,
            destination=args.destination,
            date=args.date,
            adults=args.adults,
            currency=args.currency,
        )
    elif args.command == "monitor":
        agent.monitor(
            origin=args.origin,
            destination=args.destination,
            date=args.date,
            threshold=args.threshold,
            interval_minutes=args.interval,
            adults=args.adults,
            currency=args.currency,
        )
    elif args.command == "analyze":
        agent.analyze(origin=args.origin, destination=args.destination)


if __name__ == "__main__":
    main()
