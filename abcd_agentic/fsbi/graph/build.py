"""
Builds the causal knowledge graph.

In production this graph is populated from structured FSBI entities plus an event
and news feed, with a schema refined alongside domain experts. Here we seed it with
the domain causal knowledge needed for the walkthrough scenario: how a storm event
propagates to a sector index.

The edges carry a confidence and a cause-versus-association label. Labeling matters:
overstating causality is the fastest way to lose a risk committee, so the reasoning
agent surfaces the label in every chain.
"""
from __future__ import annotations

from .base import KnowledgeGraph


def seed_domain_graph(g: KnowledgeGraph) -> KnowledgeGraph:
    # storm demand-shock pathway
    g.add_edge("Hurricane", "drives demand for", "Building Materials", 0.92, "cause")
    g.add_edge("Building Materials", "lifts", "Building Materials sales index", 0.88, "cause")
    g.add_edge("Building Materials sales index", "raises", "FSBI sector reading", 0.80, "cause")

    # a couple of non-causal associations the reasoner must label honestly
    g.add_edge("Hurricane", "coincides with", "Gas Stations", 0.55, "association")
    g.add_edge("Fall season", "coincides with", "Apparel", 0.50, "association")
    return g
