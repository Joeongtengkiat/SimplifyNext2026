import re

from backend.schema import EvidenceItem, Verdict

_VERDICT_RE = re.compile(r"VERDICT:\s*(\S+)", re.IGNORECASE)
_CONFIDENCE_RE = re.compile(r"CONFIDENCE:\s*(\S+)", re.IGNORECASE)
_EVIDENCE_LINE_RE = re.compile(r"^-\s*([^:]+):\s*(.+)$")
_EXPLANATION_RE = re.compile(r"EXPLANATION:\s*(.+)", re.IGNORECASE | re.DOTALL)


def parse_verdict(final_text: str, investigation_steps: int) -> Verdict:
    """Parses the agent's structured plain-text answer (see agent.SYSTEM_PROMPT) into a Verdict."""
    verdict_match = _VERDICT_RE.search(final_text)
    confidence_match = _CONFIDENCE_RE.search(final_text)
    explanation_match = _EXPLANATION_RE.search(final_text)

    evidence = [
        EvidenceItem(signal=m.group(1).strip(), detail=m.group(2).strip())
        for line in final_text.splitlines()
        if (m := _EVIDENCE_LINE_RE.match(line.strip()))
    ]

    return Verdict(
        verdict=verdict_match.group(1).lower() if verdict_match else "suspicious",
        confidence=confidence_match.group(1).lower() if confidence_match else "low",
        evidence=evidence,
        explanation=explanation_match.group(1).strip() if explanation_match else final_text.strip(),
        investigation_steps=investigation_steps,
    )
