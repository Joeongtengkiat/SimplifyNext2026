import json
import os
from datetime import datetime, timezone
from pathlib import Path

import boto3
from botocore.config import Config

MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "us.anthropic.claude-haiku-4-5-v1:0")
REGION = os.environ.get("AWS_REGION", "us-east-1")

USAGE_LOG = Path(__file__).resolve().parent.parent / "data" / "usage_log.jsonl"


def get_client():
    return boto3.client("bedrock-runtime", region_name=REGION, config=Config(retries={"max_attempts": 3}))


def converse(client, messages: list[dict], system: str, tool_config: dict | None = None) -> dict:
    kwargs = {
        "modelId": MODEL_ID,
        "messages": messages,
        "system": [{"text": system}],
    }
    if tool_config:
        kwargs["toolConfig"] = tool_config

    response = client.converse(**kwargs)
    _log_usage(response.get("usage", {}))
    return response


def _log_usage(usage: dict) -> None:
    if not usage:
        return
    USAGE_LOG.parent.mkdir(parents=True, exist_ok=True)
    entry = {"timestamp": datetime.now(timezone.utc).isoformat(), "model": MODEL_ID, **usage}
    with USAGE_LOG.open("a") as f:
        f.write(json.dumps(entry) + "\n")
