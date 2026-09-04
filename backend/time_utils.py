from backend.schema import DAY_ORDER


def duration_hours(start: str, end: str) -> float:
    sh, sm = (int(p) for p in start.split(":"))
    eh, em = (int(p) for p in end.split(":"))
    return (eh * 60 + em - sh * 60 - sm) / 60


def window_days(today: str, due_day: str) -> list[str]:
    """Days from today (inclusive) up to but not including due_day, in week order. Assumes a
    single-week horizon -- fine for this demo's scale, would need real dates for anything
    longer."""
    start_idx = DAY_ORDER.index(today)
    end_idx = DAY_ORDER.index(due_day)
    if end_idx <= start_idx:
        return []
    return DAY_ORDER[start_idx:end_idx]


def days_in_range(start_day: str, end_day: str) -> list[str]:
    """Inclusive of both ends -- different from window_days (deadline math). Used for "am I
    free between X and Y" queries."""
    start_idx = DAY_ORDER.index(start_day)
    end_idx = DAY_ORDER.index(end_day)
    if end_idx < start_idx:
        return []
    return DAY_ORDER[start_idx : end_idx + 1]


def to_minutes(t: str) -> int:
    h, m = (int(p) for p in t.split(":"))
    return h * 60 + m


def from_minutes(m: int) -> str:
    return f"{m // 60:02d}:{m % 60:02d}"
