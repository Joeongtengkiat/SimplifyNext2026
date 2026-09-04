from backend.schema import AdaptationAction, WorldState

NUDGE = 0.05


def log_feedback(state: WorldState, actions: list[AdaptationAction], approved: bool) -> WorldState:
    """The Learn step. No real ML here -- a small, explainable nudge to the same preference
    weights score_option already reads: approving a plan that moved a protected item means the
    user was fine with it this time (nudge the weight down a little); rejecting one nudges it
    up, making that item harder to move next time."""
    moved_ids = {a.item_id for a in actions if a.type == "move_event" and a.item_id}

    for item in state.schedule:
        if item.id not in moved_ids or not item.protected:
            continue
        key = f"protect_{item.title.lower().replace(' ', '_')}"
        current = state.preferences.get(key, 0.3)
        delta = -NUDGE if approved else NUDGE
        state.preferences[key] = round(max(0.0, min(1.0, current + delta)), 3)

    return state
