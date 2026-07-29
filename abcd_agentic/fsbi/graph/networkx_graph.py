"""
Networkx knowledge graph. Local, in-memory, zero cost.

Mirrors the traversal behavior of Neo4j so the reasoning agent code is identical
whichever backend is configured. Uses a directed multigraph so multiple typed
relations can connect the same pair of nodes.
"""
from __future__ import annotations

import networkx as nx

from ..schemas import CausalLink


class NetworkxGraph:
    def __init__(self):
        self.g = nx.MultiDiGraph()

    def add_edge(self, source: str, relation: str, target: str, confidence: float, kind: str) -> None:
        self.g.add_edge(source, target, relation=relation, confidence=confidence, kind=kind)

    def paths_from(self, start: str, max_hops: int = 3) -> list[list[CausalLink]]:
        if start not in self.g:
            return []
        chains: list[list[CausalLink]] = []

        def walk(node: str, acc: list[CausalLink], depth: int):
            if depth >= max_hops:
                if acc:
                    chains.append(list(acc))
                return
            out = list(self.g.out_edges(node, keys=True, data=True))
            if not out and acc:
                chains.append(list(acc))
                return
            for _, tgt, _, data in out:
                link = CausalLink(
                    source=node,
                    relation=data["relation"],
                    target=tgt,
                    confidence=data["confidence"],
                    kind=data["kind"],
                )
                walk(tgt, acc + [link], depth + 1)

        walk(start, [], 0)
        # longest, highest-confidence chains first
        chains.sort(key=lambda c: (len(c), sum(l.confidence for l in c)), reverse=True)
        return chains
