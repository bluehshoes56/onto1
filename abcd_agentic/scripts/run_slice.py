"""
Run the full vertical slice end to end and print a readable walkthrough.

This is the script to run in front of a hiring manager. It shows, stage by stage:
the signal detected, the plan chosen, the evidence retrieved and linked, the causal
chain reasoned from the graph, the narrative drafted, the judge verdict, the guardrail
decision, the forecast, and the audit trail.

    python scripts/run_slice.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fsbi.config import load_config
from fsbi.orchestration.pipeline import Pipeline
from fsbi.orchestration.ralph_runtime import RalphRuntime


def rule(title: str) -> None:
    print("\n" + "=" * 74)
    print(title)
    print("=" * 74)


def main() -> None:
    cfg = load_config()
    rule(f"CONFIG  llm_backend={cfg.llm_backend}  graph_backend={cfg.graph_backend}")
    print(f"draft_model={cfg.draft_model}  judge_model={cfg.judge_model}")
    print(f"signal_z_threshold={cfg.signal_z_threshold}")

    pipeline = Pipeline(cfg)

    rule("STAGE 1  SIGNAL DETECTION  (statistical, deterministic)")
    signals = pipeline.detect()
    print(f"{len(signals)} signals above threshold. Top:")
    for s in signals[:5]:
        print(f"  {s.as_of}  {s.sector:<20} {s.state}  z={s.z_score:+.2f}  "
              f"{s.direction}  move={s.magnitude_pct*100:+.0f}%")

    target = signals[0]
    rule(f"ANALYZING TOP SIGNAL  {target.sector} {target.state} {target.as_of}")

    plan = pipeline.planner.run(signal=target)
    print(f"STAGE 2  PLAN         path={plan.path}")
    print(f"                      rationale={plan.rationale}")
    print(f"                      query={plan.retrieval_query!r}")

    evidence = pipeline.retrieval.run(plan=plan)
    print(f"\nSTAGE 3+4  RETRIEVAL + ENTITY LINKING  ({len(evidence)} items)")
    for e in evidence:
        print(f"  {e.doc_id}  {e.published}  rel={e.relevance:.0f}  "
              f"-> sector={e.linked_sector} state={e.linked_state}")
        print(f"           {e.headline}")

    reasoning = pipeline.reasoner.run(plan=plan, evidence=evidence)
    print(f"\nSTAGE 5  REASONING  (graph traversal, {len(reasoning.chain)} hops)")
    for link in reasoning.chain:
        print(f"  {link.source}  --[{link.relation}]-->  {link.target}  "
              f"(conf={link.confidence:.2f}, {link.kind})")

    narrative = pipeline.narrator.run(reasoning=reasoning)
    print("\nSTAGE 6  NARRATIVE  (cheap-tier draft)")
    print(f"  {narrative.text}")
    print(f"  citations: {narrative.citations}")

    verdict = pipeline.judge.run(reasoning=reasoning, narrative=narrative)
    print("\nSTAGE 7  JUDGE  (expensive-tier verification)")
    print(f"  approved={verdict.approved}  faithfulness={verdict.faithfulness}  "
          f"grounding={verdict.grounding}")
    print(f"  unsupported_claims={verdict.unsupported_claims}")

    gate = pipeline.guardrails.check(reasoning, narrative, verdict)
    print(f"\nGUARDRAILS  allowed={gate.allowed}  reason={gate.reason}")

    history = pipeline.store.history(target.sector, target.state)
    fc = pipeline.forecaster.predict(history, target.sector, target.state, 7)
    print(f"\nFORECAST  ({fc.model})  7-day {fc.sector} {fc.state}: "
          f"{fc.point}  [{fc.lower}, {fc.upper}]")

    rule("RUNTIME RALPH LOOP  (one cycle over the signal queue)")
    runtime = RalphRuntime(pipeline, top_n=3)
    report = runtime.cycle()
    print(f"detected={report.detected}  shipped={len(report.shipped)}  held={len(report.held)}")
    for r in report.shipped:
        print(f"  SHIPPED  {r.signal.sector} {r.signal.state}: {r.narrative.text[:90]}...")
    for r in report.held:
        print(f"  HELD     {r.signal.sector} {r.signal.state}: {r.verdict.notes}")
    print(f"path_success feedback: {runtime.path_success}")

    rule("AUDIT TRAIL  (CloudTrail stand-in)")
    for entry in pipeline.audit.entries():
        print(f"  {entry.ts}  {entry.agent}  -> {entry.summary}")


if __name__ == "__main__":
    main()
