import json
import os
from typing import Callable

from pydantic import ValidationError

from backend.bedrock import converse, get_client
from backend.domain_utils import registrable_domain
from backend.schema import EvidenceItem, Verdict
from backend.tools.check_domain import check_domain
from backend.tools.fetch_url import fetch_url
from backend.tools.web_search import web_search
from backend.trust_list import check_allowlist, is_trusted

MAX_TURNS = 8
ESCALATION_MODEL_ID = os.environ.get("BEDROCK_ESCALATION_MODEL_ID", "us.anthropic.claude-sonnet-4-5-v1:0")

SYSTEM_PROMPT = """You are PhishTrace, an assistant that investigates whether an email, message, \
or link is a phishing/scam attempt.

You are given either raw message text or a URL. Investigate like a security analyst would:
decide what to check, use the tools available, and read each result before deciding what to \
check next. Do not call every tool by default -- call what the evidence so far actually calls \
for, and call independent tools in parallel in the same turn when that's faster.

Ground truth: only claim something a tool result actually supports. Never assert a domain or \
sender is definitively malicious -- use probabilistic language ("signals suggest").

Typical investigation shape:
1. If given a URL (or a message containing one), fetch it to see the final destination and \
   redirect chain, then check the registered domain's age.
2. Check the domain against the trusted-domains allowlist -- a match is strong evidence of
   legitimacy, but a non-match just means "unknown, investigate further", not "bad".
3. If the domain is unfamiliar, young, or the page content looks like a login/payment form for \
   a brand it doesn't seem to be, search the web for the domain or the sender/claim to see if \
   others have reported it as a scam, or to find the real official site to compare against.
4. Stop once you have enough evidence for a confident verdict, or once further checks clearly \
   wouldn't change the answer -- don't burn turns checking things that won't matter.

You MUST finish by calling the submit_verdict tool -- never answer in plain text. For each \
evidence item, set source_tool to whichever tool call it actually came from, or "reasoning" if \
it's inference rather than a direct tool result. Only use "high" confidence when multiple \
independent tool-sourced signals agree.
"""

TOOL_CONFIG = {
    "tools": [
        {
            "toolSpec": {
                "name": "check_domain",
                "description": (
                    "Look up a domain's registration age and registrar via RDAP. "
                    "A very recently registered domain is a strong phishing signal."
                ),
                "inputSchema": {
                    "json": {
                        "type": "object",
                        "properties": {"domain": {"type": "string", "description": "bare domain, e.g. example.com"}},
                        "required": ["domain"],
                    }
                },
            }
        },
        {
            "toolSpec": {
                "name": "fetch_url",
                "description": (
                    "Fetch a URL, following redirects. Returns the final destination URL, the "
                    "full redirect chain, the page title, and a text excerpt of the page content."
                ),
                "inputSchema": {
                    "json": {
                        "type": "object",
                        "properties": {"url": {"type": "string"}},
                        "required": ["url"],
                    }
                },
            }
        },
        {
            "toolSpec": {
                "name": "web_search",
                "description": (
                    "Search the web. Use this to check whether a domain/sender has been reported "
                    "as a scam, or to find a brand's real official site to compare against."
                ),
                "inputSchema": {
                    "json": {
                        "type": "object",
                        "properties": {"query": {"type": "string"}},
                        "required": ["query"],
                    }
                },
            }
        },
        {
            "toolSpec": {
                "name": "check_allowlist",
                "description": (
                    "Check a domain against the team's curated trusted-domains list (well-known "
                    "legitimate brands/institutions). A match is strong evidence of legitimacy; "
                    "a non-match just means 'unknown', not 'bad' -- most real sites aren't on it."
                ),
                "inputSchema": {
                    "json": {
                        "type": "object",
                        "properties": {"domain": {"type": "string"}},
                        "required": ["domain"],
                    }
                },
            }
        },
        {
            "toolSpec": {
                "name": "submit_verdict",
                "description": (
                    "Submit your final investigation verdict. Call this once you have enough "
                    "evidence to conclude. This is the only way to finish the investigation -- "
                    "do not answer in plain text."
                ),
                "inputSchema": {
                    "json": {
                        "type": "object",
                        "properties": {
                            "verdict": {
                                "type": "string",
                                "enum": ["likely_legitimate", "suspicious", "likely_phishing"],
                            },
                            "confidence": {"type": "string", "enum": ["low", "medium", "high"]},
                            "evidence": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "signal": {"type": "string", "description": "short label, e.g. domain_age"},
                                        "detail": {
                                            "type": "string",
                                            "description": "one-line detail, grounded in a tool result",
                                        },
                                        "source_tool": {
                                            "type": "string",
                                            "enum": [
                                                "check_domain",
                                                "fetch_url",
                                                "web_search",
                                                "check_allowlist",
                                                "reasoning",
                                            ],
                                        },
                                    },
                                    "required": ["signal", "detail", "source_tool"],
                                },
                            },
                            "explanation": {
                                "type": "string",
                                "description": "one paragraph, plain language, for a non-technical reader",
                            },
                        },
                        "required": ["verdict", "confidence", "evidence", "explanation"],
                    }
                },
            }
        },
    ]
}

