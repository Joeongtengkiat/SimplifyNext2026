import json
from pathlib import Path

from backend.domain_utils import registrable_domain
from backend.schema import AllowlistCheckResult

TRUST_LIST_PATH = Path(__file__).resolve().parent.parent / "data" / "trusted_domains.json"


def _load() -> set[str]:
    if not TRUST_LIST_PATH.exists():
        return set()
    return set(json.loads(TRUST_LIST_PATH.read_text()))


def _save(domains: set[str]) -> None:
    TRUST_LIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    TRUST_LIST_PATH.write_text(json.dumps(sorted(domains), indent=2) + "\n")


def add_trusted_domain(raw: str) -> str:
    resolved = registrable_domain(raw)
    domains = _load()
    domains.add(resolved)
    _save(domains)
    return resolved


def is_trusted(raw: str) -> bool:
    return registrable_domain(raw) in _load()


def check_allowlist(domain: str) -> AllowlistCheckResult:
    """Agent tool: checks a domain against the curated trusted-domains list. A match is strong
    evidence of legitimacy; a non-match just means "unknown", not "bad" -- most legitimate sites
    aren't on any allowlist, so absence should never be treated as a negative signal."""
    resolved = registrable_domain(domain)
    return AllowlistCheckResult(domain=resolved, trusted=resolved in _load())
