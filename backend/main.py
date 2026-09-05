from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402

from backend import world_state  # noqa: E402
from backend.agent import run_adaptation  # noqa: E402
from backend.intent import classify_intent  # noqa: E402
from backend.query_agent import run_query  # noqa: E402
from backend.schema import (  # noqa: E402
    DAY_ORDER,
    ChatRequest,
    ExecuteRequest,
    FeedbackRequest,
    InjectChangeRequest,
    QueryRequest,
    ScheduleEventRequest,
    ScheduleItem,
)
from backend.tools.apply_adaptation import _new_id, apply_adaptation  # noqa: E402
from backend.tools.log_feedback import log_feedback  # noqa: E402

app = FastAPI(title="ADAPT")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/state")
def get_state():
    return world_state.load().model_dump()


@app.post("/reset")
def reset_state():
    return world_state.reset().model_dump()


@app.post("/inject-change")
def inject_change(req: InjectChangeRequest) -> dict:
    state = world_state.load()
    return run_adaptation(req.change_text, state)


@app.post("/execute")
def execute(req: ExecuteRequest) -> dict:
    option = next((o for o in req.proposal.options if o.id == req.option_id), None)
    if option is None:
        return {"error": f"unknown option_id '{req.option_id}'"}

    state = world_state.load()
    result = apply_adaptation(state, option.actions)
    log_feedback(result.state, option.actions, approved=True)
    world_state.save(result.state)
    return result.model_dump()


@app.post("/feedback")
def feedback(req: FeedbackRequest) -> dict:
    option = next((o for o in req.proposal.options if o.id == req.option_id), None)
    if option is None:
        return {"error": f"unknown option_id '{req.option_id}'"}

    state = world_state.load()
    log_feedback(state, option.actions, approved=req.approved)
    world_state.save(state)
    return {"acknowledged": True, "preferences": state.preferences}


@app.post("/query")
def query(req: QueryRequest) -> dict:
    state = world_state.load()
    return run_query(req.query_text, state)


@app.post("/chat")
def chat(req: ChatRequest) -> dict:
    """Single entry point for the chat UI -- routes each message to whichever agent actually
    handles it (still two separate agents under the hood, just one door in)."""
    state = world_state.load()
    kind = classify_intent(req.message)
    if kind == "query":
        return {"kind": "query", **run_query(req.message, state)}
    return {"kind": "adaptation", **run_adaptation(req.message, state)}


@app.post("/schedule-event")
def schedule_event(req: ScheduleEventRequest) -> dict:
    if req.day not in DAY_ORDER:
        return {"error": f"'{req.day}' isn't a valid day; use one of {DAY_ORDER}"}

    state = world_state.load()
    state.schedule.append(
        ScheduleItem(
            id=_new_id(state.schedule, "user"),
            day=req.day,
            start=req.start,
            end=req.end,
            title=req.title,
            type=req.type,
            movable=True,
        )
    )
    world_state.save(state)
    return state.model_dump()