TOOL_FUNCS: dict[str, Callable] = {
    "check_domain": check_domain,
    "fetch_url": fetch_url,
    "web_search": web_search,
    "check_allowlist": check_allowlist,
}


def _call_tool(tool_use: dict, on_step: Callable[[dict], None] | None) -> dict:
    name, tool_input = tool_use["name"], tool_use["input"]
    func = TOOL_FUNCS.get(name)
    try:
        result = func(**tool_input).model_dump() if func else {"error": f"unknown tool '{name}'"}
    except Exception as e:  # a bad tool input or a network blip shouldn't kill the investigation
        result = {"error": f"{type(e).__name__}: {e}"}

    step = {"tool": name, "input": tool_input, "result": result}
    if on_step:
        on_step(step)
    return step


def _ground_evidence(raw_evidence: list[dict], steps: list[dict]) -> tuple[list[EvidenceItem], list[str]]:
    called_tools = {s["tool"] for s in steps}
    items, warnings = [], []
    for raw in raw_evidence:
        item = EvidenceItem(**raw)
        if item.source_tool != "reasoning" and item.source_tool not in called_tools:
            warnings.append(f"Evidence '{item.signal}' cites {item.source_tool}, which was never called this run")
        items.append(item)
    return items, warnings


def _finalize(raw_input: dict, steps: list[dict]) -> dict:
    warnings: list[str] = []
    try:
        evidence, ground_warnings = _ground_evidence(raw_input.get("evidence", []), steps)
        warnings.extend(ground_warnings)

        confidence = raw_input.get("confidence", "low")
        if ground_warnings and confidence == "high":
            confidence = "medium"
            warnings.append("Confidence downgraded from high because some cited evidence was ungrounded")

        verdict = Verdict(
            verdict=raw_input["verdict"],
            confidence=confidence,
            evidence=evidence,
            explanation=raw_input.get("explanation", ""),
            investigation_steps=len(steps),
        )
    except (ValidationError, KeyError) as e:
        warnings.append(f"submit_verdict output failed schema validation: {e}")
        verdict = Verdict(
            verdict="suspicious",
            confidence="low",
            evidence=[],
            explanation="The agent's verdict could not be validated; treat with caution and review manually.",
            investigation_steps=len(steps),
        )

    return {"steps": steps, "verdict": verdict.model_dump(), "warnings": warnings}


def _escalate(client, steps: list[dict]) -> dict | None:
    """Re-runs just the final judgment on Sonnet when Haiku's own verdict came back low-confidence,
    reusing the evidence already gathered rather than re-investigating from scratch."""
    evidence_summary = json.dumps(steps, indent=2)[:8000]
    messages = [
        {
            "role": "user",
            "content": [
                {
                    "text": "A prior investigation gathered this evidence but was only low-confidence:\n\n"
                    f"{evidence_summary}\n\nReview it and submit your own independent verdict."
                }
            ],
        }
    ]
    try:
        response = converse(
            client,
            messages,
            SYSTEM_PROMPT,
            TOOL_CONFIG,
            tool_choice={"tool": {"name": "submit_verdict"}},
            model_id=ESCALATION_MODEL_ID,
        )
    except Exception:
        return None

    for block in response["output"]["message"]["content"]:
        if block.get("toolUse", {}).get("name") == "submit_verdict":
            return block["toolUse"]["input"]
    return None


