"""
Agents 3 and 4: Retrieval and entity linking.

Retrieval finds candidate evidence in the right time window. Entity linking maps each
hit to a sector and state so the evidence is grounded to structured entities, not just
loosely relevant text. Recency and geography filters keep stale or off-target articles
out. In production retrieval is vector search over pgvector or OpenSearch. Here it is a
transparent keyword-plus-window match so the logic is visible in a walkthrough.

What an analyst does here: find the news that explains the move, and confirm it is
actually about this sector in this state on these dates.
"""
from __future__ import annotations

from datetime import timedelta

from ..data.news import NEWS
from ..schemas import Evidence, Plan
from .base import Agent

# minimal sector vocabulary for entity linking
_SECTOR_TERMS = {
    "Building Materials": {"building materials", "plywood", "supplies", "repair", "construction"},
    "Gas Stations": {"gas stations", "fuel", "gasoline"},
    "Apparel": {"apparel", "clothing"},
    "Restaurants": {"restaurants", "dining"},
    "Grocery": {"grocery", "food"},
}


class RetrievalAgent(Agent):
    name = "retrieval_entity_linking"

    def _run(self, plan: Plan, **_) -> list[Evidence]:
        signal = plan.signal
        lo = signal.as_of - timedelta(days=plan.lookback_days)
        hi = signal.as_of + timedelta(days=2)
        query_terms = set(plan.retrieval_query.lower().split())

        results: list[Evidence] = []
        for item in NEWS:
            # recency filter
            if not (lo <= item["published"] <= hi):
                continue
            themes = set(item["themes"])
            text = (item["headline"] + " " + item["body"]).lower()

            # relevance: query term overlap plus theme overlap
            overlap = len(query_terms & themes) + sum(1 for t in query_terms if t in text)
            if overlap == 0:
                continue

            # entity linking: which sector and state does this evidence attach to
            linked_sector = _link_sector(text)
            linked_state = signal.state if signal.state in item["regions"] else None

            results.append(
                Evidence(
                    doc_id=item["doc_id"],
                    published=item["published"],
                    headline=item["headline"],
                    snippet=item["body"][:160],
                    source=item["source"],
                    linked_sector=linked_sector,
                    linked_state=linked_state,
                    relevance=float(overlap),
                )
            )

        results.sort(key=lambda e: e.relevance, reverse=True)
        return results


def _link_sector(text: str) -> str | None:
    for sector, terms in _SECTOR_TERMS.items():
        if any(t in text for t in terms):
            return sector
    return None
