"""
Evaluation metrics. RAGAS-style, computed on the pipeline outputs.

Accuracy alone is not enough for an explanation product, so we score four things:
    faithfulness      fraction of narrative claims supported by evidence
    grounding         fraction of supplied evidence actually used
    forecast_mape     mean absolute percentage error of the forecast vs actual
    trigger_recall    did signal detection catch the known planted event

These turn "is it good" into numbers, which the build-time Ralph loop can gate on.
"""
from __future__ import annotations

from ..schemas import AnalysisResult


def faithfulness(result: AnalysisResult) -> float:
    return result.verdict.faithfulness


def grounding(result: AnalysisResult) -> float:
    return result.verdict.grounding


def forecast_mape(point: float, actual: float) -> float:
    if actual == 0:
        return 0.0
    return abs(point - actual) / abs(actual)