def _finalize_with_escalation(client, raw_input: dict, steps: list[dict]) -> dict:
    outcome = _finalize(raw_input, steps)
    if outcome["verdict"]["confidence"] != "low":
        return outcome

    escalated_input = _escalate(client, steps)
    if not escalated_input:
        return outcome

    escalated_outcome = _finalize(escalated_input, steps)
    escalated_outcome["warnings"].append("Escalated to Sonnet for a second opinion due to low confidence")
    return escalated_outcome


def _force_conclusion(client, messages: list[dict], steps: list[dict]) -> dict:
    messages.append(
        {
            "role": "user",
            "content": [
                {
                    "text": "You must conclude now. Call submit_verdict with your best assessment "
                    "based on the evidence gathered so far."
                }
            ],
        }
    )
    try:
        response = converse(
            client, messages, SYSTEM_PROMPT, TOOL_CONFIG, tool_choice={"tool": {"name": "submit_verdict"}}
        )
        for block in response["output"]["message"]["content"]:
            if block.get("toolUse", {}).get("name") == "submit_verdict":
                return _finalize_with_escalation(client, block["toolUse"]["input"], steps)
    except Exception:
        pass

    return {
        "steps": steps,
        "verdict": Verdict(
            verdict="suspicious",
            confidence="low",
            evidence=[],
            explanation="Investigation ended without a validated verdict; review manually.",
            investigation_steps=len(steps),
        ).model_dump(),
        "warnings": ["Forced conclusion failed; returning a default low-confidence verdict"],
    }


def _is_bare_url(text: str) -> bool:
    """True when the whole input is a single URL/domain token rather than pasted message text --
    only then is it safe to trust-list-bypass, since a longer message could still contain other
    red flags even if it happens to mention/link a trusted brand."""
    return bool(text) and " " not in text and "\n" not in text


def _primary_domain(user_input: str, steps: list[dict]) -> str | None:
    """Best-effort guess at "the domain this investigation was actually about", so the UI can
    offer a one-click Trust action. Prefers the actual landing page (fetch_url's final_url --
    what the user would actually land on, post-redirect) over a check_domain call, over the raw
    input itself."""
    for step in reversed(steps):
        if step["tool"] == "fetch_url" and step["result"].get("success") and step["result"].get("final_url"):
            return registrable_domain(step["result"]["final_url"])
    for step in reversed(steps):
        if step["tool"] == "check_domain" and step["result"].get("found"):
            return step["result"].get("domain")

    stripped = user_input.strip()
    if _is_bare_url(stripped) and "." in stripped:
        return registrable_domain(stripped)
    return None


def run_investigation(user_input: str, on_step: Callable[[dict], None] | None = None) -> dict:
    stripped = user_input.strip()
    if _is_bare_url(stripped) and is_trusted(stripped):
        domain = registrable_domain(stripped)
        return {
            "steps": [],
            "domain": domain,
            "verdict": Verdict(
                verdict="likely_legitimate",
                confidence="high",
                evidence=[
                    EvidenceItem(
                        signal="trusted_allowlist",
                        detail=f"{domain} is on the team's curated trusted-domains list",
                        source_tool="check_allowlist",
                    )
                ],
                explanation=f"{domain} is a pre-vetted, well-known domain, so no further investigation was needed.",
                investigation_steps=0,
            ).model_dump(),
            "warnings": [],
        }

    client = get_client()
    messages = [{"role": "user", "content": [{"text": user_input}]}]
    steps: list[dict] = []

    for _ in range(MAX_TURNS):
        response = converse(client, messages, SYSTEM_PROMPT, TOOL_CONFIG)
        output_message = response["output"]["message"]
        messages.append(output_message)

        submit_input = None
        tool_result_blocks = []

        for block in output_message["content"]:
            tool_use = block.get("toolUse")
            if not tool_use:
                continue
            if tool_use["name"] == "submit_verdict":
                submit_input = tool_use["input"]
                continue

            step = _call_tool(tool_use, on_step)
            steps.append(step)
            tool_result_blocks.append(
                {"toolResult": {"toolUseId": tool_use["toolUseId"], "content": [{"json": step["result"]}]}}
            )

        if submit_input is not None:
            outcome = _finalize_with_escalation(client, submit_input, steps)
            outcome["domain"] = _primary_domain(user_input, steps)
            return outcome

        if not tool_result_blocks:
            break  # model answered without calling a tool at all -- force it to conclude properly

        messages.append({"role": "user", "content": tool_result_blocks})

    outcome = _force_conclusion(client, messages, steps)
    outcome["domain"] = _primary_domain(user_input, steps)
    return outcome
