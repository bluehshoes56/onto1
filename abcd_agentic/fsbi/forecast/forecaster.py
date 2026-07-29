"""
Forecasting layer.

Kept deliberately separate from the LLM. Predictions come from a time-series model,
never a language model guess. That separation is exactly what a risk committee wants:
the number is statistically defensible, the LLM only explains it.

This implementation is a transparent seasonal-naive-with-drift model plus a residual
based interval, so the math is fully visible in a walkthrough. Behind the same
interface, production swaps in statsforecast AutoARIMA or Prophet, or a SageMaker
endpoint, with no change to callers.

What an analyst does here: predict where the index goes next, with a stated range.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..schemas import Forecast


class Forecaster:
    model_name = "seasonal_naive_drift"

    def predict(self, history: pd.DataFrame, sector: str, state: str, horizon_days: int = 7) -> Forecast:
        y = history["sales_index"].to_numpy(dtype=float)
        if len(y) < 14:
            point = float(y[-1]) if len(y) else 0.0
            return Forecast(sector=sector, state=state, horizon_days=horizon_days,
                            point=point, lower=point, upper=point, model=self.model_name)

        season = 7
        # drift: average change over the last 4 weeks
        drift = float(np.mean(np.diff(y[-4 * season:])))
        # seasonal-naive base: value from one season ago at the target horizon offset
        base = float(y[-season + (horizon_days % season)])
        point = base + drift * horizon_days

        # residual-based interval from in-sample seasonal-naive errors
        resid = y[season:] - y[:-season]
        sigma = float(np.std(resid)) if len(resid) else 1.0
        z = 1.28  # ~80 percent interval
        return Forecast(
            sector=sector,
            state=state,
            horizon_days=horizon_days,
            point=round(point, 2),
            lower=round(point - z * sigma, 2),
            upper=round(point + z * sigma, 2),
            model=self.model_name,
        )
