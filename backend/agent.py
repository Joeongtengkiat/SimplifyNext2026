import re
from typing import Callable

from backend import world_state
from backend.bedrock import converse, get_client
from backend.schema import AdaptationAction, AdaptationOption, AdaptationProposal, WorldState
from backend.tools.create_task import create_task
from backend.tools.detect_conflicts import detect_conflicts
from backend.tools.score_option import score_option

MAX_TURNS = 8

# best-effort check for §11 limitation #9: the model's free-text `reasoning` isn't a structured,
# re-derivable value like the numbers in `options[]`, so nothing guarantees it agrees with them.
# This catches the literal "Option X (NN%...)" pattern the first real run actually produced, plus
# any bare percentage that doesn't match ANY option's real score -- it does not catch a claim
# phrased without a digit ("about the same"), so treat this as risk reduction, not a guarantee.
_OPTION_PERCENT_PATTERN = re.compile(r"\b([A-Za-z][A-Za-z0-9_]*)\s*\(\s*(\d{1,3})\s*%")
_BARE_PERCENT_PATTERN = re.compile(r"\b(\d{1,3})\s*%")


def _check_reasoning_grounding(reasoning: str, options: list[AdaptationOption]) -> list[str]:
    warnings: list[str] = []
    actual_pct = {opt.id: round(opt.completion_probability * 100) for opt in options}

    for match in _OPTION_PERCENT_PATTERN.finditer(reasoning):
        option_id, claimed = match.group(1), int(match.group(2))
        if option_id in actual_pct and actual_pct[option_id] != claimed:
            warnings.append(
                f"Reasoning cites {claimed}% for option {option_id}, but its actual computed "
                f"score is {actual_pct[option_id]}% -- treat the written explanation with caution."
            )

    known_percentages = set(actual_pct.values())
    for match in _BARE_PERCENT_PATTERN.finditer(reasoning):
        claimed = int(match.group(1))
        if claimed not in known_percentages:
            warnings.append(
                f"Reasoning mentions {claimed}%, which doesn't match any option's actual computed "
                f"score ({sorted(known_percentages)}) -- possibly an invented number."
            )

    return warnings

SYSTEM_PROMPT = """You are ADAPT: you help a person replan when something in their schedule \
changes, without ever silently acting on their behalf.

You are given the person's current schedule, tasks, and preferences, plus a change event (e.g. \
a deadline moved). Your job:

0. If the change describes a genuinely new commitment that isn't in the given task list, but \
   names (or clearly implies) a day you CAN place on Mon/Tue/Wed/Thu/Fri/Sat/Sun, call \
   create_task first to record it -- a short clear title, that due day, your best estimate of \
   hours_required if the person didn't say one (state that assumption plainly in \
   change_summary, e.g. "assumed 3h of prep since none was specified" -- never hide a guess), \
   and priority (default medium if unstated). Never ask the person for a task id -- you assign \
   that yourself when you call the tool. Then continue the normal flow below using the id \
   create_task returns. You still have no real calendar and cannot resolve an absolute date \
   (e.g. "September 30th") to a day of this single-week view -- if you can't place the change \
   on Mon-Sun at all, DO NOT guess or substitute a different existing task just to have \
   something to show -- that produces a confident-looking answer about the wrong thing, which is \
   worse than admitting the gap. Instead call propose_adaptation with task_id set to an empty \
   string, an empty options list, and use reasoning to say plainly what you couldn't resolve and \
   why (e.g. "I can't place September 30th within this week -- which day of the week is that?").
1. Identify which task the change refers to and its new due day (must be one of Mon/Tue/Wed/\
   Thu/Fri/Sat/Sun).
2. Call detect_conflicts to find out how big a problem this actually is -- remaining work versus \
   time actually available before the new deadline.
3. Generate 2-3 realistically different candidate plans (which movable commitments to shift, how \
   much study time to block, whether to draft a message to anyone) and call score_option for \
   each one. Never state a completion probability yourself -- only ever report what score_option \
   actually returned for that exact set of actions.
4. Tag every action's tier: "green" (safe to do automatically -- reorganizing internal tasks), \
   "yellow" (needs the person's approval -- moving a calendar event, drafting a message), or \
   "red" (never automate -- dropping a commitment entirely, anything financial). Only propose a \
   red action if genuinely necessary; expect it to be refused rather than executed.
5. Recommend the option with the best real trade-off, not necessarily the single highest number \
   -- e.g. a slightly lower-scoring option that protects something the person clearly cares about \
   may be the better recommendation. Explain the trade-off in your reasoning, grounded only in \
   what the tools actually returned.
6. In your reasoning, do NOT restate exact percentages (e.g. "72%", "89%") -- each option's real \
   score is already shown next to it, so repeating a number from memory only risks getting it \
   wrong. Refer to options by id and describe the trade-off qualitatively instead: what's \
   protected, what's controllable versus dependent on someone else, what's fully covered versus \
   partially covered.
7. Finish by calling propose_adaptation. Never answer in plain text.
"""

_ACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "type": {"type": "string", "enum": ["block_study_time", "move_event", "draft_message"]},
        "tier": {"type": "string", "enum": ["green", "yellow", "red"]},
        "day": {"type": "string", "description": "for block_study_time"},
        "start": {"type": "string", "description": "HH:MM, for block_study_time"},
        "end": {"type": "string", "description": "HH:MM, for block_study_time"},
        "item_id": {"type": "string", "description": "for move_event -- the schedule item id being moved"},
        "to_day": {"type": "string", "description": "for move_event"},
        "to_start": {"type": "string", "description": "HH:MM, for move_event"},
        "to_end": {"type": "string", "description": "HH:MM, for move_event"},
        "recipient": {"type": "string", "description": "for draft_message"},
        "message": {"type": "string", "description": "for draft_message"},
    },
    "required": ["type", "tier"],
}

TOOL_CONFIG = {
    "tools": [
        {
            "toolSpec": {
                "name": "create_task",
                "description": (
                    "Records a genuinely new commitment that isn't in the given task list yet -- "
                    "e.g. a test or assignment the person just mentioned. Commits immediately "
                    "(this is capturing a fact, not acting on the calendar), and returns the new "
                    "task's id so you can use it in detect_conflicts/score_option/propose_adaptation "
                    "right after. Calling it twice for the same title+due_day is safe -- it just "
                    "returns the existing task instead of creating a duplicate."
                ),
                "inputSchema": {
                    "json": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "due_day": {"type": "string", "enum": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]},
                            "hours_required": {
                                "type": "number",
                                "description": "Omit if the person didn't say -- a default estimate will be assumed and flagged.",
                            },
                            "priority": {"type": "string", "enum": ["low", "medium", "high"]},
                        },
                        "required": ["title", "due_day"],
                    }
                },
            }
        },
        {
            "toolSpec": {
                "name": "detect_conflicts",
                "description": (
                    "Check how a task's new due day compares to what's actually schedulable -- "
                    "remaining work required versus hours available before the deadline."
                ),
                "inputSchema": {
                    "json": {
                        "type": "object",
                        "properties": {
                            "task_id": {"type": "string"},
                            "new_due_day": {"type": "string", "enum": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]},
                        },
                        "required": ["task_id", "new_due_day"],
                    }
                },
            }
        },
        {
            "toolSpec": {
                "name": "score_option",
                "description": (
                    "Deterministically scores one candidate plan (a set of actions) and returns "
                    "its actual completion probability. Call this once per candidate plan before "
                    "recommending anything -- never guess a probability yourself."
                ),
                "inputSchema": {
                    "json": {
                        "type": "object",
                        "properties": {
                            "task_id": {"type": "string"},
                            "new_due_day": {"type": "string"},
                            "actions": {"type": "array", "items": _ACTION_SCHEMA},
                        },
                        "required": ["task_id", "new_due_day", "actions"],
                    }
                },
            }
        },
        {
            "toolSpec": {
                "name": "propose_adaptation",
                "description": (
                    "Submit your final adaptation proposal. This is the only way to finish -- do "
                    "not answer in plain text. Do not include probabilities here; the server "
                    "recomputes them from your actions so they're always accurate."
                ),
                "inputSchema": {
                    "json": {
                        "type": "object",
                        "properties": {
                            "change_summary": {"type": "string"},
                            "task_id": {
                                "type": "string",
                                "description": (
                                    "Must match an id from the given task list. Leave as an empty "
                                    "string if the change doesn't refer to any task you were given, "
                                    "or names a date/day you can't place in Mon-Sun -- never "
                                    "substitute a different existing task."
                                ),
                            },
                            "new_due_day": {"type": "string"},
                            "options": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "id": {"type": "string"},
                                        "summary": {"type": "string"},
                                        "actions": {"type": "array", "items": _ACTION_SCHEMA},
                                    },
                                    "required": ["id", "summary", "actions"],
                                },
                            },
                            "recommended_option_id": {"type": "string"},
                            "reasoning": {
                                "type": "string",
                                "description": (
                                    "Plain-language explanation of the trade-off. Do not restate exact "
                                    "percentages -- refer to options by id and describe what's protected, "
                                    "controllable, or fully vs. partially covered instead. Scores are "
                                    "already shown separately and don't need to be repeated here."
                                ),
                            },
                        },
                        "required": ["change_summary", "task_id", "new_due_day", "options", "recommended_option_id", "reasoning"],
                    }
                },
            }
        },
    ]
}


