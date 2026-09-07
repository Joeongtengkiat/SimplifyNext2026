# ADAPT — Demo Script

Target length: ~5 minutes (live or recorded). Timings include buffer; cut the Month/Year tour
first if running long — the adaptation loop (0:55–2:40) is non-negotiable, it's the whole thesis.

---

## Before you record: one open item

The problem statement (`README.md` §1) still has an unfilled `[cite: ...]` bracket — it asserts
people lose time to manual replanning without a source. Either find a real citation fast (a
student-survey stat, even informal), or soften the claim to something defensible without one
("most students I've talked to..."). An unsupported number is worse than no number if a judge
asks where it came from.

---

## 1. Problem statement + why agentic AI (0:00–0:55)

**Hook:**
> "Your life changed 30 seconds ago."

**Problem:**
> "A university student juggling classes, a part-time job, and an internship search needs a way
> to know how a single change — a moved deadline, a cancelled meeting — ripples across
> everything they've already committed to. Today that replanning is entirely manual, spread
> across a calendar, a messaging app, and a task list."

**Why this needs agentic AI (say close to verbatim — this is the sharpest version we have, and
it's the part judges explicitly grade):**
> "A calendar can tell you that something changed. It can't read an unstructured announcement
> and figure out which of your other commitments it now conflicts with. It can't weigh three
> different ways to fix that conflict against your actual priorities. It can't explain why one
> option beats another with real numbers. That's sense, reason, predict, decide, act, learn — a
> loop, not a single lookup. That's why this needs an agent, not a smarter reminder."

---

## 2. Model & backend (weave into the demo at 1:10–1:40, don't stop for a slide)

> "This runs on Claude Haiku 4.5 through AWS Bedrock. Two agent loops — one for replanning, one
> for availability questions — behind a single chat endpoint, routed by a free, zero-cost
> keyword classifier so we're not spending a model call just to decide who answers. But the
> important part: the numbers you're about to see aren't the model guessing. `detect_conflicts`
> and `score_option` are plain deterministic Python — the model's job is deciding *what* to
> check and explaining trade-offs in plain language; the server recomputes every number from
> scratch before it's ever shown to you. The model literally isn't allowed to report a number it
> made up."

That last line is the strongest technical-quality answer available — it pre-empts "how do you
know that's not just an LLM sounding confident."

---

## 3. Full feature list (reference — not all of this fits in 5 minutes live)

**Adaptation loop (the centerpiece)**
- Natural-language change detection ("deadline moved from Friday to Tuesday")
- New-task creation from chat ("I have a test on Thursday") — records it, assumes a labeled default for anything unstated (e.g. hours needed), then plans around it like any tracked task
- Deterministic conflict detection (remaining hours vs. available hours before deadline)
- 2–3 generated candidate plans, each scored by a real completion-probability formula
- WHY button — expandable, shows the actual grounded math
- Bounded autonomy tiers (🟢 auto-safe / 🟡 needs approval / 🔴 never auto-executed), enforced in code
- Execute / Reject with real state mutation
- Collision detection — won't double-book an existing commitment
- Draft-message generation (shown, never sent)
- Learn step — approve/reject nudges preference weights for next time

**Availability query agent (second capability)**
- Natural-language free-time questions ("which days am I free for more than 2 hours?", "what
  time should I go to the gym?")
- Real interval-arithmetic slot-finding, not an LLM guess
- Slot picker: click a free slot, adjust start/end, name it, add to calendar

**Unified interface**
- Single chat room — one input handles both capabilities, routed automatically
- Calendar: Day (real hour timeline with a live "now" line), Week, Month, Year, Custom range
- Automatic topic color-coding (academic/career/social/health/personal), click-to-customize per viewer
- Reset button for repeatable demos

**Under the hood (technical-quality talking points if pressed)**
- Grounding-by-construction: server re-derives every number, never trusts the model's own restatement
- A safety net that catches the model misstating its own numbers in prose (found and fixed
  during testing — good "we test this seriously" story)
- Token usage logged per call for cost visibility
- Both agent loops verified against live Bedrock, not just unit-tested

---

## 4. Timed script

| Time | Say | Show / Click |
|---|---|---|
| 0:00–0:55 | Hook + problem statement + why-agentic-AI (§1 above) | Calendar in **Day view**, today's schedule visible |
| 0:55–1:10 | "Watch what happens when something changes." | Click the **"Deadline moved up"** quick-suggestion button in chat |
| 1:10–1:40 | Narrate the reasoning trace as it streams: "It's checking conflicts, then scoring three different plans — in parallel, one round-trip, not three." (drop in the model/backend line here — §2) | Reasoning trace appearing in the chat bubble |
| 1:40–2:20 | "Three options, each with a real number behind it — not a vibe." Click **WHY** on the recommended option, read one line of the grounded breakdown aloud | Proposal card, WHY expanded, point at the tier badges (🟢/🟡) |
| 2:20–2:40 | "I approve — nothing happens without me." Click **Execute** | Schedule updates live; point at the drafted message: "drafted, never sent — that's the bounded-autonomy line, enforced in the code, not just the prompt" |
| 2:40–3:00 | Switch calendar view, point at the color-coded categories updating | **Week view** (or Day view again) |
| 3:00–3:40 | "It's not just reactive — ask it something." | Click **"Free for 2+ hours?"** suggestion; slot picker opens; click a slot, adjust time, name it, **Add to calendar** |
| 3:40–3:55 | Quick tour: "Month and Year views for the bigger picture, and every category's color is yours to customize" | Flip to **Month** or **Year**, click a legend swatch once |
| 3:55–4:30 | Close: "ADAPT never replaces my judgment. It makes my judgment more adaptive." | Back to calendar showing the resolved schedule |

That's a full 4:30 — leaves ~30 sec buffer for a stumble or a judge interrupting.

---

## 5. If judges ask

- **"Isn't this just a calendar?"** → §1's "why agentic AI" answer, verbatim if needed.
- **"How do you know the AI isn't just making up that percentage?"** → the grounding-by-construction line (§2).
- **"What stops it from just sending that message itself?"** → "The tier is enforced in
  `apply_adaptation.py` — a red-tier or an unapproved yellow action is refused in code, not just
  discouraged in the prompt. We tested that directly."
- **"Does this actually run, or is it a mockup?"** → "It's running live right now against Claude
  Haiku 4.5 on Bedrock — happy to show a fresh one."
