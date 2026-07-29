-- Semantic model (dbt style).
--
-- This is the single source of truth for what a metric means. Every agent that
-- needs "growth" or "the index" reads this definition, so no two agents compute
-- the same number two different ways. In production this is a dbt model compiled
-- against Athena or Redshift. Locally the same SQL runs on DuckDB via dbt-duckdb.
--
-- Metric definitions:
--   sales_index         : the granular daily index level
--   day_over_day_growth : percentage change vs the prior day
--   z_score             : standardized deviation from the trailing 14-day baseline
--                         (this is the definition the signal agent depends on)

SELECT
    date,
    sector,
    state,
    sales_index,
    baseline_mean,
    baseline_std,
    baseline_n,
    (sales_index - LAG(sales_index) OVER (PARTITION BY sector, state ORDER BY date))
        / NULLIF(LAG(sales_index) OVER (PARTITION BY sector, state ORDER BY date), 0)
        AS day_over_day_growth,
    (sales_index - baseline_mean) / NULLIF(baseline_std, 0) AS z_score
FROM gold_daily_index
