from backend.capacity import available_hours
from backend.schema import AdaptationAction, ScoredOption, WorldState
from backend.time_utils import duration_hours, window_days

BASE_PROBABILITY = 0.5
COVERAGE_WEIGHT = 0.45
PROTECTED_MOVE_PENALTY_SCALE = 0.08  # rescheduling a protected item is a mild hit -- it still
# happens, just on a different day; conflating that with cancelling it would wrongly let a
# naive partial-coverage plan outscore a full-coverage one that moves something protected


def score_option(state: WorldState, task_id: str, new_due_day: str, actions: list[AdaptationAction]) -> ScoredOption:
    task = next((t for t in state.tasks if t.id == task_id), None)
    if task is None:
        raise ValueError(f"unknown task_id '{task_id}'")

    days = window_days(state.today, new_due_day)
    moves = {a.item_id: a.to_day for a in actions if a.type == "move_event" and a.item_id and a.to_day}

    available = available_hours(state, days, moves=moves)
    baseline_available = available_hours(state, days)
    freed_hours = available - baseline_available

    study_hours = sum(
        duration_hours(a.start, a.end) for a in actions if a.type == "block_study_time" and a.day in days
    )
    usable = min(study_hours, available)

    remaining = max(0.0, task.hours_required - task.hours_completed)
    coverage = 1.0 if remaining <= 0 else min(1.0, usable / remaining)

    penalty = 0.0
    for item_id, new_day in moves.items():
        item = next((s for s in state.schedule if s.id == item_id), None)
        if item and item.protected and new_day != item.day:
            key = f"protect_{item.title.lower().replace(' ', '_')}"
            penalty += state.preferences.get(key, 0.3) * PROTECTED_MOVE_PENALTY_SCALE

    probability = max(0.05, min(0.95, BASE_PROBABILITY + COVERAGE_WEIGHT * coverage - penalty))

    breakdown = (
        f"{usable:.1f}h of {remaining:.1f}h needed are covered before the deadline "
        f"({available:.1f}h available after proposed moves, {freed_hours:+.1f}h freed by them)"
        + (f"; -{penalty:.2f} probability for moving a protected commitment" if penalty else "")
    )

    return ScoredOption(
        completion_probability=round(probability, 2),
        available_hours=round(available, 2),
        freed_hours=round(freed_hours, 2),
        preference_penalty=round(penalty, 2),
        breakdown=breakdown,
    )
