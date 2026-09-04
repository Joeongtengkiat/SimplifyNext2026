import json
from pathlib import Path

from backend.schema import WorldState

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SEED_PATH = DATA_DIR / "world_state.seed.json"
STATE_PATH = DATA_DIR / "world_state.json"  # working copy the demo mutates; gitignored


def reset() -> WorldState:
    """Restores the working state from the seed -- lets the demo be re-run from scratch."""
    state = WorldState.model_validate_json(SEED_PATH.read_text())
    STATE_PATH.write_text(state.model_dump_json(indent=2))
    return state


def load() -> WorldState:
    if not STATE_PATH.exists():
        return reset()
    return WorldState.model_validate_json(STATE_PATH.read_text())


def save(state: WorldState) -> None:
    STATE_PATH.write_text(state.model_dump_json(indent=2))
