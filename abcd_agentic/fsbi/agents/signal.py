"""
Agent 1: Signal detection.

The first step of the pipeline. Nothing downstream runs without a trigger. It scans
the governed metric table for daily moves whose z-score exceeds the threshold. This
is deliberately statistical, not LLM based: the trigger must be cheap, deterministic,
and explainable. The LLM enters later, to explain, not to detect.

What an analyst does here: watch the index for a move that breaks the recent range.
"""
from __future__ import annotations

import pandas as pd

from ..config import Config
from ..schemas import Signal
from .base import Agent


class SignalAgent(Agent):
    name = "signal_detection"

    def __init__(self, audit, cfg: Config):
        super().__init__(audit)
        self.cfg = cfg

    def _run(self, metrics: pd.DataFrame, **_) -> list[Signal]:
        df = metrics.dropna(subset=["z_score", "baseline_mean"]).copy()
        # require a fully warmed baseline to avoid start-of-window false positives
        df = df[df["baseline_n"] >= 14]
        hits = df[df["z_score"].abs() >= self.cfg.signal_z_threshold]
        signals: list[Signal] = []
        for _, r in hits.iterrows():
            signals.append(
                Signal(
                    sector=r["sector"],
                    state=r["state"],
                    as_of=pd.to_datetime(r["date"]).date(),
                    observed=float(r["sales_index"]),
                    expected=float(r["baseline_mean"]),
                    z_score=float(r["z_score"]),
                    direction="up" if r["z_score"] > 0 else "down",
                )
            )
        signals.sort(key=lambda s: abs(s.z_score), reverse=True)
        return signals
