from dotenv import load_dotenv

load_dotenv()  # must run before backend.bedrock reads AWS/model env vars

from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402

from backend.agent import run_investigation  # noqa: E402
from backend.schema import InvestigateRequest  # noqa: E402

app = FastAPI(title="PhishTrace")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/investigate")
def investigate(req: InvestigateRequest) -> dict:
    return run_investigation(req.input)
