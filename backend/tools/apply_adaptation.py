import re

from backend.schema import ActionResult, AdaptationAction, ExecutionResult, ScheduleItem, WorldState
from backend.time_utils import to_minutes

_ID_PATTERN = re.compile(r"^([a-zA-Z]+)(\d+)$")


def _new_id(schedule: list[ScheduleItem], prefix: str) -> str:
    """Derives the next id from ids already present in the schedule, rather than an in-memory
    counter -- a counter resets to 0 on server restart and can reissue an id ("study1") that's
    already sitting in world_state.json from a prior run."""
    max_n = 0
    for item in schedule:
        match = _ID_PATTERN.match(item.id)
        if match and match.group(1) == prefix:
            max_n = max(max_n, int(match.group(2)))
    return f"{prefix}{max_n + 1}"


def _find_collision(day: str, start: str, end: str, schedule: list[ScheduleItem], exclude_id: str | None = None) -> ScheduleItem | None:
    """First existing item that overlaps [start, end) on `day`, or None. Checked against the
    schedule as it stands *at this point in the batch* -- if an earlier action in the same
    request already moved something out of the way, that's reflected here since actions mutate
    `state.schedule` in place as they're applied."""
    start_m, end_m = to_minutes(start), to_minutes(end)
    for item in schedule:
        if item.id == exclude_id or item.day != day:
            continue
        item_start, item_end = to_minutes(item.start), to_minutes(item.end)
        if start_m < item_end and item_start < end_m:
            return item
    return None


def apply_adaptation(state: WorldState, actions: list[AdaptationAction]) -> ExecutionResult:
    """Commits an approved plan to world state -- but only 🟢/🟡 actions, and only if they don't
    land on top of something already there. A 🔴 action is refused regardless of what the model
    proposed, and a colliding action is refused too, rather than silently double-booking a slot;
    this is the actual enforcement behind the "bounded autonomy" claim, not just a prompt
    instruction."""
    results = []

    for action in actions:
        if action.tier == "red":
            results.append(ActionResult(action=action, applied=False, detail="Refused: red-tier actions are never auto-executed. Handle this one yourself."))
            continue

        if action.type == "block_study_time":
            collision = _find_collision(action.day, action.start, action.end, state.schedule)
            if collision:
                results.append(
                    ActionResult(
                        action=action,
                        applied=False,
                        detail=f"Refused: {action.day} {action.start}-{action.end} overlaps with '{collision.title}'.",
                    )
                )
                continue

            state.schedule.append(
                ScheduleItem(
                    id=_new_id(state.schedule, "study"),
                    day=action.day,
                    start=action.start,
                    end=action.end,
                    title="Study block (auto-scheduled)",
                    type="study",
                    movable=False,
                )
            )
            results.append(ActionResult(action=action, applied=True, detail=f"Blocked {action.day} {action.start}-{action.end} for focused work."))

        elif action.type == "move_event":
            item = next((s for s in state.schedule if s.id == action.item_id), None)
            if item is None:
                results.append(ActionResult(action=action, applied=False, detail=f"Unknown schedule item '{action.item_id}'."))
                continue

            new_day = action.to_day or item.day
            new_start = action.to_start or item.start
            new_end = action.to_end or item.end

            if new_day == item.day and new_start == item.start and new_end == item.end:
                # re-running an already-applied move (e.g. a double-clicked Execute) is a no-op,
                # not a fresh success -- say so plainly instead of reporting a "move" to the exact
                # spot it's already at
                results.append(
                    ActionResult(
                        action=action,
                        applied=True,
                        detail=f"'{item.title}' is already at {item.day} {item.start}-{item.end}; no change needed.",
                    )
                )
                continue

            collision = _find_collision(new_day, new_start, new_end, state.schedule, exclude_id=item.id)
            if collision:
                results.append(
                    ActionResult(
                        action=action,
                        applied=False,
                        detail=f"Refused: moving '{item.title}' to {new_day} {new_start}-{new_end} overlaps with '{collision.title}'.",
                    )
                )
                continue

            old_day, old_start = item.day, item.start
            item.day, item.start, item.end = new_day, new_start, new_end
            results.append(
                ActionResult(
                    action=action,
                    applied=True,
                    detail=f"Moved '{item.title}' from {old_day} {old_start} to {item.day} {item.start}.",
                )
            )

        elif action.type == "draft_message":
            # never actually sent -- no real messaging integration exists, and shouldn't pretend to
            results.append(
                ActionResult(
                    action=action,
                    applied=True,
                    detail=f"Drafted (not sent) to {action.recipient}: “{action.message}”",
                )
            )

        else:
            results.append(ActionResult(action=action, applied=False, detail=f"Unknown action type '{action.type}'."))

    return ExecutionResult(results=results, state=state)
