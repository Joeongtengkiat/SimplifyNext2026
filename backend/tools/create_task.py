from backend.schema import DAY_ORDER, Task, WorldState
from backend.tools.apply_adaptation import _new_id

DEFAULT_HOURS_ESTIMATE = 3.0
_PRIORITIES = {"low", "medium", "high"}


def create_task(
    state: WorldState,
    title: str,
    due_day: str,
    hours_required: float | None = None,
    priority: str = "medium",
) -> tuple[Task, str | None]:
    """Records a new commitment the person just described. Deliberately treated as *sensing*,
    not *acting*: capturing that a task exists doesn't move anything on the calendar or send
    anything on the person's behalf, so unlike the other action types it's safe to commit
    immediately rather than waiting for an Execute click on a proposed option.

    Returns (task, note) -- note is set when a detail had to be assumed (currently only a missing
    hours_required), so the caller can surface that assumption instead of hiding it."""
    if due_day not in DAY_ORDER:
        raise ValueError(f"'{due_day}' isn't a day this app can place (must be one of {DAY_ORDER})")

    existing = next(
        (t for t in state.tasks if t.title.strip().lower() == title.strip().lower() and t.due_day == due_day),
        None,
    )
    if existing:
        return existing, None

    note = None
    if hours_required is None or hours_required <= 0:
        hours_required = DEFAULT_HOURS_ESTIMATE
        note = f"No hours estimate was given, so {DEFAULT_HOURS_ESTIMATE:.0f}h was assumed -- adjust the task if that's off."

    task = Task(
        id=_new_id(state.tasks, "task"),
        title=title,
        due_day=due_day,
        hours_required=hours_required,
        hours_completed=0.0,
        priority=priority if priority in _PRIORITIES else "medium",
    )
    state.tasks.append(task)
    return task, note
