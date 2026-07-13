"""Local web UI for the Flight Price Tracker.

A thin Flask layer over the existing agent components (provider / storage / analyzer)
so you can browse recorded fares, trigger a live scan day-by-day, and cross-check each
price against Google Flights. Launch with:  uv run main.py serve
"""

import json
import os
import threading
import time
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_from_directory

from agent import price_watch
from agent.analyzer import PriceAnalyzer
from agent.dates import build_date_range
from agent.models import FlightOffer
from agent.storage import PriceStorage

load_dotenv()  # so a WSGI entrypoint (waitress/gunicorn) also picks up .env locally
_STATIC = Path(__file__).parent / "static"
_alert_state: dict[str, float] = {}  # last-alerted price per watch, to avoid repeat emails


def _email_configured() -> bool:
    return bool(os.getenv("SMTP_HOST") and os.getenv("ALERT_TO"))


def _send_email(subject: str, body: str) -> bool:
    if not _email_configured():
        return False
    import smtplib
    from email.message import EmailMessage

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = os.getenv("ALERT_FROM") or os.getenv("SMTP_USER") or "flight-tracker@localhost"
    msg["To"] = os.getenv("ALERT_TO")
    msg.set_content(body)
    try:
        with smtplib.SMTP(os.getenv("SMTP_HOST"), int(os.getenv("SMTP_PORT", "587")), timeout=20) as s:
            s.starttls()
            user, password = os.getenv("SMTP_USER"), os.getenv("SMTP_PASSWORD")
            if user and password:
                s.login(user, password)
            s.send_message(msg)
        return True
    except Exception as exc:
        print(f"[alert] email send failed: {exc}")
        return False


