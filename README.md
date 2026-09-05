# ADAPT — An AI That Adapts With You, Not For You

An agent that senses a change in your world, reasons about which of your existing commitments it actually affects, predicts the consequences of different responses, and proposes — never silently executes — the best next move. Every recommendation comes with a **WHY**: the actual numbers behind it, not a vibe.

**Event:** IGNITE Agentic AI Hackathon 2026 (SimplifyNext)
**Today:** 2026-09-05. Submission ~2026-09-07 — **confirm the exact cutoff with the team.**
**Platform:** AWS sandbox account, `us-east-1` only (see constraints below).

This replaces the earlier PhishTrace concept (a phishing-investigation agent) — full history is still in git if it's ever useful, but the team has pivoted. Everything below is the current direction.

---

## 0. Hard constraints (unchanged from before, still apply)

| Constraint | Detail |
|---|---|
| **Budget** | Bar shows $30 but **access is revoked at $20**. At $30 the account is **terminated**. |
| **Leases** | One per team, no second lease granted. Approval takes **up to 2 working days**. |
| **Region** | `us-east-1` only. |
| **Credentials** | Access keys **expire every 12 hours**. |
| **Banned by cost** | OpenSearch, SageMaker real-time endpoints, NAT Gateway, ALB/NLB, EC2/RDS, Bedrock Provisioned Throughput. |
| **Encouraged** | Bedrock (on-demand), Lambda, DynamoDB on-demand, S3. |

**Deliverables:** Project files (max 5GB), Presentation Deck (max 10 slides), a Digital Solution Video or Simulation Recording (max 5 min). No live deployment required — a working local demo plus a recording is enough.

---

## 1. Problem statement (POV format, per hackathon judging rubric)

> A university student juggling classes, a part-time commitment, club obligations, and a job/internship search needs a way to immediately understand how a single change — a moved deadline, a cancelled meeting, a delayed commute — ripples across everything else they've already committed to, because today that replanning is entirely manual and scattered across a calendar, a messaging app, and a task list, and [cite: average time students spend re-arranging a schedule per disruption / share of missed deadlines caused by an unnoticed downstream conflict, not by forgetting outright — find a real source before the deck].

Pressure-test: names a specific person and moment (yes); the `[cite: ...]` bracket still needs a real source — **do this before the deck is finalized**, it's currently the weakest link; survives a different solution — the ripple-effect replanning problem exists whether or not ADAPT gets built (yes, passes); not a solution in disguise — describes the person's situation, not "students need an AI scheduling agent."

**Why this needs agentic AI, not a smarter reminder app:** a fixed calendar/reminder tool can tell you *that* something changed. It can't read an unstructured announcement, figure out *which* of your existing, unrelated commitments it now conflicts with, weigh several ways to resolve that conflict against your actual priorities and history, and only then act within bounds you've approved. That's sense → reason → predict → decide → act → learn — a loop, not a single classification.

---

## 2. Scope decision (read this before assuming the pitch = the build)

The original concept describes continuous monitoring across Canvas, email, Telegram, WhatsApp, calendars, and live "digital twin" life simulation. **None of that is buildable credibly in ~3 days**, and a demo that depends on three external OAuth integrations all working live in front of judges is a bigger risk than the idea itself.

What's actually being built:

- The **real** Sense → Reason → Predict → Decide → Act → Learn loop, genuinely working end-to-end.
- **Bounded autonomy**, actually enforced in code, not just described in the pitch: every proposed action is tagged 🟢 auto-safe / 🟡 needs approval / 🔴 never auto-executed, and the backend enforces that tagging when a plan is executed.
- The **WHY button** — every recommendation cites the actual numbers a deterministic tool produced (available hours, completion probability), not an invented-sounding percentage.
- A **seeded scenario** (one persona, "Alex," and the exact deadline-conflict walkthrough from the original pitch) standing in for live calendar/messaging integration. This is a deliberate, disclosed scope cut — say so plainly in the deck rather than implying live integration. Google Calendar (real read/write, well-documented OAuth) is the one stretch integration worth attempting if the core loop is solid with a day or more to spare; Canvas/Telegram/WhatsApp are out of scope for this hackathon.

This mirrors the hackathon's own "Building Agents That Hold Up" guidance: build a short, single-purpose agent that does one job well, over one that half-works across many.

