"""
Deterministic mock LLM.

This is what lets the entire platform run and be tested with no Ollama, no Bedrock,
no network, and no cost. It is not a toy: it parses the structured prompt payload
and returns grounded JSON so the planner, narrator, and judge behave meaningfully.
The narrator only writes claims it can tie to real evidence, and the judge really
checks claim-to-evidence coverage. That makes the eval harness scores real.

In a walkthrough this is the honest answer to "how do you test agents cheaply":
you build a deterministic stand-in behind the same interface and reserve real model
calls for staging.
"""
from __future__ import annotations

import json

from ..config import Config
from .base import LLMClient


class MockLLM(LLMClient):
    def __init__(self, cfg: Config):
        self.cfg = cfg

    def draft(self, system: str, user: str) -> str:
        payload = _parse(user)
        task = payload.get("task")
        if task == "plan":
            return self._plan(payload)
        if task == "narrate":
            return self._narrate(payload)
        return json.dumps({"error": f"unknown draft task {task}"})

    def judge(self, system: str, user: str) -> str:
        payload = _parse(user)
        return self._judge(payload)

    # ---- planning ----
    def _plan(self, p: dict) -> str:
        z = float(p["z_score"])
        direction = p["direction"]
        sector = p["sector"]
        state = p["state"]
        # A large sharp move with no calendar cause is treated as news-driven.
        if abs(z) >= 3.0:
            path = "news_driven"
            rationale = (
                f"Move of {z:.1f} sigma in {sector} {state} is far beyond seasonal "
                f"range. Investigate for an external event."
            )
        elif abs(z) >= 2.5:
            path = "seasonal"
            rationale = "Moderate deviation consistent with a calendar effect."
        else:
            path = "data_quality"
            rationale = "Small deviation. Check for a data artifact before escalating."
        query = f"{sector} {state} {'surge' if direction == 'up' else 'drop'}"
        return json.dumps(
            {"path": path, "rationale": rationale, "retrieval_query": query, "lookback_days": 7}
        )

    # ---- narrative ----
    def _narrate(self, p: dict) -> str:
        signal = p["signal"]
        chain = p["chain"]              # list of "source relation target"
        evidence = p["evidence"]        # list of {doc_id, headline, linked_sector, linked_state}

        # Build a claim -> supporting doc_ids map by matching chain entities to
        # evidence entities. The narrator refuses to assert a link it cannot cite.
        citations: dict[str, list[str]] = {}
        sentences = []
        for link in chain:
            supporting = [
                e["doc_id"] for e in evidence
                if e.get("linked_sector") == signal["sector"]
                and e.get("linked_state") == signal["state"]
            ]
            if supporting:
                citations[link] = supporting
                sentences.append(link)

        move = "rose" if signal["direction"] == "up" else "fell"
        pct = abs(float(signal["magnitude_pct"])) * 100
        lead = (
            f"{signal['sector']} in {signal['state']} {move} {pct:.0f} percent above "
            f"its trailing baseline on {signal['as_of']}."
        )
        if sentences:
            body = " The likely driver: " + "; ".join(sentences) + "."
        else:
            body = " No external driver could be grounded in evidence."
        return json.dumps({"text": lead + body, "citations": citations})

    # ---- judge ----
    def _judge(self, p: dict) -> str:
        claims = p["claims"]            # atomic claims the narrative made
        citations = p["citations"]      # claim -> [doc_ids]
        evidence_ids = set(p["evidence_ids"])

        unsupported = []
        for c in claims:
            cited = citations.get(c, [])
            if not cited or not set(cited).issubset(evidence_ids):
                unsupported.append(c)

        total = max(len(claims), 1)
        faithfulness = 1.0 - len(unsupported) / total
        grounding = len({d for ds in citations.values() for d in ds} & evidence_ids) / max(
            len(evidence_ids), 1
        )
        approved = faithfulness >= self.cfg.min_faithfulness and grounding >= self.cfg.min_grounding
        return json.dumps(
            {
                "approved": approved,
                "faithfulness": round(faithfulness, 3),
                "grounding": round(min(grounding, 1.0), 3),
                "unsupported_claims": unsupported,
                "notes": "citation coverage check complete",
            }
        )


def _parse(user: str) -> dict:
    try:
        return json.loads(user)
    except json.JSONDecodeError:
        return {}