class _WatchManager:
    """Persisted list of price-watch targets (route + date + trip type)."""

    def __init__(self, path: Path):
        self._path = Path(path)
        self._lock = threading.Lock()
        self._watches: list[dict] = []
        if self._path.exists():
            try:
                self._watches = json.loads(self._path.read_text(encoding="utf-8"))
            except Exception:
                self._watches = []

    @staticmethod
    def _key(w: dict) -> str:
        return f"{w['origin']}|{w['destination']}|{w['trip']}|{w.get('date', '')}|{w.get('return_date', '')}"

    def list(self) -> list[dict]:
        with self._lock:
            return list(self._watches)

    def has(self, origin, dest, roundtrip, date, return_date) -> bool:
        key = f"{origin}|{dest}|{'roundtrip' if roundtrip else 'oneway'}|{date or ''}|{return_date or ''}"
        return any(self._key(w) == key for w in self.list())

    def add(self, w: dict) -> None:
        with self._lock:
            for i, existing in enumerate(self._watches):
                if self._key(existing) == self._key(w):
                    self._watches[i] = w  # update threshold / currency / etc.
                    self._save()
                    return
            self._watches.append(w)
            self._save()

    def remove(self, w: dict) -> None:
        with self._lock:
            self._watches = [x for x in self._watches if self._key(x) != self._key(w)]
            self._save()

    def _save(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(json.dumps(self._watches, indent=2), encoding="utf-8")
        except Exception:
            pass


def _select_provider():
    if os.getenv("SERPAPI_KEY"):
        from agent.providers.serpapi import SerpApiProvider
        return SerpApiProvider()
    from agent.providers.google_flights import GoogleFlightsProvider
    return GoogleFlightsProvider()


def _num(value, cast, default=None):
    try:
        return cast(value)
    except (TypeError, ValueError):
        return default


def _offer_to_dict(o: FlightOffer) -> dict:
    return {
        "airline": o.airline,
        "price": o.price,
        "currency": o.currency,
        "departure": o.departure_time.strftime("%Y-%m-%d %H:%M"),
        "departure_time": o.departure_time.strftime("%H:%M"),
        "arrival": o.arrival_time.strftime("%Y-%m-%d %H:%M"),
        "arrival_time": o.arrival_time.strftime("%H:%M"),
        "duration": o.duration,
        "stops": o.stops,
        "origin": o.origin,
        "destination": o.destination,
        "recorded_at": o.recorded_at.strftime("%Y-%m-%d %H:%M:%S"),
        "return_date": o.return_date,
    }


def _record_to_dict(r: dict) -> dict:
    return {
        "recorded_at": str(r.get("recorded_at", "")),
        "airline": str(r.get("airline", "")),
        "price": _num(r.get("price"), float),
        "currency": str(r.get("currency", "")),
        "departure": str(r.get("departure", "")),
        "arrival": str(r.get("arrival", "")),
        "duration": str(r.get("duration", "")),
        "stops": _num(r.get("stops"), int, 0),
        "origin": str(r.get("origin", "")),
        "destination": str(r.get("destination", "")),
        "return_date": str(r.get("return_date", "") or ""),
    }


def _daily_cheapest(records: list[dict]) -> list[dict]:
    """Collapse all records to the cheapest offer per travel (departure) date."""
    best: dict[str, dict] = {}
    for r in records:
        travel_date = r["departure"][:10]
        price = r["price"]
        if not travel_date or price is None:
            continue
        current = best.get(travel_date)
        if current is None or price < current["price"]:
            best[travel_date] = {
                "date": travel_date,
                "price": price,
                "currency": r["currency"] or "USD",
                "airline": r["airline"],
                "departure_time": r["departure"][11:16],
                "duration": r["duration"],
                "stops": r["stops"],
                "recorded_at": r["recorded_at"],
                "return_date": r.get("return_date", ""),
            }
    return [best[d] for d in sorted(best)]


def _stats(daily: list[dict]) -> dict:
    if not daily:
        return {}
    prices = sorted(d["price"] for d in daily)
    n = len(prices)
    median = prices[n // 2] if n % 2 else (prices[n // 2 - 1] + prices[n // 2]) / 2
    cheapest = min(daily, key=lambda d: d["price"])
    return {
        "min": round(prices[0], 2),
        "max": round(prices[-1], 2),
        "median": round(median, 2),
        "avg": round(sum(prices) / n, 2),
        "count": n,
        "cheapest_date": cheapest["date"],
        "cheapest_airline": cheapest["airline"],
        "currency": daily[0]["currency"],
    }


def create_app() -> Flask:
    app = Flask(__name__, static_folder=str(_STATIC), static_url_path="/static")

    @app.before_request
    def _guard():
        """Optional access lock — set APP_TOKEN to require a token (use when tunneling
        the app to the public internet). Unset = no gate (local / home-Wi-Fi use)."""
        from flask import redirect
        token = os.getenv("APP_TOKEN")
        if not token or request.path.startswith("/static") or request.path == "/healthz":
            return None
        if request.cookies.get("ft_token") == token:
            return None
        if request.args.get("token") == token:
            resp = redirect(request.path or "/")
            resp.set_cookie("ft_token", token, max_age=31_536_000, samesite="Lax")
            return resp
        if request.path.startswith("/api/"):
            return jsonify({"error": "unauthorized"}), 401
        return ("<!doctype html><meta name=viewport content='width=device-width,initial-scale=1'>"
                "<body style='font-family:monospace;background:#0b0f1a;color:#eef2fb;display:flex;"
                "min-height:100vh;align-items:center;justify-content:center'>"
                "<form method=get style='text-align:center'>"
                "<div style='color:#ffb23e;letter-spacing:.2em;margin-bottom:14px'>AEROFARE — LOCKED</div>"
                "<input name=token placeholder='access token' autofocus "
                "style='padding:10px;border-radius:8px;border:1px solid #333;background:#10162a;color:#fff'/> "
                "<button style='padding:10px 16px;border-radius:8px;border:0;background:#ffb23e'>Enter</button>"
                "</form></body>", 401)

    storage = PriceStorage(os.getenv("DATA_DIR", "data"))
    analyzer = PriceAnalyzer(storage)
    provider = _select_provider()
    lock = threading.Lock()
    watches = _WatchManager(Path(os.getenv("DATA_DIR", "data")) / "watches.json")

    def _record(offers):
        if offers:
            with lock:
                storage.append_offers(offers)

    def _load(origin, dest, roundtrip):
        with lock:
            return [_record_to_dict(r) for r in storage.load_history(origin, dest, roundtrip=roundtrip)]

    def _sample(w):
        """Sample one watch target once; persists and returns the offers."""
        if w["trip"] == "roundtrip":
            if not hasattr(provider, "search_roundtrip"):
                return []
            offers = provider.search_roundtrip(w["origin"], w["destination"], w["date"],
                                                w["return_date"], w.get("adults", 1), w.get("currency", "INR"))
        else:
            offers = provider.search(w["origin"], w["destination"], w["date"],
                                     w.get("adults", 1), w.get("currency", "INR"))
        _record(offers)
        return offers

    def _watch_from_args():
        origin = request.args.get("origin", "").upper()
        dest = request.args.get("destination", "").upper()
        date = request.args.get("date", "")
        if not (origin and dest and date):
            return None
        return {
            "origin": origin, "destination": dest, "date": date,
            "return_date": request.args.get("return_date", "") or "",
            "trip": "roundtrip" if request.args.get("trip") == "roundtrip" else "oneway",
            "currency": (request.args.get("currency") or "INR").upper(),
            "adults": _num(request.args.get("adults"), int, 1),
            "threshold": _num(request.args.get("threshold"), float),
        }

    def _maybe_alert(w, offers):
        """Email once when the cheapest fare drops to/below a watch's threshold (and again
        only if it falls further)."""
        threshold = w.get("threshold")
        if not (threshold and offers):
            return
        current = offers[0].price
        if current > threshold:
            return
        key = _WatchManager._key(w)
        last = _alert_state.get(key)
        if last is not None and current >= last:
            return
        _alert_state[key] = current
        o = offers[0]
        label = (f"{w['origin']}⇄{w['destination']} {w['date']}→{w['return_date']}"
                 if w["trip"] == "roundtrip" else f"{w['origin']}→{w['destination']} {w['date']}")
        _send_email(
            f"✈ Price drop: {label} — {o.currency} {current:,.0f}",
            f"{label}\n\nCheapest now: {o.currency} {current:,.0f} on {o.airline}\n"
            f"Below your threshold of {o.currency} {threshold:,.0f}.\n"
            f"Departs {o.departure_time.strftime('%d %b %H:%M')} · {o.duration} · {o.stops} stop(s)\n\n"
            f"— Flight Price Tracker",
        )

    def _sampler_loop():
        interval = max(60, int(os.getenv("WATCH_INTERVAL_MINUTES", "30")) * 60)
        while True:
            time.sleep(interval)
            for w in watches.list():
                try:
                    _maybe_alert(w, _sample(w))
                except Exception:
                    pass  # a single failed sample must not kill the watcher

    threading.Thread(target=_sampler_loop, daemon=True).start()

    @app.get("/")
    def index():
        return send_from_directory(_STATIC, "index.html")

    @app.get("/healthz")
    def healthz():
        return {"ok": True}

    @app.get("/api/routes")
    def routes():
        import openpyxl
        found = []
        if storage.path.exists():
            wb = openpyxl.load_workbook(storage.path, read_only=True)
            for name in wb.sheetnames:
                if "→" in name:
                    origin, dest = name.split("→", 1)
                    found.append({"origin": origin, "destination": dest})
            wb.close()
        return jsonify({"routes": found, "provider": provider.name})

    @app.get("/api/date-range")
    def date_range():
        try:
            dates = build_date_range(request.args.get("date") or None,
                                     request.args.get("end_date") or None)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        return jsonify({"dates": dates})

    @app.get("/api/history")
    def history():
        origin = request.args.get("origin", "").upper()
        dest = request.args.get("destination", "").upper()
        roundtrip = request.args.get("trip") == "roundtrip"
        records = _load(origin, dest, roundtrip)
        daily = _daily_cheapest(records)
        return jsonify({
            "origin": origin, "destination": dest, "trip": "roundtrip" if roundtrip else "oneway",
            "records": records, "daily": daily, "stats": _stats(daily),
        })

    @app.get("/api/weekend-pairs")
    def weekend_pairs_ep():
        from agent.dates import weekend_pairs
        try:
            pairs = weekend_pairs(request.args.get("date") or None, request.args.get("end_date") or None)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        return jsonify({"pairs": pairs})

    @app.get("/api/search-weekend")
    def search_weekend():
        origin = request.args.get("origin", "").upper()
        dest = request.args.get("destination", "").upper()
        out = request.args.get("out", "")
        ret = request.args.get("ret", "")
        adults = _num(request.args.get("adults"), int, 1)
        currency = request.args.get("currency", "USD")
        if not (origin and dest and out and ret):
            return jsonify({"error": "origin, destination, out and ret are required"}), 400
        if not hasattr(provider, "search_roundtrip"):
            return jsonify({"out": out, "ret": ret, "error": "round-trip not supported", "offers": []})
        try:
            offers = provider.search_roundtrip(origin, dest, out, ret, adults, currency)
        except Exception as exc:  # a bad pair shouldn't abort the whole scan
            return jsonify({"out": out, "ret": ret, "error": str(exc), "offers": []})
        _record(offers)
        return jsonify({"out": out, "ret": ret, "offers": [_offer_to_dict(o) for o in offers]})

    @app.get("/api/search-day")
    def search_day():
        origin = request.args.get("origin", "").upper()
        dest = request.args.get("destination", "").upper()
        date = request.args.get("date", "")
        adults = _num(request.args.get("adults"), int, 1)
        currency = request.args.get("currency", "USD")
        if not (origin and dest and date):
            return jsonify({"error": "origin, destination and date are required"}), 400
        try:
            offers = provider.search(origin, dest, date, adults, currency)
        except Exception as exc:  # a bad day shouldn't abort the whole scan
            return jsonify({"date": date, "error": str(exc), "offers": []})
        _record(offers)
        return jsonify({"date": date, "offers": [_offer_to_dict(o) for o in offers]})

    @app.get("/api/analysis")
    def analysis():
        origin = request.args.get("origin", "").upper()
        dest = request.args.get("destination", "").upper()
        s = analyzer.summary(origin, dest)
        return jsonify({
            "hour_avg": {int(k): round(float(v), 2) for k, v in s["hour_avg"].items()},
            "day_avg": {str(k): (round(float(v), 2) if v is not None else None)
                        for k, v in s["day_avg"].items()},
            "daily_min": {str(k): round(float(v), 2) for k, v in s["daily_min"].items()},
            "recommendation": s["recommendation"],
        })

    @app.get("/api/timeline")
    def timeline_ep():
        origin = request.args.get("origin", "").upper()
        dest = request.args.get("destination", "").upper()
        roundtrip = request.args.get("trip") == "roundtrip"
        travel_date = request.args.get("date") or None
        return_date = request.args.get("return_date", "") or ""
        records = _load(origin, dest, roundtrip)
        currency = next((r["currency"] for r in records if r["currency"]), "INR")
        points = price_watch.timeline(records, travel_date)
        return jsonify({
            "points": points,
            "summary": price_watch.change_summary(points, currency),
            "currency": currency,
            "watching": watches.has(origin, dest, roundtrip, travel_date, return_date),
        })

    @app.get("/api/watches")
    def watches_ep():
        return jsonify({"watches": watches.list(),
                        "interval_minutes": max(1, int(os.getenv("WATCH_INTERVAL_MINUTES", "30"))),
                        "email_alerts": _email_configured()})

    @app.get("/api/watch/add")
    def watch_add():
        w = _watch_from_args()
        if not w:
            return jsonify({"error": "origin, destination and date are required"}), 400
        watches.add(w)
        return jsonify({"watches": watches.list(), "added": w})

    @app.get("/api/watch/remove")
    def watch_remove():
        w = _watch_from_args()
        if not w:
            return jsonify({"error": "origin, destination and date are required"}), 400
        watches.remove(w)
        return jsonify({"watches": watches.list()})

    @app.get("/api/sample-now")
    def sample_now():
        w = _watch_from_args()
        if not w:
            return jsonify({"error": "origin, destination and date are required"}), 400
        try:
            offers = _sample(w)
            _maybe_alert(w, offers)
        except Exception as exc:
            return jsonify({"error": str(exc), "sampled": 0}), 200
        records = _load(w["origin"], w["destination"], w["trip"] == "roundtrip")
        points = price_watch.timeline(records, w["date"])
        return jsonify({
            "sampled": len(offers),
            "points": points,
            "summary": price_watch.change_summary(points, w["currency"]),
        })

    return app


def run(host: str = "127.0.0.1", port: int = 8000) -> None:
    app = create_app()
    print(f"\n  ✈  Flight Price Tracker — web UI")
    print(f"     →  http://{host}:{port}\n     (Ctrl+C to stop)\n")
    app.run(host=host, port=port, debug=False, threaded=True)
