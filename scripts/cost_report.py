"""Sums logged Bedrock token usage into a running dollar estimate.

Reads data/usage_log.jsonl (written by backend.bedrock._log_usage). Pricing is
an approximation -- verify current rates at https://aws.amazon.com/bedrock/pricing/
before trusting this near the $20 budget cutoff.
"""

import json
from pathlib import Path

# Haiku 4.5 approx per-token USD price on Bedrock -- CONFIRM against the live pricing page.
PRICE_PER_INPUT_TOKEN = 1.00 / 1_000_000
PRICE_PER_OUTPUT_TOKEN = 5.00 / 1_000_000

USAGE_LOG = Path(__file__).resolve().parent.parent / "data" / "usage_log.jsonl"


def main() -> None:
    if not USAGE_LOG.exists():
        print(f"No usage log found at {USAGE_LOG} yet.")
        return

    total_input = total_output = calls = 0
    with USAGE_LOG.open() as f:
        for line in f:
            entry = json.loads(line)
            total_input += entry.get("inputTokens", 0)
            total_output += entry.get("outputTokens", 0)
            calls += 1

    cost = total_input * PRICE_PER_INPUT_TOKEN + total_output * PRICE_PER_OUTPUT_TOKEN
    print(f"Bedrock calls logged: {calls}")
    print(f"Input tokens:  {total_input:,}")
    print(f"Output tokens: {total_output:,}")
    print(f"Estimated cost: ${cost:.4f} (approximate -- verify against AWS Budgets)")


if __name__ == "__main__":
    main()
