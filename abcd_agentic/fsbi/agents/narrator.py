"""
Agents 6 and 7: Narrative and judge.

The narrator (cheap tier) turns the structured causal chain into an analyst-ready
explanation, citing evidence doc ids per claim. The judge (expensive tier) audits that
explanation: every claim must map to real evidence, or the explanation is rejected.
This draft-then-judge split is both the quality guard against hallucination and the
cost lever, since the expensive model runs only on verification.

What an analyst does here: write the explanation, then have it checked before it ships.
"""
from __future__ import annotations

import json

from ..llm.base import LLMClient
from ..schemas import JudgeVerdict, Narrative, Reasoning
from .base import Agent

_NARRATE_SYSTEM = (
    "You are a narrative agent. Turn a causal chain and evidence into a short, precise "
    "explanation. Do not assert any link you cannot cite. Return strict JSON with keys "
    "text and citations, where citations maps each claim to a list of evidence doc ids."
)
_JUDGE_SYSTEM = (
    "You are a judge agent. Verify that every claim in the narrative maps to supplied "
    "evidence doc ids. Return strict JSON with keys approved, faithfulness, grounding, "
    "unsupported_claims, notes."
)


class NarratorAgent(Agent):
    name = "narrative"

    def __init__(self, audit, llm: LLMClient):
        super().__init__(audit)
        self.llm = llm

    def _run(self, reasoning: Reasoning, **_) -> Narrative:
        signal = reasoning.signal
        user = json.dumps(
            {
                "task": "narrate",
                "signal": {
                    "sector": signal.sector,
                    "state": signal.state,
                    "as_of": str(signal.as_of),
                    "direction": signal.direction,
                    "magnitude_pct": signal.magnitude_pct,
                },
                "chain": reasoning.as_claims(),
                "evidence": [
                    {
                        "doc_id": e.doc_id,
                        "headline": e.headline,
                        "linked_sector": e.linked_sector,
                        "linked_state": e.linked_state,
                    }
                    for e in reasoning.supporting_evidence
                ],
            }
        )
        out = json.loads(self.llm.draft(_NARRATE_SYSTEM, user))
        return Narrative(signal=signal, text=out["text"], citations=out.get("citations", {}))


class JudgeAgent(Agent):
    name = "judge"

    def __init__(self, audit, llm: LLMClient):
        super().__init__(audit)
        self.llm = llm

    def _run(self, reasoning: Reasoning, narrative: Narrative, **_) -> JudgeVerdict:
        user = json.dumps(
            {
                "task": "judge",
                "claims": reasoning.as_claims(),
                "citations": narrative.citations,
                "evidence_ids": [e.doc_id for e in reasoning.supporting_evidence],
            }
        )
        out = json.loads(self.llm.judge(_JUDGE_SYSTEM, user))
        return JudgeVerdict(**out)
