"""
Synthetic FSBI transaction data.

In production this layer is fed by Fiserv transaction feeds landing in S3 through
DMS change data capture. For a local walkthrough we generate a realistic stand-in
so the whole pipeline runs with zero external data. The generator plants one clear
causal story so the seven agents have something true to discover:

    A hurricane makes landfall in Florida on 2025-09-18. Building Materials sales
    in FL spike hard for several days as residents buy plywood, generators, and
    supplies. Everything else stays on its normal seasonal path.

The agents must independently detect that spike, find the hurricane news, link it
to the right sector and state, reason the causal chain, explain it, and forecast
the recovery. We know the ground truth, so we can grade them.
"""
from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd

SECTORS = ["Building Materials", "Restaurants", "Gas Stations", "Grocery", "Apparel"]
STATES = ["FL", "GA", "TX", "NY", "CA"]

# baseline daily index level and weekly seasonality strength per sector
_BASE = {
    "Building Materials": 100.0,
    "Restaurants": 120.0,
    "Gas Stations": 90.0,
    "Grocery": 140.0,
    "Apparel": 80.0,
}
_SEASONAL_AMP = {
    "Building Materials": 4.0,
    "Restaurants": 10.0,
    "Gas Stations": 3.0,
    "Grocery": 6.0,
    "Apparel": 8.0,
}

HURRICANE_DATE = date(2025, 9, 18)
HURRICANE_STATE = "FL"
HURRICANE_SECTOR = "Building Materials"


def generate(start: date = date(2025, 7, 1), days: int = 90, seed: int = 7) -> pd.DataFrame:
    """Return a tidy daily frame: date, sector, state, sales_index."""
    rng = np.random.default_rng(seed)
    rows = []
    for i in range(days):
        d = start + timedelta(days=i)
        dow = d.weekday()
        for sector in SECTORS:
            base = _BASE[sector]
            # weekly seasonality: weekends lift restaurants and apparel, dip building materials
            seasonal = _SEASONAL_AMP[sector] * np.sin(2 * np.pi * dow / 7)
            trend = 0.03 * i  # gentle upward drift
            noise = rng.normal(0, 1.2)
            for state in STATES:
                # small stable per-state offset
                state_offset = (hash((sector, state)) % 7) - 3
                value = base + seasonal + trend + state_offset + noise

                # planted causal event: hurricane demand shock
                if sector == HURRICANE_SECTOR and state == HURRICANE_STATE:
                    delta = (d - HURRICANE_DATE).days
                    if 0 <= delta <= 5:
                        # sharp spike that decays over the week
                        value += 45.0 * np.exp(-0.5 * delta)

                rows.append(
                    {"date": d, "sector": sector, "state": state, "sales_index": round(float(value), 3)}
                )
    return pd.DataFrame(rows)


if __name__ == "__main__":
    df = generate()
    print(df.head())
    fl = df[(df.sector == HURRICANE_SECTOR) & (df.state == HURRICANE_STATE)]
    print(fl[fl.date.between(date(2025, 9, 16), date(2025, 9, 22))])
