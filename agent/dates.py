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


def weekend_pairs(start: str | None, end: str | None) -> list[dict]:
    """Thursday/Friday departures within the range, each paired with the next Sunday.

    Returns dicts: {"out": YYYY-MM-DD, "ret": YYYY-MM-DD, "dow": "Thu"|"Fri"}.
    The return Sunday may spill into the next month (e.g. Fri Jul 31 → Sun Aug 2).
    """
    pairs: list[dict] = []
    for iso in build_date_range(start, end):
        d = datetime.strptime(iso, "%Y-%m-%d").date()
        weekday = d.weekday()  # Mon=0 … Thu=3, Fri=4, Sun=6
        if weekday == 3:
            ret = d + timedelta(days=3)
        elif weekday == 4:
            ret = d + timedelta(days=2)
        else:
            continue
        pairs.append({"out": iso, "ret": ret.isoformat(),
                      "dow": "Thu" if weekday == 3 else "Fri"})
    return pairs
