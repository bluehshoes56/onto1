"""
Build-time Ralph loop driver.

This is the loop an engineer runs during development. It evaluates the pipeline, and if
the gate fails it reports exactly which metric fell short so the next iteration knows
what to fix. In a real agentic build the coding agent reads this output, edits code or
prompts, and reruns, looping with fresh context until the gate passes.

Here we run it as a bounded loop for demonstration. The gate already passes, so it exits
on the first iteration and reports green.

    python scripts/ralph_build.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fsbi.config import load_config
from fsbi.eval.harness import evaluate

MAX_ITERS = 5


def main() -> int:
    cfg = load_config()
    for i in range(1, MAX_ITERS + 1):
        report = evaluate(cfg)
        status = "PASS" if report.passed else "FAIL"
        print(f"[ralph build] iter {i}  {status}  "
              f"faith={report.faithfulness} ground={report.grounding} "
              f"mape={report.forecast_mape} recall={report.trigger_recall}")
        if report.passed:
            print("[ralph build] gate green. code may ship.")
            return 0
        print(f"[ralph build] gate red: {report.detail}")
        print("[ralph build] an agent would edit code/prompts here, then reloop.")
    print("[ralph build] exhausted iterations without passing.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
