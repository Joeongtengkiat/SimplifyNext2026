# Test cases

Known-legitimate URLs (safe to hardcode):
- https://www.wikipedia.org
- https://www.google.com
- https://www.nus.edu.sg

Known-phishing URLs are **not** hardcoded here since active malicious links shouldn't be
committed to a repo. Pull a fresh sample at test time from PhishTank
(https://phishtank.org/) or OpenPhish (https://openphish.com/) instead -- both publish
recently-reported URLs. Keep a private, local `phishing_samples.txt` (gitignored) for
your own testing during Day 2-3 evaluation runs.
