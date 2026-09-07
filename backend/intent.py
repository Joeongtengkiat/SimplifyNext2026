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
    "free for", "am i free", "how much time", "how much free", "how many hours", "how free",
    "allocate", "block out", "block off", "set aside", "reserve time", "book time",
]

# a bare "?" alone used to be treated as "this is a query" -- but that swallowed polite,
# question-phrased change REQUESTS ("can you move my assignment to Thursday?") into the query
# agent, which has no ability to act on an existing task at all (found via testing, not reported
# live). These verbs describe modifying or removing something already on the calendar, which only
# the adaptation agent understands, so they win over a trailing "?" even though the sentence reads
# as a question.
_CHANGE_MARKERS = [
    "move my", "move the", "reschedule", "postpone", "push back", "push my", "push the",
    "delay my", "delay the", "cancel", "cancelled", "canceled", "got moved", "got pushed",
    "shift my", "shift the", "new deadline", "extend the deadline", "change the deadline",
]


def classify_intent(message: str) -> Literal["query", "change"]:
    lowered = message.lower()
    if any(marker in lowered for marker in _CHANGE_MARKERS):
        return "change"
    if "?" in message or any(marker in lowered for marker in _QUERY_MARKERS):
        return "query"
    return "change"
