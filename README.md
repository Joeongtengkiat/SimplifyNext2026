# PhishTrace — Agentic Phishing Investigation Assistant

An agent that investigates a suspicious email or link the way a security analyst would: it decides what to check, chases the evidence across multiple sources, and only stops once it has enough to issue a verdict — rather than running one fixed classifier call.

**Event:** IGNITE Agentic AI Hackathon 2026 (SimplifyNext)
**Submission deadline:** Sun/Mon 2026-09-07/08 — confirm the exact cutoff with the team; official deck says Solution Submission on 7 Sep, semi-finals 9–11 Sep, Grand Finale 18 Sep at NUS.
**Today:** 2026-09-02 (kickoff day) — roughly 5–6 days to build.
**Platform:** AWS sandbox account, `us-east-1` only (constraints below inherited from the team's IGNITE AWS access guide — verify these still hold for this project's lease).

---

## 0. Hard constraints (read before designing anything)

| Constraint | Detail |
|---|---|
| **Budget** | Bar shows $30 but **access is revoked at $20**. At $30 the account is **terminated**. |
| **Leases** | One per team, no second lease granted. Approval takes **up to 2 working days** — request it today if not already done. |
| **Region** | `us-east-1` only. Wrong region = cascade of `Access denied` errors. |
| **Credentials** | Access keys **expire every 12 hours** — re-login to the AWS access portal for fresh ones. |
| **Banned by cost** | OpenSearch, SageMaker real-time endpoints, NAT Gateway, ALB/NLB, EC2/RDS, Bedrock Provisioned Throughput. |
| **Encouraged** | Bedrock (on-demand), Lambda (+ Function URLs), DynamoDB on-demand, S3, S3 Vectors. |

**Set an AWS Budgets alarm at $5 on day one.**

**Deliverables (per official IGNITE guidelines):** Project files (max 5GB), Presentation Deck (max 10 slides), and either a Digital Solution Video or a Simulation Recording (max 5 minutes). **No live public deployment is required** — a working local demo plus a recorded video is enough. This lets us skip Lambda/API Gateway entirely and run the backend locally, which is a meaningful time save given the AWS constraints above.

---

## 1. Problem statement (POV format, per hackathon judging rubric)

> A working adult who receives an unexpected email, SMS, or message with a link needs a fast way to tell whether it's a scam **before** clicking or replying, because phishing and impersonation scams make up a large share of reported scam losses each year [cite: latest national scam statistics — fill in exact figure/source before the deck], and checking a domain's registration age, tracing where a link actually redirects to, and spotting a look-alike page all require technical knowledge or tools most people don't have and don't have time for in the moment.

