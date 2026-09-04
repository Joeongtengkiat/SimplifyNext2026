from backend.schema import ActionResult, AdaptationAction, ExecutionResult, ScheduleItem, WorldState

_next_id_counter = [0]


def _new_id(prefix: str) -> str:
    _next_id_counter[0] += 1
    return f"{prefix}{_next_id_counter[0]}"


def apply_adaptation(state: WorldState, actions: list[AdaptationAction]) -> ExecutionResult:
    """Commits an approved plan to world state -- but only 🟢/🟡 actions. A 🔴 action is refused
    here regardless of what the model proposed; this is the actual enforcement behind the
    "bounded autonomy" claim, not just a prompt instruction."""
    results = []

    for action in actions:
        if action.tier == "red":
            results.append(ActionResult(action=action, applied=False, detail="Refused: red-tier actions are never auto-executed. Handle this one yourself."))
            continue

        if action.type == "block_study_time":
            state.schedule.append(
                ScheduleItem(
                    id=_new_id("study"),
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
            old_day, old_start = item.day, item.start
            item.day = action.to_day or item.day
            item.start = action.to_start or item.start
            item.end = action.to_end or item.end
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
