from datetime import date
import holidays


def is_weekend_or_holiday() -> bool:
    """Returns True if today is Saturday, Sunday or a German public holiday."""
    today = date.today()
    if today.weekday() >= 5:  # 5=Saturday, 6=Sunday
        return True
    return today in holidays.Germany()


def active_time_window(
    allowed_from: str,
    allowed_until: str,
    weekend_from: str,
    weekend_until: str,
) -> tuple[str, str]:
    """Returns the (from, until) time window that applies today."""
    if is_weekend_or_holiday():
        return weekend_from, weekend_until
    return allowed_from, allowed_until