Pressure-test (per the hackathon's own framework): names a real user and moment (yes), carries evidence to cite (needs a real figure — TODO before submission), stays true regardless of what gets built (yes — the need exists even without agentic AI), is not the "everyone" problem (scoped to "received a suspicious message, deciding whether to act on it").

**Why this needs agentic AI, not just a classifier** (judges explicitly grade this): a single "is this phishing? yes/no" model call can't chase evidence. The value is in the *investigation* — deciding what to check next based on what's already been found (a fresh domain is suspicious but not proof; a redirect to a look-alike login page is much stronger; a web search turning up scam reports settles it), and knowing when it has enough evidence to stop. That adaptive, multi-tool, variable-depth behavior is what a fixed pipeline can't replicate.

---

## 2. Architecture

```
+----------------------+
| Simple web frontend  |  paste an email/message or a URL
| (local, no framework |  watch the agent's investigation
|  required)           |  steps stream in, see the verdict
+----------+-----------+
           | POST /investigate { text? , url? }
           v
+----------------------------------------------+
| FastAPI backend (local, uvicorn)              |
|   agent.py — Bedrock Converse tool-use loop   |
|   Claude Haiku 4.5, bounded to ~6-8 turns     |
+----------------------------------------------+
           |
           v  (Claude decides which tools to call, and when to stop)
+----------------+  +----------------+  +----------------+  +------------------+
| check_domain   |  | fetch_url      |  | web_search     |  | compare_brand    |
| RDAP/WHOIS,    |  | follow         |  | Tavily API —   |  | (stretch) screen-|
| free, no key   |  | redirects,     |  | scam reports,  |  | shot + vision    |
|                |  | fetch page text|  | official site  |  | vs claimed brand |
+----------------+  +----------------+  +----------------+  +------------------+
           |
           v
   Evidence list + risk verdict, shown with the reasoning trail
```

### Why this tool set

- **`check_domain`** — domain age is the single strongest cheap signal (freshly registered domains dominate phishing infrastructure). Free via RDAP (`rdap.org`), no API key.
- **`fetch_url`** — follows the actual redirect chain (phishing links often hop through shorteners/redirectors) and pulls the landing page's cleaned text so Claude can read what it actually says.
- **`web_search`** — the step a fixed classifier can't do: search for the domain/sender/claim to find scam reports, or find the real official site to compare against. Use Tavily (built for LLM agents, free tier, one API key) rather than scraping a search engine.
- **`compare_brand`** *(stretch goal, cut first if time is short)* — screenshot the landing page and ask Claude (vision) whether it visually matches the brand it claims to be. Heavier dependency (headless browser); only add once the core loop is solid.

---

## 3. Model selection (Amazon Bedrock, us-east-1)

| Job | Model | Bedrock model ID |
|---|---|---|
| Agent loop (tool use, Converse API) | Claude Haiku 4.5 — fast, cheap, this is the hackathon's own recommended default | `us.anthropic.claude-haiku-4-5-v1:0` |
| Final verdict + user-facing explanation | Claude Haiku 4.5 | `us.anthropic.claude-haiku-4-5-v1:0` |
| Escalation for ambiguous cases *(optional)* | Claude Sonnet 4.5 — stronger reasoning, single-region | confirm exact ID in the Bedrock console before use |

**Rules of thumb**

- Start with Haiku 4.5 for the whole loop — it's cheap enough to not think about, and tool-orchestration + evidence synthesis is well within its ability.
- Only reach for Sonnet if testing shows Haiku missing distinctions (e.g., an ambiguous but legitimate marketing redirect vs. a real phish) — swap the model for that one call, don't rebuild the loop.
- **Enable model access** in the Bedrock console (us-east-1) the moment the AWS lease is approved — this blocks everything else, do it first.
- Newer Anthropic models on Bedrock need the **`us.` inference-profile prefix**.
- Bedrock pricing is partner-priced, separate from Anthropic's direct API — check current rates before assuming a number.

---

## 4. Repo layout

```
phishtrace/
├── README.md
├── requirements.txt
├── .env.example              # AWS_ACCESS_KEY_ID / SECRET / SESSION_TOKEN / REGION / TAVILY_API_KEY
├── backend/
│   ├── main.py                # FastAPI app, /investigate endpoint, SSE stream of agent steps
│   ├── bedrock.py              # boto3 client, Converse wrapper, retry, token accounting
│   ├── agent.py                 # the tool-use loop: bounded iterations, stop condition
│   ├── tools/
│   │   ├── check_domain.py      # RDAP lookup -> registrar, age_days
│   │   ├── fetch_url.py         # requests + redirect chain + BeautifulSoup text extraction
│   │   ├── web_search.py        # Tavily search wrapper
│   │   └── compare_brand.py     # stretch: screenshot + vision comparison
│   ├── schema.py                # Pydantic models for tool I/O and the final verdict
│   └── store.py                 # local run history (SQLite or JSON), optional
├── frontend/
│   └── index.html                # paste input, stream steps, show evidence + verdict
├── data/
│   └── test_cases/               # a handful of known-phishing and known-legit URLs/emails for eval
└── scripts/
    └── cost_report.py             # sum token usage -> running $ estimate
```

---

## 5. Setup

```bash
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
uvicorn backend.main:app --reload
```

Paste fresh AWS keys from the access portal into `.env` — they expire every 12 hours.

`requirements.txt` baseline:

```
fastapi
uvicorn
boto3
python-dotenv
requests
beautifulsoup4
lxml
tavily-python
pydantic
```

**Never commit `.env`.**

---

## 6. Six-day plan

| Day | Ship |
|---|---|
| **Tue 09-02 (today)** | Confirm/submit AWS lease if not already done (2-day lead time is the critical path). Write `check_domain` and `fetch_url` tools — both work offline against real URLs, zero AWS dependency. Pin down the problem statement's evidence citation. |
| **Wed 09-03** | Lease lands: enable Bedrock model access, boto3 hello-world, wire the Converse tool-use loop with Haiku 4.5 and the two working tools. Test against 3–4 known phishing URLs (PhishTank samples) and 3–4 legitimate sites. |
| **Thu 09-04** | Add `web_search` (Tavily). **Goal: end-to-end verdict on a real suspicious URL by tonight.** Design the evidence output format. |
| **Fri 09-05** | Build the minimal frontend (paste input, stream investigation steps). Add `compare_brand` only if the core loop is solid and there's time left. |
| **Sat 09-06** | Run the test-case set, tune the stop condition and iteration cap, fix cases where the agent over- or under-investigates. Cover this testing methodology in the slides (judges explicitly score it). |
| **Sun 09-07** | Demo script, slides (10-slide structure), record a fallback video, freeze code. |

> **Hard rule: a real end-to-end verdict on a live URL by Thursday night.** A thin working loop beats three disconnected tools.

---

## 7. Output contract

```json
{
  "verdict": "likely_phishing",
  "confidence": "high",
  "evidence": [
    {
      "signal": "domain_age",
      "detail": "Domain registered 4 days ago via a privacy-shielded registrar"
    },
    {
      "signal": "redirect_chain",
      "detail": "Link hops through 2 shorteners before landing on a page not affiliated with the claimed bank"
    },
    {
      "signal": "web_search",
      "detail": "No official presence found for this domain; 3 unrelated scam-report forum threads reference the same URL pattern"
    }
  ],
  "explanation": "one paragraph, plain language, written by the agent from the evidence above",
  "investigation_steps": 4
}
```

`verdict` is one of `likely_legitimate`, `suspicious`, `likely_phishing`.

**Always show the evidence and the steps taken, never a bare score.** This is also what makes "agentic" visible in the demo — the judges are explicitly scoring whether you can show the planning/acting/adapting, not just the final answer.

---

## 8. Guidance for Claude Code

- **Bound every loop.** Hard cap the investigation at ~6–8 tool calls in code, independent of the model's own judgement — a loop that only exits when the model is "satisfied" can run forever.
- **Cost is a hard constraint.** Default to Haiku 4.5 for everything; only escalate a specific call to Sonnet if testing shows a real quality gap.
- **Tool descriptions are the interface.** The model picks tools by reading their names/descriptions/params — treat those as the highest-leverage prompt text in this codebase.
- **Keep tool results small and typed** (Pydantic). Don't return raw page dumps into the conversation — extract only what's needed (cleaned text, key metadata), or the context fills with material that has to be re-read every turn.
- **Everything in `us-east-1`.** Read credentials from `.env` via `python-dotenv`; they rotate every 12 hours — surface auth failures with a clear "re-login for fresh keys" message rather than a raw boto3 traceback.
- **The verdict is advisory, not an accusation.** Keep user-facing wording probabilistic ("signals suggest") — never assert a specific sender or domain is definitively malicious.
- Log every Bedrock call's token usage through `scripts/cost_report.py` so running spend is visible.