def _describe_state(state: WorldState) -> str:
    schedule_lines = "\n".join(
        f"- [{s.id}] {s.day} {s.start}-{s.end} {s.title}"
        f"{' (fixed)' if not s.movable else ''}{' (protected)' if s.protected else ''}"
        for s in state.schedule
    )
    task_lines = "\n".join(
        f"- [{t.id}] {t.title}: due {t.due_day}, {t.hours_completed}/{t.hours_required}h done, priority {t.priority}"
        for t in state.tasks
    )
    prefs = ", ".join(f"{k}={v}" for k, v in state.preferences.items())
    return (
        f"Today is {state.today}.\n\nSchedule:\n{schedule_lines}\n\nTasks:\n{task_lines}\n\nPreferences: {prefs}"
    )


def _call_tool(name: str, tool_input: dict, state: WorldState, on_step: Callable[[dict], None] | None) -> dict:
    try:
        if name == "create_task":
            task, note = create_task(
                state,
                title=tool_input["title"],
                due_day=tool_input["due_day"],
                hours_required=tool_input.get("hours_required"),
                priority=tool_input.get("priority", "medium"),
            )
            world_state.save(state)  # commit immediately -- recording a fact, not acting on the
            # calendar, so unlike block_study_time/move_event this doesn't wait for an Execute
            # click on a proposed option
            result = {"task": task.model_dump(), "note": note}
        elif name == "detect_conflicts":
            result = detect_conflicts(state, tool_input["task_id"], tool_input["new_due_day"]).model_dump()
        elif name == "score_option":
            actions = [AdaptationAction(**a) for a in tool_input["actions"]]
            result = score_option(state, tool_input["task_id"], tool_input["new_due_day"], actions).model_dump()
        else:
            result = {"error": f"unknown tool '{name}'"}
    except Exception as e:  # a bad tool input shouldn't kill the whole run
        result = {"error": f"{type(e).__name__}: {e}"}

    step = {"tool": name, "input": tool_input, "result": result}
    if on_step:
        on_step(step)
    return step


