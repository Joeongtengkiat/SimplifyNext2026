from backend.schema import WorldState
from backend.time_utils import duration_hours


def available_hours(state: WorldState, days: list[str], moves: dict[str, str] | None = None) -> float:
    """Sum of free/flex hours across `days`, after subtracting movable schedule items that
    still occupy those days. `moves` optionally relocates a movable item's day (item_id ->
    new_day) to model "what if we moved this" for a candidate option -- an item moved OUT of
    the window frees its hours there; moved INTO the window, it occupies hours there instead.
    Fixed (immovable) items are assumed already baked into daily_capacity_hours."""
    moves = moves or {}
    total = 0.0
    for day in days:
        occupied = 0.0
        for item in state.schedule:
            if not item.movable:
                continue
            effective_day = moves.get(item.id, item.day)
            if effective_day == day:
                occupied += duration_hours(item.start, item.end)
        total += max(0.0, state.daily_capacity_hours.get(day, 0.0) - occupied)
    return total
