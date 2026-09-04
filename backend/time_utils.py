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
