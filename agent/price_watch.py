"""Price-over-time analytics — the "when to book" engine.

A single price check can't tell cheap from expensive. By sampling the *same* target
(route + travel date) repeatedly over time we build a trajectory, then report where the
current price sits versus everything observed and which way it's moving. This is an
evidence-based signal, not a forecast — no one can truly predict fares.
"""

from statistics import mean

_SYM = {"INR": "₹", "USD": "$", "EUR": "€", "GBP": "£", "AED": "AED "}


def _fmt(value: float, currency: str) -> str:
    return f"{_SYM.get(currency, currency + ' ')}{value:,.0f}"


def timeline(records: list[dict], travel_date: str | None = None) -> list[dict]:
    """Cheapest price per snapshot (recorded_at), oldest → newest.

    Each ``recorded_at`` is one moment we sampled the market; we keep the cheapest
    fare seen at that moment (optionally restricted to a single outbound date).
    """
    by_snapshot: dict[str, dict] = {}
    for r in records:
        if travel_date and str(r.get("departure", ""))[:10] != travel_date:
            continue
        when = str(r.get("recorded_at", ""))
        price = r.get("price")
        if not when or price is None:
            continue
        cur = by_snapshot.get(when)
        if cur is None or price < cur["price"]:
            by_snapshot[when] = {"t": when, "price": float(price),
                                 "airline": str(r.get("airline", ""))}
    return [by_snapshot[t] for t in sorted(by_snapshot)]


def change_summary(points: list[dict], currency: str = "INR") -> dict:
    """Turn a price trajectory into change stats and a buy/wait/watch signal."""
    if not points:
        return {"samples": 0, "signal": "watch", "recommendation": "No samples yet."}

    prices = [p["price"] for p in points]
    n = len(prices)
    current = points[-1]
    prev = points[-2] if n >= 2 else None
    obs_min = min(points, key=lambda p: p["price"])
    obs_max = max(points, key=lambda p: p["price"])

    delta = (current["price"] - prev["price"]) if prev else 0.0
    pct = (delta / prev["price"] * 100) if prev and prev["price"] else 0.0

    if n >= 2:
        avg_step = mean(prices[i] - prices[i - 1] for i in range(1, n))
        threshold = min(prices) * 0.01  # 1% of the lowest price
        trend = "rising" if avg_step > threshold else "falling" if avg_step < -threshold else "stable"
    else:
        trend = "unknown"

    span = obs_max["price"] - obs_min["price"]
    volatility = (span / obs_min["price"] * 100) if obs_min["price"] else 0.0
    position = (current["price"] - obs_min["price"]) / span * 100 if span else 0.0

    rec = _recommend(n, current, obs_min, obs_max, trend, delta, position, currency)
    return {
        "samples": n,
        "current": round(current["price"], 2),
        "current_airline": current["airline"],
        "current_time": current["t"],
        "previous": round(prev["price"], 2) if prev else None,
        "delta": round(delta, 2),
        "pct_change": round(pct, 2),
        "observed_min": round(obs_min["price"], 2),
        "observed_min_time": obs_min["t"],
        "observed_max": round(obs_max["price"], 2),
        "observed_max_time": obs_max["t"],
        "trend": trend,
        "volatility_pct": round(volatility, 1),
        "position_pct": round(position, 1),
        "signal": rec["signal"],
        "recommendation": rec["text"],
    }


def _recommend(n, current, obs_min, obs_max, trend, delta, position, currency) -> dict:
    def m(x):
        return _fmt(x, currency)

    if n < 3:
        return {"signal": "watch",
                "text": (f"Only {n} sample{'s' if n != 1 else ''} so far — keep the watch "
                         f"running. A trustworthy when-to-book call needs the fare sampled "
                         f"repeatedly over hours/days; one check can't tell cheap from dear.")}
    if current["price"] <= obs_min["price"] * 1.02:
        return {"signal": "buy",
                "text": (f"BOOK NOW — {m(current['price'])} is at/near the lowest observed "
                         f"({m(obs_min['price'])}). It has been as high as {m(obs_max['price'])}.")}
    if trend == "rising":
        return {"signal": "buy",
                "text": (f"Lean book — rising ({'+' if delta >= 0 else ''}{m(delta)} since last "
                         f"check), now {position:.0f}% up the observed range. Waiting risks the "
                         f"{m(obs_max['price'])} high.")}
    if trend == "falling":
        return {"signal": "wait",
                "text": (f"WAIT — falling (last move {m(delta)}). Still {position:.0f}% above the "
                         f"{m(obs_min['price'])} low seen {obs_min['t'][5:16]}; a dip is plausible.")}
    return {"signal": "neutral",
            "text": (f"Stable near {m(current['price'])}. Watch for a dip below "
                     f"{m(obs_min['price'])}; otherwise book when convenient.")}
