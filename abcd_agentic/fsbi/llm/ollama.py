"""
Ollama implementation. Local models, no cost, data never leaves the machine.

This is the free stand-in for Bedrock. Same draft/judge interface. Requires an
Ollama server running locally (docker compose brings one up). Kept import-light so
the mock path never needs the requests dependency.
"""
from __future__ import annotations

import json

from ..config import Config
from .base import LLMClient


class OllamaLLM(LLMClient):
    def __init__(self, cfg: Config):
        self.cfg = cfg
        import requests  # imported lazily so mock runs need no extra deps
        self._requests = requests

    def _call(self, model: str, system: str, user: str) -> str:
        resp = self._requests.post(
            f"{self.cfg.ollama_host}/api/chat",
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "format": "json",
                "stream": False,
                "options": {"temperature": 0},
            },
            timeout=120,
        )
        resp.raise_for_status()
        return resp.json()["message"]["content"]

    def draft(self, system: str, user: str) -> str:
        return self._call(self.cfg.draft_model, system, user)

    def judge(self, system: str, user: str) -> str:
        return self._call(self.cfg.judge_model, system, user)
