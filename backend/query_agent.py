from typing import Callable

from backend.bedrock import converse, get_client
from backend.schema import QueryResponse, RecommendedSlot, WorldState
from backend.tools.find_free_slots import find_free_slots

MAX_TURNS = 4

SYSTEM_PROMPT = """You handle two kinds of message about a person's free time, grounded only in \
their actual schedule -- never invent availability.

Type 1, a question: "which days am I free", "which periods am I free for more than 2 hours", \
"what time should I go to the gym".

Type 2, a direct scheduling request: "allocate the whole day Thursday for a friend meetup", \
"block out 2 hours Friday for gym", "set aside Saturday morning to study". This is NOT a \
deadline changing on an existing task -- it's someone asking you to find them the time for \
something new. Treat "the whole day" as the largest free slot that day, not a single hour.

For both types:
1. Interpret the request into a day range (start_day, end_day, both from Mon/Tue/Wed/Thu/Fri/\
   Sat/Sun) and a minimum duration in hours (0 if none was implied). If no range is stated, \
   default to today through Sunday.
2. Call find_free_slots with that range -- this is the only source of truth for what's actually \
   free. Never state a free slot that tool didn't return.
3. Pick ONE of the actual returned slots as your recommendation and explain why: for a Type 1 \
   "what time should I do X" question, explain the fit; for a Type 2 scheduling request, \
   recommend the slot that best matches what was asked (the whole free window for "the whole \
   day", a slot of at least the requested duration otherwise). Only skip the recommendation for \
   a plain "which days/periods am I free" listing question with no specific thing to schedule.
4. Finish by calling answer_query with a short, plain-language message summarizing what you \
   found. Never answer in plain text outside that tool call.
"""

TOOL_CONFIG = {
    "tools": [
        {
            "toolSpec": {
                "name": "find_free_slots",
                "description": "Returns the actual free time gaps in the schedule for a day range, optionally filtered to a minimum duration.",
                "inputSchema": {
                    "json": {
                        "type": "object",
                        "properties": {
                            "start_day": {"type": "string", "enum": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]},
                            "end_day": {"type": "string", "enum": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]},
                            "min_duration_hours": {"type": "number"},
                        },
                        "required": ["start_day", "end_day"],
                    }
                },
            }
        },
        {
            "toolSpec": {
                "name": "answer_query",
                "description": "Submit your final answer. This is the only way to finish -- do not answer in plain text.",
                "inputSchema": {
                    "json": {
                        "type": "object",
                        "properties": {
                            "start_day": {"type": "string"},
                            "end_day": {"type": "string"},
                            "min_duration_hours": {"type": "number"},
                            "message": {"type": "string"},
                            "recommended_slot": {
                                "type": "object",
                                "properties": {
                                    "day": {"type": "string"},
                                    "start": {"type": "string"},
                                    "end": {"type": "string"},
                                    "reasoning": {"type": "string"},
                                },
                            },
                        },
                        "required": ["start_day", "end_day", "min_duration_hours", "message"],
                    }
                },
            }
        },
    ]
}


def _describe_state(state: WorldState) -> str:
    schedule_lines = "\n".join(f"- {s.day} {s.start}-{s.end} {s.title}" for s in state.schedule)
    return f"Today is {state.today}.\n\nSchedule:\n{schedule_lines}"


def _call_tool(tool_input: dict, state: WorldState, on_step: Callable[[dict], None] | None) -> dict:
    try:
        slots = find_free_slots(
            state, tool_input["start_day"], tool_input["end_day"], tool_input.get("min_duration_hours", 0.0)
        )
        result = {"slots": [s.model_dump() for s in slots]}
    except Exception as e:
        result = {"error": f"{type(e).__name__}: {e}"}

    step = {"tool": "find_free_slots", "input": tool_input, "result": result}
    if on_step:
        on_step(step)
    return step


def _finalize(raw_input: dict, state: WorldState, steps: list[dict]) -> dict:
    """Recomputes the free slots authoritatively from the interpreted range, and checks any
    recommended slot actually falls within one of them -- same grounding-by-construction
    pattern as the adaptation agent."""
    warnings: list[str] = []
    try:
        start_day, end_day = raw_input["start_day"], raw_input["end_day"]
        min_hours = raw_input.get("min_duration_hours", 0.0)
        slots = find_free_slots(state, start_day, end_day, min_hours)

        recommended = None
        raw_rec = raw_input.get("recommended_slot")
        if raw_rec:
            candidate = RecommendedSlot(**raw_rec)
            grounded = any(
                s.day == candidate.day and s.start <= candidate.start and s.end >= candidate.end for s in slots
            )
            if grounded:
                recommended = candidate
            else:
                warnings.append("Recommended slot didn't match any actual free slot found; dropped it.")

        response = QueryResponse(
            interpreted_start_day=start_day,
            interpreted_end_day=end_day,
            interpreted_min_duration_hours=min_hours,
            free_slots=slots,
            message=raw_input.get("message", ""),
            recommended_slot=recommended,
            investigation_steps=len(steps),
        )
    except Exception as e:
        # same lesson as agent.py's _finalize: a narrow except clause misses real failure modes
        # (e.g. ValueError from an invalid day string) -- degrade gracefully on anything, never
        # crash the request over the model's own malformed output
        warnings.append(f"answer_query output failed validation: {type(e).__name__}: {e}")
        response = QueryResponse(
            interpreted_start_day=state.today,
            interpreted_end_day="Sun",
            interpreted_min_duration_hours=0.0,
            free_slots=[],
            message="Couldn't interpret that query; try rephrasing it.",
            investigation_steps=len(steps),
        )

    return {"steps": steps, "query_response": response.model_dump(), "warnings": warnings}


def _force_conclusion(client, messages: list[dict], state: WorldState, steps: list[dict]) -> dict:
    """Mirrors agent.py's _force_conclusion -- without this, a message the model doesn't call a
    tool for at all (e.g. gibberish, or a message it can't parse as a question) fell straight
    through to a generic "didn't reach an answer" with no attempt at an honest explanation."""
    messages.append(
        {
            "role": "user",
            "content": [
                {
                    "text": "You must conclude now. Call answer_query with your best understanding, "
                    "or an honest explanation of what you couldn't interpret, based on what you've "
                    "found so far."
                }
            ],
        }
    )
    try:
        response = converse(
            client, messages, SYSTEM_PROMPT, TOOL_CONFIG, tool_choice={"tool": {"name": "answer_query"}}
        )
        for block in response["output"]["message"]["content"]:
            if block.get("toolUse", {}).get("name") == "answer_query":
                return _finalize(block["toolUse"]["input"], state, steps)
    except Exception:
        pass

    return {
        "steps": steps,
        "query_response": None,
        "warnings": ["Forced conclusion failed; no answer could be generated."],
    }


def run_query(query_text: str, state: WorldState, on_step: Callable[[dict], None] | None = None) -> dict:
    client = get_client()
    messages = [{"role": "user", "content": [{"text": f"{_describe_state(state)}\n\nQuestion: {query_text}"}]}]
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
            if tool_use["name"] == "answer_query":
                submit_input = tool_use["input"]
                continue

            step = _call_tool(tool_use["input"], state, on_step)
            steps.append(step)
            tool_result_blocks.append(
                {"toolResult": {"toolUseId": tool_use["toolUseId"], "content": [{"json": step["result"]}]}}
            )

        if submit_input is not None:
            return _finalize(submit_input, state, steps)

        if not tool_result_blocks:
            break

        messages.append({"role": "user", "content": tool_result_blocks})

    return _force_conclusion(client, messages, state, steps)
