"""Runs the agent against a labeled test set and reports accuracy plus the hackathon's own
agent-performance metrics (schema validation, tool-call errors, loop discipline, answer fidelity).

Needs Bedrock access configured in .env to run. Populate data/test_cases/labeled.json first --
see data/test_cases/labeled.json.example for the format. That file is gitignored since a
realistic test set needs live phishing URLs (pull fresh ones from https://phishtank.org/).
"""

import json
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from backend.agent import run_investigation  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
LABELED_PATH = ROOT / "data" / "test_cases" / "labeled.json"
REPORT_PATH = ROOT / "data" / "eval_report.json"

# both of these count as a "phishing" prediction when scoring against a "phishing" label --
# "suspicious" is a hedge, not a clean bill of health, so treating it as "legitimate" would
# understate how often the agent correctly senses something is wrong
PHISHING_VERDICTS = {"likely_phishing", "suspicious"}


def main() -> None:
    if not LABELED_PATH.exists():
        print(f"No labeled test set at {LABELED_PATH}.")
        print("Copy data/test_cases/labeled.json.example, fill in real cases, and rerun.")
        sys.exit(1)

    cases = json.loads(LABELED_PATH.read_text())
    results = []

    for case in cases:
        print(f"Investigating: {case['input'][:80]}")
        try:
            outcome = run_investigation(case["input"])
        except Exception as e:
            results.append({**case, "error": str(e)})
            continue

        verdict = outcome["verdict"]
        predicted_label = "phishing" if verdict["verdict"] in PHISHING_VERDICTS else "legitimate"
        tool_errors = sum(1 for s in outcome["steps"] if s["result"].get("error") or s["result"].get("success") is False)

        results.append(
            {
                **case,
                "predicted_verdict": verdict["verdict"],
                "predicted_label": predicted_label,
                "correct": predicted_label == case["label"],
                "confidence": verdict["confidence"],
                "investigation_steps": verdict["investigation_steps"],
                "tool_errors": tool_errors,
                "warnings": outcome.get("warnings", []),
            }
        )

    _report(results)
    REPORT_PATH.write_text(json.dumps(results, indent=2))
    print(f"\nFull per-case results written to {REPORT_PATH}")


def _report(results: list[dict]) -> None:
    scored = [r for r in results if "correct" in r]
    errored = len(results) - len(scored)

    correct = sum(r["correct"] for r in scored)
    phishing_cases = [r for r in scored if r["label"] == "phishing"]
    predicted_phishing = [r for r in scored if r["predicted_label"] == "phishing"]

    true_positives = sum(1 for r in phishing_cases if r["correct"])
    precision = true_positives / len(predicted_phishing) if predicted_phishing else 0.0
    recall = true_positives / len(phishing_cases) if phishing_cases else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0

    total_steps = sum(r["investigation_steps"] for r in scored)
    avg_steps = total_steps / len(scored) if scored else 0.0
    tool_error_rate = sum(r["tool_errors"] for r in scored) / total_steps if total_steps else 0.0
    schema_fallbacks = sum(1 for r in scored if any("validation" in w.lower() for w in r["warnings"]))

    print("\n--- Evaluation report ---")
    print(f"Cases: {len(results)} ({errored} errored before scoring)")
    print(f"Accuracy (task completion): {correct}/{len(scored)} = {correct / len(scored):.1%}" if scored else "Accuracy: n/a")
    print(f"Precision: {precision:.2f}  Recall: {recall:.2f}  F1: {f1:.2f}  (answer fidelity)")
    print(f"Avg investigation steps (loop discipline): {avg_steps:.1f} / {8} cap")
    print(f"Tool-call error rate: {tool_error_rate:.1%}")
    print(f"Schema-validation fallbacks: {schema_fallbacks}/{len(scored)}")


if __name__ == "__main__":
    main()
