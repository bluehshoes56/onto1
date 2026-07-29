"""
Message schemas: the typed contracts passed between agents.

Why this file matters in a walkthrough:
    A monolithic prompt that does everything is impossible to govern or debug.
    We split the work into seven agents. Each agent receives a typed object and
    returns a typed object. The handoff is a contract, not free text. If an
    agent produces a malformed output the pipeline fails loudly at that agent
    instead of silently corrupting a downstream step. This is the difference
    between a demo and a production system.
"""
from __future__ import annotations

from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, Field


class Signal(BaseModel):
    """Output of the signal-detection agent. The trigger for everything downstream."""
    sector: str
    state: str
    as_of: date
    metric: str = "daily_sales_index"
    observed: float
    expected: float
    z_score: float
    direction: Literal["up", "down"]

    @property
    def magnitude_pct(self) -> float:
        if self.expected == 0:
            return 0.0
        return (self.observed - self.expected) / self.expected


class Plan(BaseModel):
    """Output of the planning agent. Which investigation path to run for this signal."""
    signal: Signal
    path: Literal["news_driven", "seasonal", "data_quality"]
    rationale: str
    retrieval_query: str
    lookback_days: int = 7


class Evidence(BaseModel):
    """A single retrieved and entity-linked piece of evidence."""
    doc_id: str
    published: date
    headline: str
    snippet: str
    source: str
    # entity linking result
    linked_sector: Optional[str] = None
    linked_state: Optional[str] = None
    relevance: float = 0.0


class CausalLink(BaseModel):
    """One hop in a causal chain assembled by the reasoning agent from the graph."""
    source: str
    relation: str
    target: str
    confidence: float
    kind: Literal["cause", "association"]


class Reasoning(BaseModel):
    """Output of the reasoning agent. Structured causal chain, not prose yet."""
    signal: Signal
    chain: list[CausalLink]
    supporting_evidence: list[Evidence]

    def as_claims(self) -> list[str]:
        """The atomic claims a downstream narrative must not exceed."""
        return [f"{c.source} {c.relation} {c.target}" for c in self.chain]


class Narrative(BaseModel):
    """Output of the narrative agent. Analyst-ready explanation with citations."""
    signal: Signal
    text: str
    # every claim maps to the evidence doc_ids that support it
    citations: dict[str, list[str]] = Field(default_factory=dict)


class Forecast(BaseModel):
    """Output of the forecasting layer. Numeric, produced by time-series models, never the LLM."""
    sector: str
    state: str
    horizon_days: int
    point: float
    lower: float
    upper: float
    model: str


class JudgeVerdict(BaseModel):
    """Output of the judge agent. Verifies the narrative against the evidence."""
    approved: bool
    faithfulness: float
    grounding: float
    unsupported_claims: list[str] = Field(default_factory=list)
    notes: str = ""


class AnalysisResult(BaseModel):
    """The full artifact one Ralph runtime cycle produces for one signal."""
    signal: Signal
    plan: Plan
    reasoning: Reasoning
    narrative: Narrative
    forecast: Forecast
    verdict: JudgeVerdict
    shipped: bool