---

## 3. Architecture

```
                    One chat box — POST /chat
                    "Marketing assignment deadline moved
                     from Friday to Tuesday" (typed in, or
                     a demo button — stands in for a real
                     Canvas/email webhook)
                              │
                              ▼
                    ┌───────────────────┐
                    │  classify_intent   │  deterministic keyword router
                    │  (backend/intent)  │  (no model call) — a question goes
                    └─────────┬──────────┘  to the availability agent instead
                              ▼
                    ┌───────────────────┐
                    │   SENSE            │  raw change event (free text)
                    └─────────┬──────────┘
                              ▼
                    ┌───────────────────┐
                    │   REASON           │  Claude reads world_state (schedule,
                    │  (agent loop)      │  tasks, preferences) + the change,
                    └─────────┬──────────┘  identifies the affected task
                              ▼
                    ┌───────────────────┐
              ┌────▶│ detect_conflicts  │  deterministic: remaining work vs
              │     │ (tool)            │  available capacity before new deadline
              │     └─────────┬──────────┘
              │               ▼
              │     ┌───────────────────┐
              │     │   PREDICT          │  agent proposes 2-3 candidate
              │     │ score_option       │  reshuffles; each is scored by a
              │     │ (tool, per option) │  deterministic completion-probability
              │     └─────────┬──────────┘  formula -- not an LLM guess
              │               ▼
              │     ┌───────────────────┐
              └─────│   DECIDE            │  propose_adaptation tool: ranks
                    │ (submit tool)       │  options, recommends one, WHY
                    └─────────┬──────────┘  grounded in the tool numbers above,
                              ▼              each action tagged 🟢/🟡/🔴
                    ┌───────────────────┐
                    │  HUMAN CHECKPOINT  │  shown with the WHY expanded;
                    │  Execute / Reject  │  nothing has been applied yet
                    └─────────┬──────────┘
                              ▼
                    ┌───────────────────┐
                    │   ACT               │  apply_adaptation: commits 🟢/🟡
                    │ (only on approval)  │  actions to world_state; any 🔴
                    └─────────┬──────────┘  action is refused, not executed
                              ▼
                    ┌───────────────────┐
                    │   LEARN             │  log_feedback: approve/reject
                    │                     │  nudges preference weights (e.g.
                    └───────────────────┘  "protect basketball") for next time
```

### Why each piece is a deterministic tool, not just the LLM talking

