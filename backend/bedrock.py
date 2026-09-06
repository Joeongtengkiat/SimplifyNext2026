import json
import os
from datetime import datetime, timezone
from pathlib import Path

import boto3
from botocore.config import Config

# verified 2026-09 against this account's list_inference_profiles -- the id is missing the
# "-20251001" release-date segment without it, which Bedrock rejects with ValidationException
MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "us.anthropic.claude-haiku-4-5-20251001-v1:0")
REGION = os.environ.get("AWS_REGION", "us-east-1")

USAGE_LOG = Path(__file__).resolve().parent.parent / "data" / "usage_log.jsonl"


def get_client():
    # explicit bounds -- botocore's defaults (60s connect, 60s read, 3 retries) can chain into a
    # multi-minute hang on a stuck connection, which is indistinguishable from the app "freezing"
    # to whoever's watching the spinner. This still allows a genuinely slow multi-tool-call turn
    # to finish, just not an unbounded one.
    config = Config(retries={"max_attempts": 2}, connect_timeout=10, read_timeout=45)
    return boto3.client("bedrock-runtime", region_name=REGION, config=config)


def converse(
    client,
    messages: list[dict],
    system: str,
    tool_config: dict | None = None,
    tool_choice: dict | None = None,
    model_id: str | None = None,
) -> dict:
    resolved_model = model_id or MODEL_ID
    kwargs = {
        "modelId": resolved_model,
        "messages": messages,
        "system": [{"text": system}],
    }
    if tool_config:
        cfg = dict(tool_config)
        if tool_choice:
            cfg["toolChoice"] = tool_choice
        kwargs["toolConfig"] = cfg

    response = client.converse(**kwargs)
    _log_usage(response.get("usage", {}), resolved_model)
    return response


def _log_usage(usage: dict, model_id: str) -> None:
    if not usage:
        return
    USAGE_LOG.parent.mkdir(parents=True, exist_ok=True)
    entry = {"timestamp": datetime.now(timezone.utc).isoformat(), "model": model_id, **usage}
    with USAGE_LOG.open("a") as f:
        f.write(json.dumps(entry) + "\n")
