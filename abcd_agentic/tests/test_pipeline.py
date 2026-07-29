"""
Build-time Ralph gate as tests.

These are the checks the build-time Ralph loop runs. The agent iterates on code and
prompts until every one passes. In CI a failure here blocks the deploy. That is how the
system reaches high accuracy before it ever ships.

Run: python -m pytest -q   (or python tests/test_pipeline.py)
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fsbi.config import load_config
from fsbi.data.generate import HURRICANE_SECTOR, HURRICANE_STATE
from fsbi.eval.harness import evaluate
from fsbi.orchestration.pipeline import Pipeline


def test_detects_planted_event():
    cfg = load_config()
    signals = Pipeline(cfg).detect()
    assert any(s.sector == HURRICANE_SECTOR and s.state == HURRICANE_STATE for s in signals)


def test_top_signal_is_the_hurricane():
    cfg = load_config()
    signals = Pipeline(cfg).detect()
    top = signals[0]
    assert (top.sector, top.state) == (HURRICANE_SECTOR, HURRICANE_STATE)


def test_narrative_is_grounded_and_approved():
    cfg = load_config()
    report = evaluate(cfg)
    assert report.faithfulness >= cfg.min_faithfulness
    assert report.grounding >= cfg.min_grounding


def test_ungrounded_signal_is_held_not_shipped():
    # a sector/state with no supporting evidence must not ship an explanation
    cfg = load_config()
    p = Pipeline(cfg)
    signals = p.detect()
    ungrounded = next(
        s for s in signals if not (s.sector == HURRICANE_SECTOR and s.state == HURRICANE_STATE)
    )
    result = p.analyze(ungrounded)
    assert result.shipped is False


def test_forecast_error_within_bound():
    cfg = load_config()
    report = evaluate(cfg)
    assert report.forecast_mape <= cfg.max_forecast_mape


def test_build_gate_passes():
    cfg = load_config()
    report = evaluate(cfg)
    assert report.passed, report.detail


if __name__ == "__main__":
    cfg = load_config()
    rep = evaluate(cfg)
    print("EVAL REPORT")
    print(f"  trigger_recall = {rep.trigger_recall}")
    print(f"  faithfulness   = {rep.faithfulness}")
    print(f"  grounding      = {rep.grounding}")
    print(f"  forecast_mape  = {rep.forecast_mape}")
    print(f"  PASSED         = {rep.passed}")
    print(f"  detail         = {rep.detail}")
    sys.exit(0 if rep.passed else 1)
