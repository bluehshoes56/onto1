"""
Neo4j knowledge graph. Production path.

Same interface as the networkx stand-in. This is what runs against Neo4j Community
locally (docker compose) or Aura, and the same Cypher pattern ports to Amazon
Neptune via openCypher. Kept import-light so the mock and networkx paths need no
neo4j driver installed.

Walkthrough point: the reasoning agent never changes when you move from networkx to
Neo4j. Only GRAPH_BACKEND changes. The traversal semantics are preserved by the
Cypher below.
"""
from __future__ import annotations

from ..config import Config
from ..schemas import CausalLink


class Neo4jGraph:
    def __init__(self, cfg: Config):
        from neo4j import GraphDatabase  # lazy import
        self._driver = GraphDatabase.driver(
            cfg.neo4j_uri, auth=(cfg.neo4j_user, cfg.neo4j_password)
        )

    def add_edge(self, source: str, relation: str, target: str, confidence: float, kind: str) -> None:
        with self._driver.session() as s:
            s.run(
                """
                MERGE (a:Entity {name: $source})
                MERGE (b:Entity {name: $target})
                MERGE (a)-[r:CAUSES {relation: $relation}]->(b)
                SET r.confidence = $confidence, r.kind = $kind
                """,
                source=source, target=target, relation=relation,
                confidence=confidence, kind=kind,
            )

    def paths_from(self, start: str, max_hops: int = 3) -> list[list[CausalLink]]:
        cypher = f"""
            MATCH path = (a:Entity {{name: $start}})-[:CAUSES*1..{max_hops}]->(b:Entity)
            RETURN [rel IN relationships(path) |
                     {{source: startNode(rel).name, relation: rel.relation,
                       target: endNode(rel).name, confidence: rel.confidence,
                       kind: rel.kind}}] AS hops
            ORDER BY length(path) DESC
        """
        chains: list[list[CausalLink]] = []
        with self._driver.session() as s:
            for record in s.run(cypher, start=start):
                chains.append([CausalLink(**hop) for hop in record["hops"]])
        return chains

    def close(self):
        self._driver.close()
