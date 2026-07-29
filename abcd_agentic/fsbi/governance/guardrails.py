"""
Guardrails. The last gate before an explanation reaches a human.

Local stand-in for Bedrock Guardrails. Enforces two things independent of the model:
a grounding gate (the judge must have approved) and a content policy (no overstated
certainty language on association-only chains, no empty or malformed output). On AWS
this is Bedrock Guardrails attached at the invoke call. The point is that the safety
decision lives outside the model, so it cannot be prompted away.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..schemas import JudgeVerdict, Narrative, Reasoning


@dataclass
class GuardrailResult:
    allowed: bool
    reason: str


# words that assert hard causality; not allowed when the chain is association-only
_CAUSAL_WORDS = {"caused", "because of", "due to", "driven by"}


class Guardrails:
    def check(self, reasoning: Reasoning, narrative: Narrative, verdict: JudgeVerdict) -> GuardrailResult:
        if not narrative.text.strip():
            return GuardrailResult(False, "empty narrative")
        if not verdict.approved:
            return GuardrailResult(False, "failed judge grounding gate")

        association_only = bool(reasoning.chain) and all(
            link.kind == "association" for link in reasoning.chain
        )
        if association_only:
            text = narrative.text.lower()
            if any(w in text for w in _CAUSAL_WORDS):
                return GuardrailResult(False, "causal language on association-only chain")

        return GuardrailResult(True, "passed")
