from typing import Literal

# deterministic, zero-cost routing -- no need to spend an LLM call just to decide which of the
# two agents should handle a message. The query agent (backend/query_agent.py) actually handles
# two kinds of message despite its name: "am I free" questions, AND direct scheduling requests
# ("allocate my whole Thursday for a friend meetup") -- both need find_free_slots, neither is a
# deadline changing on an existing task, which is the only thing the adaptation agent
# understands. Routing a scheduling request to the adaptation agent produces a nonsensical
# "deadline conflict" story instead of just... scheduling the thing (found via live testing).
_QUERY_MARKERS = [
    "which day", "which days", "which period", "which periods",
    "what time", "when am i", "when should", "when can i",
    "free for", "am i free", "how much time", "how many hours", "how free",
    "allocate", "block out", "block off", "set aside", "reserve time", "book time",
]


def classify_intent(message: str) -> Literal["query", "change"]:
    lowered = message.lower()
    if "?" in message or any(marker in lowered for marker in _QUERY_MARKERS):
        return "query"
    return "change"
