from typing import Literal

# deterministic, zero-cost routing -- no need to spend an LLM call just to decide which of the
# two agents should handle a message. A question about availability gets these markers; a
# change announcement ("X moved to Y") generally doesn't.
_QUERY_MARKERS = [
    "which day", "which days", "which period", "which periods",
    "what time", "when am i", "when should", "when can i",
    "free for", "am i free", "how much time", "how many hours", "how free",
]


def classify_intent(message: str) -> Literal["query", "change"]:
    lowered = message.lower()
    if "?" in message or any(marker in lowered for marker in _QUERY_MARKERS):
        return "query"
    return "change"
