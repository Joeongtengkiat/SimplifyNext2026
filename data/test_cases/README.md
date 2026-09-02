# Test cases

Copy `labeled.json.example` to `labeled.json` (gitignored -- it'll reference live malicious
URLs) and fill it in with real cases, then run `python scripts/evaluate.py` to score the agent.

Known-legitimate URLs (safe to hardcode):
- https://www.wikipedia.org
- https://www.google.com
- https://www.nus.edu.sg

Known-phishing URLs are **not** committed here. Pull fresh ones at test time from PhishTank
(https://phishtank.org/) or OpenPhish (https://openphish.com/) -- both publish recently-reported
URLs -- and paste them into your local `labeled.json` during Day 2-3 evaluation runs.
