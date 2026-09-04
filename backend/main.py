from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402

from backend import world_state  # noqa: E402
from backend.agent import run_adaptation  # noqa: E402
from backend.schema import ExecuteRequest, FeedbackRequest, InjectChangeRequest  # noqa: E402
from backend.tools.apply_adaptation import apply_adaptation  # noqa: E402
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
