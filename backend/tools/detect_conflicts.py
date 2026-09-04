from backend.capacity import available_hours
from backend.schema import ConflictReport, WorldState
from backend.time_utils import window_days


def detect_conflicts(state: WorldState, task_id: str, new_due_day: str) -> ConflictReport:
    task = next((t for t in state.tasks if t.id == task_id), None)
    if task is None:
        raise ValueError(f"unknown task_id '{task_id}'")

    remaining_hours = max(0.0, task.hours_required - task.hours_completed)
    days = window_days(state.today, new_due_day)
    available = available_hours(state, days)
    shortfall = max(0.0, remaining_hours - available)

    movable_in_window = [item for item in state.schedule if item.movable and item.day in days]

    return ConflictReport(
        task_id=task.id,
        task_title=task.title,
        old_due_day=task.due_day,
        new_due_day=new_due_day,
        remaining_hours=remaining_hours,
        available_hours_before_new_due=available,
        shortfall_hours=shortfall,
        movable_items_in_window=movable_in_window,
    )
