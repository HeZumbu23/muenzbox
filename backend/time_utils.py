from datetime import date, datetime
import holidays

_FALLBACK = [{"von": "08:00", "bis": "20:00"}]


def is_weekend_or_holiday() -> bool:
    """Returns True if today is Saturday, Sunday or a German public holiday."""
    today = date.today()
    if today.weekday() >= 5:  # 5=Saturday, 6=Sunday
        return True
    return today in holidays.Germany()


def _parse_time(t: str) -> tuple[int, int]:
    h, m = t.split(":")
    return int(h), int(m)


def is_in_periods(periods: list[dict]) -> bool:
    """Returns True if the current time falls within any of the given periods."""
    now = datetime.now()
    current_minutes = now.hour * 60 + now.minute
    for p in periods:
        fh, fm = _parse_time(p["von"])
        uh, um = _parse_time(p["bis"])
        if fh * 60 + fm <= current_minutes <= uh * 60 + um:
            return True
    return False


def get_active_periods(
    allowed_periods: list[dict],
    weekend_periods: list[dict],
) -> list[dict]:
    """Returns the periods applicable today (weekday vs weekend/holiday)."""
    if is_weekend_or_holiday():
        return weekend_periods or _FALLBACK
    return allowed_periods or _FALLBACK
