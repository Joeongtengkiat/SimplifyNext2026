from dotenv import load_dotenv

load_dotenv()  # must run before backend.bedrock reads AWS/model env vars

from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402

from backend.agent import run_investigation  # noqa: E402
from backend.schema import InvestigateRequest  # noqa: E402
from backend.trust_list import add_trusted_domain  # noqa: E402

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


TRUST_COMMAND = "-trust"


@app.post("/investigate")
def investigate(req: InvestigateRequest) -> dict:
    text = req.input.strip()

    if text.lower().startswith(TRUST_COMMAND):
        domain = text[len(TRUST_COMMAND) :].strip()
        if not domain:
            return {"command": "trust", "error": "Usage: -trust <domain>"}
        resolved = add_trusted_domain(domain)
        return {"command": "trust", "domain": resolved, "message": f"'{resolved}' added to the trusted-domains list."}

    return run_investigation(req.input)
