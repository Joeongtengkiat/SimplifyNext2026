# ADAPT — An AI That Adapts With You, Not For You

An agent that senses a change in your world, reasons about which of your existing commitments it actually affects, predicts the consequences of different responses, and proposes — never silently executes — the best next move. Every recommendation comes with a **WHY**: the actual numbers behind it, not a vibe.

**Event:** IGNITE Agentic AI Hackathon 2026 (SimplifyNext)
**Today:** 2026-09-04. Submission ~2026-09-07 — **confirm the exact cutoff with the team.**
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
                    "Marketing assignment deadline moved
                     from Friday to Tuesday" (typed in, or
                     a demo button — stands in for a real
                     Canvas/email webhook)
                              │
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
| Agent loop (tool use, Converse API) | Claude Haiku 4.5 | `us.anthropic.claude-haiku-4-5-v1:0` |
| Escalation for low-confidence proposals *(optional, reuse the earlier pattern)* | Claude Sonnet | confirm exact ID in the Bedrock console |

---

## 6. Repo layout

```
adapt/
├── README.md
├── requirements.txt
├── .env.example                  # AWS creds + BEDROCK_MODEL_ID
├── backend/
│   ├── main.py                    # FastAPI: /state, /inject-change, /execute, /feedback, /reset,
│   │                                # /query, /schedule-event
│   ├── bedrock.py                  # boto3 Converse wrapper (generic, reused as-is)
│   ├── agent.py                     # adaptation loop: detect_conflicts -> score_option (per
│   │                                 # candidate) -> propose_adaptation
│   ├── query_agent.py                # availability-query loop: find_free_slots -> answer_query
│   ├── world_state.py                 # loads/saves data/world_state.json, seeded from
│   │                                    # data/world_state.seed.json; /reset restores the seed
│   ├── time_utils.py / capacity.py     # date/interval arithmetic shared by both agents' tools
│   ├── tools/
│   │   ├── detect_conflicts.py         # deterministic: remaining work vs. available capacity
│   │   ├── score_option.py              # deterministic: completion-probability formula
│   │   ├── find_free_slots.py            # deterministic: literal schedule-gap interval arithmetic
│   │   ├── apply_adaptation.py           # commits an approved plan, enforcing 🟢/🟡/🔴
│   │   └── log_feedback.py                # the Learn step: nudges preference weights
│   └── schema.py                     # Pydantic models for world state, the adaptation proposal,
│                                       # and the availability-query response
├── frontend/
│   ├── index.html                  # calendar (Day/Week/Month/Year/Range), Inject Change,
│   │                                # availability query box, slot-picker modal
│   ├── style.css
│   └── app.js
└── data/
    └── world_state.seed.json      # Alex's schedule/tasks/preferences -- the demo scenario
```

---

## 7. Setup

```bash
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
uvicorn backend.main:app --reload
```

Then open `frontend/index.html`. `detect_conflicts` and `score_option` need no AWS access at all and can be developed/tested entirely offline; only `/inject-change` (the actual reasoning step) needs Bedrock credentials.

---

## 8. Three-day plan

| Day | Ship |
|---|---|
| **Fri 09-04 (today)** | `world_state.py` + seed data matching the exact pitch scenario. `detect_conflicts` and `score_option` — both fully testable offline, no AWS needed. Nail the numbers so the "good" option scores clearly better than a naive one. |
| **Sat 09-05** | Wire the agent loop (Converse tool-use, Haiku) once Bedrock access is confirmed. **Goal: a real end-to-end run — inject the change, get a grounded proposal back — by tonight.** |
| **Sun 09-06** | `apply_adaptation` with real tier enforcement, `log_feedback` for the Learn step, the frontend (Before/After view, WHY-expandable proposal card, Execute/Reject). Rehearse the demo script below. |
| **Mon 09-07 (buffer / submission)** | Fix whatever the rehearsal exposed. Record the fallback video. Slides. Freeze code. Stretch only if there's real time left: a real Google Calendar read/write. |

---

## 9. Output contract

```json
{
  "change_summary": "Marketing assignment deadline moved from Friday to Tuesday",
  "conflict": {
    "task": "Marketing assignment",
    "remaining_hours": 4.0,
    "available_hours_before_new_due": 2.5,
    "shortfall_hours": 1.5
  },
  "options": [
    {
      "id": "A",
      "summary": "Move gym Mon->Tue, move project meeting Mon->Thu, block Mon 3-5pm to study",
      "completion_probability": 0.87,
      "actions": [
        {"type": "block_study_time", "day": "Mon", "start": "15:00", "end": "17:00", "tier": "green"},
        {"type": "move_event", "item": "Basketball", "to_day": "Tue", "to_start": "19:00", "tier": "yellow"},
        {"type": "draft_message", "to": "project team", "tier": "yellow"}
      ]
    }
  ],
  "recommended_option_id": "A",
  "reasoning": "Option A closes the 1.5-hour shortfall without touching the Wednesday interview, and only moves basketball by one day rather than cancelling it.",
  "investigation_steps": 4
}
```

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

## 11. Guidance for Claude Code

- **Keep `detect_conflicts` and `score_option` deterministic and dependency-free.** They're the credibility of the whole demo — an LLM-generated percentage would not survive a judge asking "how did you calculate that."
- **Bound the agent loop** the same way as before: a hard iteration cap independent of the model's own judgement.
- **Enforce tiers in code**, in `apply_adaptation.py` — never trust the model's own tier tag without a server-side check against an allowed-action list.
- **Never actually send a drafted message or write to a real calendar** unless a real integration is deliberately added later — until then, "act" means mutating `world_state.json` and showing drafted text, full stop.
- **Log every Bedrock call's token usage**, same pattern as before, so spend stays visible against the $20 cutoff.
- **The seed scenario is the source of truth for the demo.** Don't let ad-hoc test inputs drift the numbers away from what's rehearsed.