def _finalize(raw_input: dict, state: WorldState, steps: list[dict]) -> dict:
    """Recomputes every number authoritatively from the proposed actions -- the model never gets
    to just restate a probability it saw earlier in the loop."""
    warnings: list[str] = []
    try:
        task_id, new_due_day = raw_input["task_id"], raw_input["new_due_day"]

        if not task_id or not any(t.id == task_id for t in state.tasks):
            # the model correctly declined rather than fabricating a conflict against an
            # unrelated existing task -- surface its own explanation as-is, don't synthesize a
            # fake conflict just to fill the field (see the exception fallback below, which used
            # to make exactly that mistake)
            proposal = AdaptationProposal(
                change_summary=raw_input.get("change_summary", ""),
                conflict=None,
                options=[],
                recommended_option_id="",
                reasoning=raw_input.get(
                    "reasoning", "This doesn't match a task or day currently tracked."
                ),
                investigation_steps=len(steps),
            )
            return {"steps": steps, "proposal": proposal.model_dump(), "warnings": warnings}

        conflict = detect_conflicts(state, task_id, new_due_day)

        options = []
        for raw_opt in raw_input["options"]:
            actions = [AdaptationAction(**a) for a in raw_opt["actions"]]
            scored = score_option(state, task_id, new_due_day, actions)
            options.append(
                AdaptationOption(
                    id=raw_opt["id"],
                    summary=raw_opt["summary"],
                    actions=actions,
                    completion_probability=scored.completion_probability,
                    breakdown=scored.breakdown,
                )
            )

        if raw_input["recommended_option_id"] not in {o.id for o in options}:
            warnings.append("recommended_option_id didn't match any submitted option; defaulting to the first")
            recommended_id = options[0].id if options else ""
        else:
            recommended_id = raw_input["recommended_option_id"]

        warnings.extend(_check_reasoning_grounding(raw_input["reasoning"], options))

        proposal = AdaptationProposal(
            change_summary=raw_input["change_summary"],
            conflict=conflict,
            options=options,
            recommended_option_id=recommended_id,
            reasoning=raw_input["reasoning"],
            investigation_steps=len(steps),
        )
    except Exception as e:
        # the model's output only ever *hints* at this schema (Bedrock doesn't hard-enforce it
        # the way Anthropic's own strict tool use does) -- a malformed options[] entry (e.g. a
        # bare string instead of {id, summary, actions}) raises TypeError, not just the
        # KeyError/ValidationError this used to be narrowed to. Anything going wrong while
        # parsing the model's own output should degrade to this fallback, never crash the request.
        warnings.append(f"propose_adaptation output failed validation: {type(e).__name__}: {e}")
        proposal = AdaptationProposal(
            change_summary=raw_input.get("change_summary", "(unparseable)"),
            conflict=None,  # never fabricate a conflict against an arbitrary task just to fill
            # the field -- an honest "couldn't validate" beats a plausible-looking wrong one
            options=[],
            recommended_option_id="",
            reasoning="The agent's proposal could not be validated; review manually.",
            investigation_steps=len(steps),
        )

    return {"steps": steps, "proposal": proposal.model_dump(), "warnings": warnings}


def _force_conclusion(client, messages: list[dict], state: WorldState, steps: list[dict]) -> dict:
    messages.append(
        {
            "role": "user",
            "content": [{"text": "You must conclude now. Call propose_adaptation with your best plan based on what you've found so far."}],
        }
    )
    try:
        response = converse(
            client, messages, SYSTEM_PROMPT, TOOL_CONFIG, tool_choice={"tool": {"name": "propose_adaptation"}}
        )
        for block in response["output"]["message"]["content"]:
            if block.get("toolUse", {}).get("name") == "propose_adaptation":
                return _finalize(block["toolUse"]["input"], state, steps)
    except Exception:
        pass

    return {
        "steps": steps,
        "proposal": None,
        "warnings": ["Forced conclusion failed; no proposal could be generated."],
    }


def run_adaptation(change_text: str, state: WorldState, on_step: Callable[[dict], None] | None = None) -> dict:
    client = get_client()
    messages = [
        {
            "role": "user",
            "content": [{"text": f"{_describe_state(state)}\n\nChange event: {change_text}"}],
        }
    ]
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
            if tool_use["name"] == "propose_adaptation":
                submit_input = tool_use["input"]
                continue

            step = _call_tool(tool_use["name"], tool_use["input"], state, on_step)
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
