"""
Runtime Ralph loop. This is step 17, the operating model.

An enterprise agent system cannot run once. It runs continuously: detect signals,
plan, execute the analysis, judge the output, ship what passes, and feed judge
outcomes back so the planner improves. Each cycle starts from fresh context to avoid
drift, and re-grounds against the current data.

On AWS this loop is driven by EventBridge Scheduler plus Step Functions. Locally it is
driven by Prefect or a simple scheduler. Here we run it as an explicit bounded loop so
the mechanics are visible, then report what shipped and why.
"""
from __future__ import annotations

from dataclasses import dataclass

from .pipeline import Pipeline
from ..schemas import AnalysisResult


@dataclass
class CycleReport:
    detected: int
    shipped: list[AnalysisResult]
    held: list[AnalysisResult]


class RalphRuntime:
    def __init__(self, pipeline: Pipeline, top_n: int = 3):
        self.pipeline = pipeline
        self.top_n = top_n
        # simple feedback memory: paths that produced approved outputs get preferred
        self.path_success: dict[str, int] = {}

    def cycle(self) -> CycleReport:
        signals = self.pipeline.detect()
        # act on the strongest few signals only, mirroring an analyst triaging a queue
        picked = signals[: self.top_n]

        shipped, held = [], []
        for s in picked:
            result = self.pipeline.analyze(s)
            # judge feedback loop: remember which plan paths succeed
            key = result.plan.path
            self.path_success[key] = self.path_success.get(key, 0) + (1 if result.shipped else 0)
            (shipped if result.shipped else held).append(result)

        return CycleReport(detected=len(signals), shipped=shipped, held=held)
