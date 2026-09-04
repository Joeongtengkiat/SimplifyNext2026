from typing import Literal

from pydantic import BaseModel

Tier = Literal["green", "yellow", "red"]
DAY_ORDER = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


class ScheduleItem(BaseModel):
    id: str
    day: str
    start: str  # "HH:MM"
    end: str  # "HH:MM"
    title: str
    type: str  # class | meeting | personal | interview | ...
    movable: bool
    protected: bool = False  # user has historically resisted moving this


class Task(BaseModel):
    id: str
    title: str
    due_day: str
    hours_required: float
    hours_completed: float = 0.0
    priority: str = "medium"


class WorldState(BaseModel):
    today: str
    schedule: list[ScheduleItem]
    tasks: list[Task]
    daily_capacity_hours: dict[str, float]  # realistic free/flex hours per day, before movable items
    preferences: dict[str, float]  # e.g. "protect_basketball": 0.8


class ConflictReport(BaseModel):
    task_id: str
    task_title: str
    old_due_day: str
    new_due_day: str
    remaining_hours: float
    available_hours_before_new_due: float
    shortfall_hours: float
    movable_items_in_window: list[ScheduleItem]


class AdaptationAction(BaseModel):
    type: Literal["block_study_time", "move_event", "draft_message"]
    tier: Tier
    day: str | None = None
    start: str | None = None
    end: str | None = None
    item_id: str | None = None  # for move_event
    to_day: str | None = None
    to_start: str | None = None
    to_end: str | None = None
    recipient: str | None = None  # for draft_message
    message: str | None = None


class ScoredOption(BaseModel):
    completion_probability: float
    available_hours: float
    freed_hours: float
    preference_penalty: float
    breakdown: str  # short human-readable explanation of the calculation


class AdaptationOption(BaseModel):
    id: str
    summary: str
    actions: list[AdaptationAction]
    completion_probability: float
    breakdown: str


class AdaptationProposal(BaseModel):
    change_summary: str
    conflict: ConflictReport
    options: list[AdaptationOption]
    recommended_option_id: str
    reasoning: str
    investigation_steps: int


class ActionResult(BaseModel):
    action: AdaptationAction
    applied: bool
    detail: str


class ExecutionResult(BaseModel):
    results: list[ActionResult]
    state: WorldState


class InjectChangeRequest(BaseModel):
    change_text: str


class ExecuteRequest(BaseModel):
    option_id: str
    proposal: AdaptationProposal  # the frontend echoes back the proposal it's approving


class FeedbackRequest(BaseModel):
    option_id: str
    approved: bool
    proposal: AdaptationProposal
