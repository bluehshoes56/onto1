"""
Bedrock implementation. AWS production path.

Draft on Claude Haiku, judge on Claude Sonnet. Same interface as mock and Ollama,
so switching to real frontier models on AWS is setting LLM_BACKEND=bedrock plus the
two model IDs. Data stays inside the AWS boundary and Guardrails can be attached at
the invoke call. Kept import-light so the mock path needs no boto3.
"""
from __future__ import annotations

import json

from ..config import Config
from .base import LLMClient


class BedrockLLM(LLMClient):
    def __init__(self, cfg: Config):
        self.cfg = cfg
        import boto3  # lazy import
        self._client = boto3.client("bedrock-runtime", region_name=cfg.aws_region)

    def _call(self, model_id: str, system: str, user: str) -> str:
        body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 1024,
            "temperature": 0,
            "system": system,
            "messages": [{"role": "user", "content": user}],
        }
        resp = self._client.invoke_model(modelId=model_id, body=json.dumps(body))
        payload = json.loads(resp["body"].read())
        return payload["content"][0]["text"]

    def draft(self, system: str, user: str) -> str:
        return self._call(self.cfg.draft_model, system, user)

    def judge(self, system: str, user: str) -> str:
        return self._call(self.cfg.judge_model, system, user)
