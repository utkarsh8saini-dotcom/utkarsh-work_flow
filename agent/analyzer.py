from datetime import datetime

try:
    import pandas as pd
    _PANDAS = True
except ImportError:
    _PANDAS = False

from agent.storage import PriceStorage


class PriceAnalyzer:
    def __init__(self, storage: PriceStorage):
        self._storage = storage

    def _load_df(self, origin: str, destination: str):
        if not _PANDAS:
            raise RuntimeError("pandas not installed. Run: pip install pandas")
        rows = self._storage.load_history(origin, destination)
        if not rows:
            return None
        df = pd.DataFrame(rows)
        df["price"] = pd.to_numeric(df["price"], errors="coerce")
        df["recorded_at"] = pd.to_datetime(df["recorded_at"], errors="coerce")
        df = df.dropna(subset=["price", "recorded_at"])
        df["hour"] = df["recorded_at"].dt.hour
        df["day_of_week"] = df["recorded_at"].dt.day_name()
        df["date"] = df["recorded_at"].dt.date
        return df

    def cheapest_hour_of_day(self, origin: str, destination: str) -> dict:
        """Returns avg price per hour of the day (when data was fetched)."""
        df = self._load_df(origin, destination)
        if df is None or df.empty:
            return {}
        grouped = df.groupby("hour")["price"].mean().round(2)
        return grouped.to_dict()

    def cheapest_day_of_week(self, origin: str, destination: str) -> dict:
        """Returns avg price per day of week."""
        df = self._load_df(origin, destination)
        if df is None or df.empty:
            return {}
        order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        grouped = df.groupby("day_of_week")["price"].mean().round(2)
        return {day: grouped.get(day, None) for day in order if day in grouped}

    def price_trend(self, origin: str, destination: str, days: int = 7) -> dict:
        """Daily minimum price over last N days."""
        df = self._load_df(origin, destination)
        if df is None or df.empty:
            return {}
        grouped = df.groupby("date")["price"].min().round(2)
        tail = grouped.tail(days)
        return {str(k): float(v) for k, v in tail.items()}

    def best_time_to_buy(self, origin: str, destination: str) -> str:
        hour_data = self.cheapest_hour_of_day(origin, destination)
        day_data = self.cheapest_day_of_week(origin, destination)
        trend = self.price_trend(origin, destination)

        if not hour_data and not day_data:
            return "Not enough data yet. Run monitor for a few cycles first."

        lines = []
        if hour_data:
            best_hour = min(hour_data, key=hour_data.get)
            lines.append(f"Cheapest fetch hour: {best_hour:02d}:00 (avg {hour_data[best_hour]:.2f})")

        if day_data:
            best_day = min(day_data, key=lambda d: day_data[d] or float("inf"))
            lines.append(f"Cheapest day of week: {best_day} (avg {day_data[best_day]:.2f})")

        if len(trend) >= 2:
            prices = list(trend.values())
            delta = prices[-1] - prices[0]
            direction = "rising" if delta > 0 else "falling" if delta < 0 else "stable"
            lines.append(f"Price trend ({len(trend)}d): {direction} (Δ {delta:+.2f})")

        return "\n".join(lines) if lines else "Insufficient data."

    def summary(self, origin: str, destination: str) -> dict:
        return {
            "hour_avg": self.cheapest_hour_of_day(origin, destination),
            "day_avg": self.cheapest_day_of_week(origin, destination),
            "daily_min": self.price_trend(origin, destination),
            "recommendation": self.best_time_to_buy(origin, destination),
        }