`detect_conflicts` and `score_option` are plain Python, not model calls. The 87%-style completion-probability number in the demo has to come from a real, explainable formula (available hours vs. hours required, adjusted for the task's actual progress) — an LLM inventing a percentage that *sounds* right is exactly the kind of thing that falls apart under a judge's first follow-up question. The agent's job is deciding *which* options to generate and *how to explain* the numbers in plain language, grounded in what the tools actually returned — the same evidence-grounding pattern that worked well in the earlier build.

### A second capability: natural-language availability queries

On top of the change-adaptation loop, a separate lightweight agent (`backend/query_agent.py`) answers questions like *"which days am I free," "which periods am I free for more than 2 hours," "which days am I free between Monday and Friday,"* or *"what time should I go to the gym"* — grounded in the same `WorldState`.

- **`find_free_slots`** (`backend/tools/find_free_slots.py`) is the deterministic engine: literal interval arithmetic over the schedule (merge busy intervals, subtract from a 07:00–23:00 waking window), fully testable without AWS. It's intentionally a *different* measure from `score_option`'s `daily_capacity_hours` (a conservative planning ceiling) — literal calendar gaps and "realistic deep-work capacity" can legitimately disagree, and that's fine as long as it's documented rather than silently confusing.
- The agent's job is narrower than the adaptation loop: interpret the free-text question into a day range + minimum duration, call `find_free_slots`, and — for "what time should I do X" questions — recommend one of the *actual returned slots* with a reason. Same grounding-by-construction pattern: the server recomputes the slots from the interpreted range rather than trusting whatever the model said during the loop, and a recommended slot that doesn't match a real free slot is dropped with a warning, not silently kept.
- The frontend calendar (Day/Week/Month/Year/Custom-range toggle) anchors the seed's `Mon`.."Sun" labels to the current real-world week, so Month/Year render as genuine date grids — only that one week has data, same as any freshly-started calendar app.
- **One chat room, not two input boxes.** Both capabilities are reached through a single conversational thread (`POST /chat`) rather than separate "report a change" and "ask a question" forms. A deterministic classifier (`backend/intent.py` — question marks / "which day" / "what time" / "free for" style markers, zero AWS cost) routes each message to whichever agent actually handles it; the two agents themselves stay separate underneath, since they're solving genuinely different problems. A query response's slot-picker renders inline in the chat bubble — click a free slot, adjust the exact start/end, name it, and it's written back to `world_state` via `POST /schedule-event`. The calendar itself stays as a separate panel next to the chat, since it's a live state view rather than a conversation turn.

### Automatic topic color-coding

Every schedule item gets a `category` (academic/career/social/health/personal), assigned by a deterministic keyword classifier (`backend/categorize.py`) that runs on every load and save in `world_state.py` — covers seed items, adaptation-generated study blocks, and user-added events alike without needing to remember to categorize at every call site. It's a real, disclosed limitation of pure keyword matching that something like "coffee with advisor" lands as "social" instead of "academic" — a context-aware LLM call could do better, but would cost an AWS round-trip on every single event creation, which isn't worth it for a topic label.

**Color is a display preference, not data** — it's owned entirely client-side (`localStorage`, `adapt_category_colors`), not round-tripped to the backend. The calendar shows a color-swatch legend per category in use; click a swatch to open a native color picker and the whole calendar re-renders with the new color immediately. This is the deliberate split: the backend decides *what topic* an event is (data, needs to be consistent), the frontend decides *what color represents that topic for this viewer* (personal preference, no reason to touch the server).

---

## 4. Bounded autonomy (the credibility mechanism)

| Tier | Examples in this scenario | Enforcement |
|---|---|---|
| 🟢 Auto-safe | Reorganize the internal task list, generate a study-block breakdown, compute the recommendation | Applied as soon as a plan is generated — no approval needed, nothing external or hard to undo |
| 🟡 Needs approval | Move a calendar event, draft a message to a teammate | Only committed to `world_state` when the user clicks **Execute adaptation** — a drafted message is shown as text, never auto-sent (no real messaging integration exists, and it shouldn't pretend to) |
| 🔴 Never auto-executed | Dropping a commitment entirely, anything financial | The backend refuses to apply a 🔴-tagged action even if the model proposes one — flagged for the user to handle manually, not automated around |

This tiering is enforced in `backend/tools/apply_adaptation.py`, not just asserted in the prompt — a judge asking "what stops it from just sending the email itself" has a concrete code-level answer.

---

## 5. Model selection (Amazon Bedrock, us-east-1)

Same reasoning as before: Claude Haiku 4.5 is the hackathon's own recommended default — fast and cheap enough that a multi-step reasoning loop stays quick and affordable, and tool-use/structured-output quality is well within what this needs.

| Job | Model | Bedrock model ID |
|---|---|---|
| Adaptation loop (`agent.py`, Converse tool use) | Claude Haiku 4.5 | `us.anthropic.claude-haiku-4-5-v1:0` |
| Availability-query loop (`query_agent.py`) | Claude Haiku 4.5 | same — both read `BEDROCK_MODEL_ID` from the env |
| Escalation for low-confidence proposals *(discussed, not built)* | Claude Sonnet | confirm exact ID in the Bedrock console |

**Verify the Haiku model ID before rehearsing** — `aws bedrock list-inference-profiles --region us-east-1 | grep haiku`. The ID above is only what `backend/bedrock.py` falls back to when `BEDROCK_MODEL_ID` is unset; if it's wrong, every Bedrock call fails — and the first Bedrock call in this repo has not happened yet (see §8). Override it in `.env`, not in code.

Token usage from every call is appended to `data/usage_log.jsonl` by `bedrock._log_usage`, so spend stays visible against the $20 cutoff.

---

## 6. Repo layout

```
adapt/
├── README.md
├── requirements.txt
├── .env.example                  # AWS creds + BEDROCK_MODEL_ID
├── backend/
│   ├── main.py                    # FastAPI: /chat (the only one the UI calls), /state, /reset,
│   │                                # /execute, /feedback, /schedule-event, /health — plus
│   │                                # /inject-change and /query, direct access to each agent
│   ├── bedrock.py                  # boto3 Converse wrapper (generic, reused as-is)
│   ├── agent.py                     # adaptation loop: detect_conflicts -> score_option (per
│   │                                 # candidate) -> propose_adaptation
│   ├── query_agent.py                # availability-query loop: find_free_slots -> answer_query
│   ├── world_state.py                 # loads/saves data/world_state.json, seeded from
│   │                                    # data/world_state.seed.json; /reset restores the seed
│   ├── intent.py                        # keyword router behind /chat — which agent handles this
│   ├── categorize.py                     # keyword topic labels, re-derived on every load/save
│   ├── time_utils.py / capacity.py        # date/interval arithmetic shared by both agents' tools
│   ├── tools/
│   │   ├── detect_conflicts.py         # deterministic: remaining work vs. available capacity
│   │   ├── score_option.py              # deterministic: completion-probability formula
│   │   ├── find_free_slots.py            # deterministic: literal schedule-gap interval arithmetic
│   │   ├── apply_adaptation.py           # commits an approved plan, enforcing 🟢/🟡/🔴
│   │   └── log_feedback.py                # the Learn step: nudges preference weights
│   └── schema.py                     # Pydantic models for world state, the adaptation proposal,
│                                       # and the availability-query response
├── frontend/
│   ├── index.html                  # calendar panel (Day/Week/Month/Year/Range) + the chat
│   │                                # room; page orchestration lives in an inline <script>
│   ├── app.js                       # render functions only: calendar views, proposal card,
│   │                                 # inline slot picker, category color handling
│   └── style.css
└── data/
    ├── world_state.seed.json      # Alex's schedule/tasks/preferences -- the demo scenario
    ├── world_state.json           # gitignored working copy the demo mutates; /reset rebuilds it
    └── usage_log.jsonl            # gitignored; one line of token usage per Bedrock call
```

---

## 7. Setup

**Python 3.10 or newer is required.** `backend/schema.py` uses `X | None` annotations that Pydantic resolves at runtime, so 3.9 fails at import with `TypeError: unsupported operand type(s) for |`. Check `python3 --version` first — macOS system Python is still 3.9.

```bash
python3 -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
uvicorn backend.main:app --reload
```

Then open `frontend/index.html`. Everything deterministic — `detect_conflicts`, `score_option`, `find_free_slots`, `apply_adaptation`, `log_feedback`, `categorize`, `classify_intent` — needs no AWS access at all and can be developed and tested entirely offline. Only the two agent loops (`/chat`, `/inject-change`, `/query`) call Bedrock.

---

## 8. Three-day plan

| Day | Ship | Status |
|---|---|---|
| **Fri 09-04** | `world_state.py` + seed data matching the exact pitch scenario. `detect_conflicts` and `score_option` — both fully testable offline, no AWS needed. Nail the numbers so the "good" option scores clearly better than a naive one. | ✅ done — and the numbers hold: 0.89 recommended vs. 0.72 naive (§9) |
| **Sat 09-05 (today)** | Wire the agent loop (Converse tool-use, Haiku) once Bedrock access is confirmed. **Goal: a real end-to-end run — inject the change, get a grounded proposal back — by tonight.** | ⚠️ code written, **never executed** — see below |
| **Sun 09-06** | `apply_adaptation` with real tier enforcement, `log_feedback` for the Learn step, the frontend (Before/After view, WHY-expandable proposal card, Execute/Reject). Rehearse the demo script below. | ✅ code done (also: calendar UI, availability agent, chat room, topic colors — pulled forward from the stretch list). Rehearsal not started |
| **Mon 09-07 (buffer / submission)** | Fix whatever the rehearsal exposed. Record the fallback video. Slides. Freeze code. Stretch only if there's real time left: a real Google Calendar read/write. | ⬜ not started |

> **The single biggest open risk: the Bedrock loop has never actually run.** There is no `.env`, no `data/usage_log.jsonl`, and no `data/world_state.json` in the working tree — all three appear the moment a real call succeeds. Every deterministic tool is verified, but `agent.py` and `query_agent.py` have only ever been read, not executed. Getting one real end-to-end `/chat` round-trip is worth more right now than any further feature, because it's the only thing standing between "the demo works" and "the demo works on stage."
>
> Separately, §1's `[cite: ...]` bracket is still unfilled — the weakest thing in the deck.

---

## 9. Output contract

What `POST /chat` actually returns for the seed scenario. Every number below was produced by running the real tools against `data/world_state.seed.json` — not written by hand.

```json
{
  "kind": "adaptation",
  "steps": [
    {"tool": "detect_conflicts", "input": {"task_id": "task1", "new_due_day": "Tue"}, "result": {"...": "..."}},
    {"tool": "score_option", "input": {"...": "..."}, "result": {"completion_probability": 0.89, "...": "..."}}
  ],
  "warnings": [],
  "proposal": {
    "change_summary": "Marketing assignment deadline moved from Friday to Tuesday",
    "conflict": {
      "task_id": "task1",
      "task_title": "Marketing assignment",
      "old_due_day": "Fri",
      "new_due_day": "Tue",
      "remaining_hours": 4.0,
      "available_hours_before_new_due": 2.5,
      "shortfall_hours": 1.5,
      "movable_items_in_window": ["mtg1", "gym1"]
    },
    "options": [
      {
        "id": "A",
        "summary": "Move the group meeting to Thu and basketball to Tue, then block Mon 15:00-19:00 to study",
        "actions": [
          {"type": "block_study_time", "day": "Mon", "start": "15:00", "end": "19:00", "tier": "green"},
          {"type": "move_event", "item_id": "mtg1", "to_day": "Thu", "to_start": "14:00", "to_end": "15:00", "tier": "yellow"},
          {"type": "move_event", "item_id": "gym1", "to_day": "Tue", "to_start": "19:00", "to_end": "20:30", "tier": "yellow"},
          {"type": "draft_message", "recipient": "project team", "message": "Can we push Monday's meeting to Thursday? My marketing deadline moved up.", "tier": "yellow"}
        ],
        "completion_probability": 0.89,
        "breakdown": "4.0h of 4.0h needed are covered before the deadline (5.0h available after proposed moves, +2.5h freed by them); -0.06 probability for moving a protected commitment"
      },
      {
        "id": "B",
        "summary": "Protect basketball — move only the group meeting, block Mon 15:00-18:00",
        "actions": ["... move_event mtg1 -> Thu, block_study_time Mon 15:00-18:00 ..."],
        "completion_probability": 0.84,
        "breakdown": "3.0h of 4.0h needed are covered before the deadline (3.5h available after proposed moves, +1.0h freed by them)"
      },
      {
        "id": "C",
        "summary": "Change nothing else — just block Mon 15:00-17:00",
        "actions": ["... block_study_time Mon 15:00-17:00 ..."],
        "completion_probability": 0.72,
        "breakdown": "2.0h of 4.0h needed are covered before the deadline (2.5h available after proposed moves, +0.0h freed by them)"
      }
    ],
    "recommended_option_id": "A",
    "reasoning": "Option A is the only one that fully covers the 4 hours still needed. B protects basketball but leaves an hour uncovered, which means the assignment plausibly doesn't get finished; A moves basketball by one day rather than cancelling it, which costs 0.06 of probability and no commitment. Neither option touches Wednesday's internship interview.",
    "investigation_steps": 4
  }
}
```

**Notes for anyone reading the numbers off this contract:**

- **`item_id`, not `item`** — `move_event` addresses a schedule item by its id (`gym1`), which is why `_describe_state` feeds the ids to the model in the prompt.
- **The model never submits a probability.** `propose_adaptation`'s schema has no field for one. The server re-runs `detect_conflicts` and `score_option` over the exact submitted actions in `agent._finalize` and attaches the results. A recommendation that doesn't match a submitted option is replaced and recorded in `warnings`.
- **The spread is the point.** 0.89 recommended vs. 0.72 for the do-nothing-else baseline is a real gap produced by a real formula, and it holds up to "how did you calculate that": `0.5 + 0.45 x coverage - penalty`, where coverage is study hours booked over hours still required, capped at the hours actually free after the proposed moves.
- **The deadline day itself is excluded** from the window — `window_days` is end-exclusive, so a Tuesday deadline gives you Monday only. That is deliberate and conservative; it's also why 4 hours of work has just 2.5 hours to land in.

**The WHY is always the grounded numbers** (`remaining_hours`, `available_hours_before_new_due`, `completion_probability`) **plus which real tool produced them** — never a plain-language claim with nothing under it.

---

## 10. The demo script (from the original pitch, kept close to what was scripted)

1. **Hook:** "Your life changed 30 seconds ago." Show the Before schedule.
2. **Inject the change:** "🚨 Professor announces: Marketing assignment deadline moved forward 3 days."
3. **Watch the loop run**, visibly: conflict detected → candidate options generated → each scored → recommendation with WHY.
4. **Click WHY:** show the actual numbers, not a vibe.
5. **Execute adaptation** → the schedule updates, a draft message appears (marked "not sent — drafted for you to review"), tier badges visible on each action.
6. **Close on bounded autonomy:** "ADAPT never replaces my judgment. It makes my judgment more adaptive."

---

## 11. Known limitations

Disclosed on purpose — a judge who finds one of these before you mention it is worse than mentioning it first. None are hard to answer for; several are deliberate scope cuts.

| # | Limitation | Where | Why it's acceptable / what it'd take |
|---|---|---|---|
| 1 | **The Bedrock loop has never been run.** The deterministic tools are verified; the two agent loops are code-reviewed only. | `agent.py`, `query_agent.py` | Not acceptable — this is the top priority (§8). Needs credentials and one real `/chat` round-trip. |
| 2 | **A question mark routes to the availability agent.** "Did my deadline move to Tuesday?" is read as a query, not a change. Conversely a query with no `?` and no marker phrase ("tell me when I'm not busy") runs the full 8-turn adaptation loop. | `intent.py:15` | Deliberate: a zero-cost classifier beats an LLM round-trip per message. The demo script never phrases a change as a question. Cheap fix: require a marker rather than accept a bare `?`. |
| 3 | **No collision checking when actions are applied.** A `block_study_time` or `move_event` can land on top of an existing item. | `apply_adaptation.py` | Real gap. `find_free_slots` already has the interval arithmetic — wiring it in is ~15 lines, worth doing if Sunday allows. |
| 4 | **ID counters reset on server restart.** `_next_event_id` and `_next_id_counter` live in memory, so a restarted server re-issues `user1` / `study1` and can collide with ids already in `world_state.json`. | `main.py:97`, `apply_adaptation.py:3` | Only bites across a restart without a `/reset`. Deriving the next id from the loaded state closes it. |
| 5 | **Keyword categorization mislabels context-dependent titles.** "Coffee with advisor" lands as `social`, not `academic`. | `categorize.py` | Deliberate: a context-aware label would cost a Bedrock round-trip per event created — not worth it for a color. |
| 6 | **Two different notions of "free" coexist.** `daily_capacity_hours` (a conservative deep-work ceiling — Mon: 5.0h) and literal calendar gaps (Mon: 11.5h across four slots) legitimately disagree. | `capacity.py` vs. `find_free_slots.py` | Deliberate, documented in both files. Don't let anyone read one as a bug in the other — the availability answer and the deadline math measure different things on purpose. |
| 7 | **Dead code in the frontend.** `submitQuery` and `injectChange` predate the chat room; nothing calls them now that everything routes through `/chat`. | `frontend/app.js` | Harmless, but delete before freezing the code. |
| 8 | **A drafted message is never sent, and no real calendar is ever written.** "Act" means mutating `world_state.json` and displaying drafted text. | by design | This is the bounded-autonomy claim, not a shortcoming — but say it out loud rather than letting the demo imply otherwise. |

---

## 12. Guidance for Claude Code

- **Keep `detect_conflicts` and `score_option` deterministic and dependency-free.** They're the credibility of the whole demo — an LLM-generated percentage would not survive a judge asking "how did you calculate that."
- **Bound the agent loop** the same way as before: a hard iteration cap independent of the model's own judgement.
- **Enforce tiers in code**, in `apply_adaptation.py` — never trust the model's own tier tag without a server-side check against an allowed-action list.
- **Never actually send a drafted message or write to a real calendar** unless a real integration is deliberately added later — until then, "act" means mutating `world_state.json` and showing drafted text, full stop.
- **Log every Bedrock call's token usage**, same pattern as before, so spend stays visible against the $20 cutoff.
- **The seed scenario is the source of truth for the demo.** Don't let ad-hoc test inputs drift the numbers away from what's rehearsed.
