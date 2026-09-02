from typing import Literal

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


class AllowlistCheckResult(BaseModel):
    domain: str
    trusted: bool


class EvidenceItem(BaseModel):
    signal: str
    detail: str
    # which tool this evidence came from, or "reasoning" if it's inference rather than a
    # direct tool result -- lets us check the model isn't citing evidence nothing backs
    source_tool: Literal["check_domain", "fetch_url", "web_search", "check_allowlist", "reasoning"] = "reasoning"


class Verdict(BaseModel):
    verdict: Literal["likely_legitimate", "suspicious", "likely_phishing"]
    confidence: Literal["low", "medium", "high"]
    evidence: list[EvidenceItem]
    explanation: str
    investigation_steps: int


class InvestigateRequest(BaseModel):
    input: str
