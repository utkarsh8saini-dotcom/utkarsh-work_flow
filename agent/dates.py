import calendar
from datetime import date, datetime, timedelta


def month_end(day: date) -> date:
    return date(day.year, day.month, calendar.monthrange(day.year, day.month)[1])


def build_date_range(start: str | None, end: str | None) -> list[str]:
    """Expand start/end into a list of YYYY-MM-DD strings (inclusive).

    Defaults: start = today, end = last day of start's month.
    """
    start_d = datetime.strptime(start, "%Y-%m-%d").date() if start else date.today()
    end_d = datetime.strptime(end, "%Y-%m-%d").date() if end else month_end(start_d)
    if end_d < start_d:
        raise ValueError(f"--end-date {end_d} is before start date {start_d}")
    return [
        (start_d + timedelta(days=i)).isoformat()
        for i in range((end_d - start_d).days + 1)
    ]
