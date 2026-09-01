from pydantic import BaseModel


class DomainCheckResult(BaseModel):
    domain: str
    found: bool
    registration_date: str | None = None
    age_days: int | None = None
    registrar: str | None = None
    error: str | None = None


class FetchUrlResult(BaseModel):
    requested_url: str
    success: bool
    final_url: str | None = None
    redirect_chain: list[str] = []
    status_code: int | None = None
    title: str | None = None
    text_excerpt: str | None = None
    error: str | None = None


class WebSearchHit(BaseModel):
    title: str
    url: str
    snippet: str


class WebSearchResult(BaseModel):
    query: str
    success: bool
    hits: list[WebSearchHit] = []
    error: str | None = None


class EvidenceItem(BaseModel):
    signal: str
    detail: str


class InvestigationStep(BaseModel):
    tool: str
    input: dict
    result: dict


class Verdict(BaseModel):
    verdict: str  # likely_legitimate | suspicious | likely_phishing
    confidence: str  # low | medium | high
    evidence: list[EvidenceItem]
    explanation: str
    investigation_steps: int


class InvestigateRequest(BaseModel):
    input: str
