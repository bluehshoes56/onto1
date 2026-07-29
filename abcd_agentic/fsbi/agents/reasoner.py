"""
Agent 5: Reasoning via graph traversal.

Converts isolated facts into a connected cause-effect chain. It reads the evidence,
picks the triggering event, and traverses the knowledge graph from that event to the
sector index. Each hop carries a confidence and a cause-versus-association label so
the downstream explanation never overstates causality. This is the step a flat vector
search cannot do.

What an analyst does here: connect the dots from the event to the number, and be
honest about which links are causal and which are only correlated.
"""
from __future__ import annotations

from ..graph.base import KnowledgeGraph
from ..schemas import Evidence, Plan, Reasoning
from .base import Agent


class ReasonerAgent(Agent):
    name = "reasoning"

    def __init__(self, audit, graph: KnowledgeGraph):
        super().__init__(audit)
        self.graph = graph

    def _run(self, plan: Plan, evidence: list[Evidence], **_) -> Reasoning:
        signal = plan.signal
        # pick the triggering event from evidence themes present in the graph
        trigger = self._infer_trigger(evidence)
        chains = self.graph.paths_from(trigger, max_hops=3) if trigger else []

        # keep the strongest chain that actually reaches a sales index node
        best: list = []
        for chain in chains:
            if any("index" in link.target.lower() or "reading" in link.target.lower() for link in chain):
                best = chain
                break
        if not best and chains:
            best = chains[0]

        supporting = [e for e in evidence if e.linked_sector == signal.sector and e.linked_state == signal.state]
        return Reasoning(signal=signal, chain=best, supporting_evidence=supporting)

    @staticmethod
    def _infer_trigger(evidence: list[Evidence]) -> str | None:
        # map evidence to a known graph root entity
        for e in evidence:
            head = e.headline.lower()
            if "hurricane" in head or "storm" in head:
                return "Hurricane"
        return None
