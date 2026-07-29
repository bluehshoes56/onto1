"""
Knowledge graph interface.

The graph is what turns isolated facts into a causal chain. A flat vector search can
tell you a hurricane article is relevant. Only a graph can traverse
hurricane -> building materials demand -> sector index up as connected hops with
confidence and a cause-versus-association label on each edge.

Two implementations behind this interface: networkx locally, Neo4j or Neptune in
production. The reasoning agent depends only on the interface.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from ..config import Config
from ..schemas import CausalLink


class KnowledgeGraph(ABC):
    @abstractmethod
    def add_edge(self, source: str, relation: str, target: str, confidence: float, kind: str) -> None:
        ...

    @abstractmethod
    def paths_from(self, start: str, max_hops: int = 3) -> list[list[CausalLink]]:
        """Return causal chains starting at a node, each a list of hops."""


def build_graph(cfg: Config) -> KnowledgeGraph:
    if cfg.graph_backend == "networkx":
        from .networkx_graph import NetworkxGraph
        return NetworkxGraph()
    if cfg.graph_backend == "neo4j":
        from .neo4j_graph import Neo4jGraph
        return Neo4jGraph(cfg)
    raise ValueError(f"unknown GRAPH_BACKEND: {cfg.graph_backend}")
