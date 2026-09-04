from backend.schema import FreeSlot, WorldState
from backend.time_utils import days_in_range, from_minutes, to_minutes

WORK_DAY_START = "07:00"
WORK_DAY_END = "23:00"


def _merge_intervals(intervals: list[tuple[int, int]]) -> list[tuple[int, int]]:
    if not intervals:
        return []
    intervals = sorted(intervals)
    merged = [intervals[0]]
    for start, end in intervals[1:]:
        if start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def find_free_slots(state: WorldState, start_day: str, end_day: str, min_duration_hours: float = 0.0) -> list[FreeSlot]:
    """Literal gaps in the schedule within a waking-hours window (07:00-23:00), for both ends
    inclusive of start_day/end_day. This is intentionally a different, more literal measure than
    score_option's daily_capacity_hours (a conservative planning ceiling used for deadline
    pressure) -- the two can legitimately disagree, e.g. a day can have open calendar gaps while
    still being a "low realistic capacity" day for deep work. Don't expect them to match exactly."""
    day_start, day_end = to_minutes(WORK_DAY_START), to_minutes(WORK_DAY_END)
    results = []

    for day in days_in_range(start_day, end_day):
        busy = [(to_minutes(item.start), to_minutes(item.end)) for item in state.schedule if item.day == day]
        merged = _merge_intervals(busy)

        cursor = day_start
        gaps = []
        for busy_start, busy_end in merged:
            if busy_start > cursor:
                gaps.append((cursor, min(busy_start, day_end)))
            cursor = max(cursor, busy_end)
        if cursor < day_end:
            gaps.append((cursor, day_end))

        for gap_start, gap_end in gaps:
            duration = (gap_end - gap_start) / 60
            if duration >= min_duration_hours and duration > 0:
                results.append(
                    FreeSlot(day=day, start=from_minutes(gap_start), end=from_minutes(gap_end), duration_hours=round(duration, 2))
                )

    return results
