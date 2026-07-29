"""
LLM client interface.

Two tiers on purpose. A cheap fast model drafts high-volume steps. A stronger,
costlier model acts as judge on the one step where correctness is critical. That
split is the primary cost lever in the whole platform. The rest of the code calls
draft() or judge() and never knows or cares which vendor is behind them.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from ..config import Config


class LLMClient(ABC):
    @abstractmethod
    def draft(self, system: str, user: str) -> str:
        """Cheap tier. Used for planning and narrative drafting."""

    @abstractmethod
    def judge(self, system: str, user: str) -> str:
        """Expensive tier. Used only for verification."""


def build_llm(cfg: Config) -> LLMClient:
    if cfg.llm_backend == "mock":
        from .mock import MockLLM
        return MockLLM(cfg)
    if cfg.llm_backend == "ollama":
        from .ollama import OllamaLLM
        return OllamaLLM(cfg)
    if cfg.llm_backend == "bedrock":
        from .bedrock import BedrockLLM
        return BedrockLLM(cfg)
    raise ValueError(f"unknown LLM_BACKEND: {cfg.llm_backend}")
