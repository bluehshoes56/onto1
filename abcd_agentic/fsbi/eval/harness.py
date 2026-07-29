"""
Eval harness and the build-time Ralph loop.

Two jobs in this file.

1. evaluate(): run the pipeline against the known planted scenario and score it on
   faithfulness, grounding, forecast error, and trigger recall. Because the synthetic
   data has a known ground truth (the Florida hurricane spike), we can grade the agents
   objectively.

2. build_gate(): the build-time Ralph loop check. It returns pass or fail against the
   configured thresholds. In development the agent iterates on code and prompts, reruns
   this gate, and only ships when every metric clears. Wire this into pytest and CI and
   a regression blocks the deploy.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..config import Config
from ..data.generate import HURRICANE_SECTOR, HURRICANE_STATE
from ..orchestration.pipeline import Pipeline
from .metrics import forecast_mape


@dataclass
class EvalReport:
    trigger_recall: float
    faithfulness: float
    grounding: float
    forecast_mape: float
    passed: bool
    detail: str


def evaluate(cfg: Config, pipeline: Pipeline | None = None) -> EvalReport:
    pipeline = pipeline or Pipeline(cfg)

    signals = pipeline.detect()
    # trigger recall: did we catch the planted hurricane event
    caught = any(s.sector == HURRICANE_SECTOR and s.state == HURRICANE_STATE for s in signals)
    trigger_recall = 1.0 if caught else 0.0

    # analyze the planted signal specifically
    target = next(
        (s for s in signals if s.sector == HURRICANE_SECTOR and s.state == HURRICANE_STATE),
        signals[0] if signals else None,
    )
    if target is None:
        return EvalReport(0, 0, 0, 1.0, False, "no signals detected")

    result = pipeline.analyze(target)

    # forecast error vs the actual most recent value as a simple proxy for accuracy
    hist = pipeline.store.history(target.sector, target.state)
    actual = float(hist["sales_index"].iloc[-1])
    mape = forecast_mape(result.forecast.point, actual)

    passed = (
        trigger_recall >= 1.0
        and result.verdict.faithfulness >= cfg.min_faithfulness
        and result.verdict.grounding >= cfg.min_grounding
        and mape <= cfg.max_forecast_mape
    )
    detail = (
        f"caught={caught} approved={result.verdict.approved} "
        f"faith={result.verdict.faithfulness} ground={result.verdict.grounding} "
        f"mape={mape:.3f} shipped={result.shipped}"
    )
    return EvalReport(
        trigger_recall=trigger_recall,
        faithfulness=result.verdict.faithfulness,
        grounding=result.verdict.grounding,
        forecast_mape=round(mape, 3),
        passed=passed,
        detail=detail,
    )


def build_gate(cfg: Config) -> bool:
    """The build-time Ralph loop gate. True means the code may ship."""
    return evaluate(cfg).passed
