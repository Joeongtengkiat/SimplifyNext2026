import json
from pathlib import Path

from backend.categorize import categorize
from backend.schema import WorldState

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SEED_PATH = DATA_DIR / "world_state.seed.json"
STATE_PATH = DATA_DIR / "world_state.json"  # working copy the demo mutates; gitignored


def _apply_categories(state: WorldState) -> WorldState:
    """Recomputes every item's category on every load -- covers seed items, adaptation-created
    study blocks, and user-added events from the slot picker alike, without needing to remember
    to categorize at every construction site."""
    for item in state.schedule:
        item.category = categorize(item.title, item.type)
    return state


def reset() -> WorldState:
    """Restores the working state from the seed -- lets the demo be re-run from scratch."""
    state = _apply_categories(WorldState.model_validate_json(SEED_PATH.read_text()))
    STATE_PATH.write_text(state.model_dump_json(indent=2))
    return state


def load() -> WorldState:
    if not STATE_PATH.exists():
        return reset()
    return _apply_categories(WorldState.model_validate_json(STATE_PATH.read_text()))


def save(state: WorldState) -> None:
    """Categorizes before writing, not just on load -- otherwise a freshly appended item (from
    /schedule-event, or apply_adaptation's block_study_time) keeps its default empty category
    until the next full reload, including in the very response that just created it."""
    state = _apply_categories(state)
    STATE_PATH.write_text(state.model_dump_json(indent=2))
