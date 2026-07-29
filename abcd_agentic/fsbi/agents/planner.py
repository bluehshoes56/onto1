"""
Agent 2: Planning.

Different signals need different investigation paths. A calendar-driven bump wants a
seasonal check, a sharp unexplained spike wants a news investigation, a lone glitch
wants a data-quality check. Sending everything down one path wastes work and produces
wrong explanations. The planner is the first LLM step: cheap-tier model, structured
JSON out, guardrail rules in the prompt.

What an analyst does here: decide how to investigate before investigating.
"""
from __future__ import annotations

import json

from ..llm.base import LLMClient
from ..schemas import Plan, Signal
from .base import Agent

_SYSTEM = (
    "You are a planning agent for a small-business sales analytics platform. "
    "Given one anomalous signal, choose the single best investigation path and "
    "return strict JSON with keys path, rationale, retrieval_query, lookback_days. "
    "path must be one of news_driven, seasonal, data_quality."
)


class PlannerAgent(Agent):
    name = "planning"

    def __init__(self, audit, llm: LLMClient):
        super().__init__(audit)
        self.llm = llm

    def _run(self, signal: Signal, **_) -> Plan:
        user = json.dumps(
            {
                "task": "plan",
                "sector": signal.sector,
                "state": signal.state,
                "z_score": signal.z_score,
                "direction": signal.direction,
                "magnitude_pct": signal.magnitude_pct,
            }
        )
        out = json.loads(self.llm.draft(_SYSTEM, user))
        return Plan(
            signal=signal,
            path=out["path"],
            rationale=out["rationale"],
            retrieval_query=out["retrieval_query"],
            lookback_days=out.get("lookback_days", 7),
        )
