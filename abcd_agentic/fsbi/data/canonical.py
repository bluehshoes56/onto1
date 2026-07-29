"""
Canonical data layer on DuckDB.

DuckDB is the free local twin of Amazon Athena. Same SQL, runs in-process, reads
Parquet directly. On AWS this exact SQL runs on Athena over Parquet in S3.

We implement the medallion pattern:
    bronze  raw generated transactions, untouched
    silver  typed, deduped, one row per date/sector/state
    gold    the granular daily index the agents consume, plus rolling stats

The rolling mean and standard deviation computed here are what the signal agent
uses to decide whether a given day is anomalous.
"""
from __future__ import annotations

import duckdb
import pandas as pd

from .generate import generate


class CanonicalStore:
    def __init__(self, db_path: str = ":memory:"):
        self.con = duckdb.connect(db_path)

    def build(self, df: pd.DataFrame | None = None) -> "CanonicalStore":
        if df is None:
            df = generate()
        self.con.register("bronze_raw", df)

        # silver: enforce types and dedupe to one row per grain
        self.con.execute(
            """
            CREATE OR REPLACE TABLE silver_sales AS
            SELECT
                CAST(date AS DATE)        AS date,
                CAST(sector AS VARCHAR)   AS sector,
                CAST(state AS VARCHAR)    AS state,
                AVG(sales_index)          AS sales_index
            FROM bronze_raw
            GROUP BY 1, 2, 3
            """
        )

        # gold: granular index with a trailing 14-day baseline per sector/state.
        # The baseline (mean + std) is the expectation the signal agent tests against.
        self.con.execute(
            """
            CREATE OR REPLACE TABLE gold_daily_index AS
            SELECT
                date, sector, state, sales_index,
                AVG(sales_index) OVER w  AS baseline_mean,
                STDDEV_SAMP(sales_index) OVER w AS baseline_std,
                COUNT(sales_index) OVER w AS baseline_n
            FROM silver_sales
            WINDOW w AS (
                PARTITION BY sector, state
                ORDER BY date
                ROWS BETWEEN 14 PRECEDING AND 1 PRECEDING
            )
            ORDER BY sector, state, date
            """
        )
        return self

    def gold(self) -> pd.DataFrame:
        return self.con.execute("SELECT * FROM gold_daily_index").df()

    def history(self, sector: str, state: str) -> pd.DataFrame:
        return self.con.execute(
            "SELECT date, sales_index FROM silver_sales "
            "WHERE sector = ? AND state = ? ORDER BY date",
            [sector, state],
        ).df()
