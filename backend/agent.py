from typing import Callable

from backend.bedrock import converse, get_client
from backend.tools.check_domain import check_domain
from backend.tools.fetch_url import fetch_url
from backend.tools.web_search import web_search

MAX_TURNS = 8

SYSTEM_PROMPT = """You are PhishTrace, an assistant that investigates whether an email, message, \
or link is a phishing/scam attempt.

You are given either raw message text or a URL. Investigate like a security analyst would:
decide what to check, use the tools available, and read each result before deciding what to \
check next. Do not call every tool by default — call what the evidence so far actually calls for.

Ground truth: only claim something a tool result actually supports. Never assert a domain or \
sender is definitively malicious — use probabilistic language ("signals suggest").

Typical investigation shape:
1. If given a URL (or a message containing one), fetch it to see the final destination and \
   redirect chain, then check the registered domain's age.
2. If the domain is unfamiliar, young, or the page content looks like a login/payment form for \
   a brand it doesn't seem to be, search the web for the domain or the sender/claim to see if \
   others have reported it as a scam, or to find the real official site to compare against.
3. Stop once you have enough evidence to give a confident verdict, or once further checks \
   clearly wouldn't change the answer — don't burn turns checking things that won't matter.

When you are done investigating, respond with your final answer as plain text (no more tool \
calls) in this shape:

VERDICT: <likely_legitimate | suspicious | likely_phishing>
CONFIDENCE: <low | medium | high>
EVIDENCE:
- <signal>: <one-line detail, grounded in an actual tool result>
- <signal>: <one-line detail>
EXPLANATION: <one paragraph, plain language, for a non-technical reader>
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
    ]
}

TOOL_FUNCS: dict[str, Callable] = {
    "check_domain": check_domain,
    "fetch_url": fetch_url,
    "web_search": web_search,
}


def run_investigation(user_input: str, on_step: Callable[[dict], None] | None = None) -> dict:
    client = get_client()
    messages = [{"role": "user", "content": [{"text": user_input}]}]
    steps = []

    for _ in range(MAX_TURNS):
        response = converse(client, messages, SYSTEM_PROMPT, TOOL_CONFIG)
        output_message = response["output"]["message"]
        messages.append(output_message)

        if response["stopReason"] != "tool_use":
            final_text = "".join(block.get("text", "") for block in output_message["content"] if "text" in block)
            return {"steps": steps, "final_text": final_text}

        tool_result_blocks = []
        for block in output_message["content"]:
            if "toolUse" not in block:
                continue
            tool_use = block["toolUse"]
            name, tool_input = tool_use["name"], tool_use["input"]
            func = TOOL_FUNCS.get(name)

            result_dict = func(**tool_input).model_dump() if func else {"error": f"unknown tool {name}"}

            step = {"tool": name, "input": tool_input, "result": result_dict}
            steps.append(step)
            if on_step:
                on_step(step)

            tool_result_blocks.append(
                {"toolResult": {"toolUseId": tool_use["toolUseId"], "content": [{"json": result_dict}]}}
            )

        messages.append({"role": "user", "content": tool_result_blocks})

    return {
        "steps": steps,
        "final_text": "VERDICT: suspicious\nCONFIDENCE: low\nEXPLANATION: Investigation hit the step "
        "limit before reaching a confident conclusion; treat with caution and review manually.",
    }
