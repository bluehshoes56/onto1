"""
The agent pipeline.

This wires the seven agents into one flow. It is written as an explicit sequence of
typed steps rather than hidden framework magic, so a reviewer can read exactly what
happens and in what order. In production this same shape runs as a LangGraph graph
locally or AWS Step Functions in the cloud: each step here is a node, each arrow is an
edge. Keeping it explicit is a deliberate choice for auditability.

Flow for one signal:
    signal -> plan -> retrieve+link -> reason -> narrate -> judge -> guardrails -> forecast
"""
from __future__ import annotations

import pandas as pd

from ..config import Config
from ..data.canonical import CanonicalStore
from ..forecast.forecaster import Forecaster
from ..governance.audit import AuditLog
from ..governance.guardrails import Guardrails
from ..graph.base import build_graph
from ..graph.build import seed_domain_graph
from ..llm.base import build_llm
from ..schemas import AnalysisResult, Signal
from ..semantic.semantic import SemanticLayer
from ..agents.signal import SignalAgent
from ..agents.planner import PlannerAgent
from ..agents.retrieval import RetrievalAgent
from ..agents.reasoner import ReasonerAgent
from ..agents.narrator import NarratorAgent, JudgeAgent


class Pipeline:
    def __init__(self, cfg: Config, store: CanonicalStore | None = None):
        self.cfg = cfg
        self.audit = AuditLog()
        self.store = (store or CanonicalStore().build())
        self.semantic = SemanticLayer(self.store)

        llm = build_llm(cfg)
        graph = seed_domain_graph(build_graph(cfg))

        # instantiate the seven agents
        self.signal = SignalAgent(self.audit, cfg)
        self.planner = PlannerAgent(self.audit, llm)
        self.retrieval = RetrievalAgent(self.audit)
        self.reasoner = ReasonerAgent(self.audit, graph)
        self.narrator = NarratorAgent(self.audit, llm)
        self.judge = JudgeAgent(self.audit, llm)

        self.guardrails = Guardrails()
        self.forecaster = Forecaster()

    def detect(self) -> list[Signal]:
        return self.signal.run(metrics=self.semantic.metrics())

    def analyze(self, signal: Signal) -> AnalysisResult:
        plan = self.planner.run(signal=signal)
        evidence = self.retrieval.run(plan=plan)
        reasoning = self.reasoner.run(plan=plan, evidence=evidence)
        narrative = self.narrator.run(reasoning=reasoning)
        verdict = self.judge.run(reasoning=reasoning, narrative=narrative)

        gate = self.guardrails.check(reasoning, narrative, verdict)

        history = self.store.history(signal.sector, signal.state)
        forecast = self.forecaster.predict(history, signal.sector, signal.state, horizon_days=7)

        return AnalysisResult(
            signal=signal,
            plan=plan,
            reasoning=reasoning,
            narrative=narrative,
            forecast=forecast,
            verdict=verdict,
            shipped=gate.allowed,
        )
