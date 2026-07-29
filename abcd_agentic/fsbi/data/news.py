"""
Synthetic news corpus.

Stands in for the external content the retrieval agent searches. In production this
is a real news and content feed embedded into a vector store (pgvector locally,
OpenSearch on AWS). Here it is a small in-memory corpus with dated, geography-tagged
items so retrieval, recency filtering, and entity linking are all exercised.

Note the corpus contains distractors (unrelated articles) so retrieval has to
actually discriminate rather than return everything.
"""
from __future__ import annotations

from datetime import date

NEWS: list[dict] = [
    {
        "doc_id": "news-001",
        "published": date(2025, 9, 18),
        "headline": "Hurricane makes landfall on Florida Gulf Coast",
        "body": "A major hurricane came ashore in Florida on Thursday, prompting "
                "evacuations and a surge in demand for plywood, generators, and "
                "building supplies as residents prepared homes and began repairs.",
        "source": "wire",
        "regions": ["FL"],
        "themes": ["hurricane", "building materials", "storm", "supplies"],
    },
    {
        "doc_id": "news-002",
        "published": date(2025, 9, 19),
        "headline": "Home improvement stores report shortages across Florida",
        "body": "Retailers in Florida reported sharp increases in sales of "
                "construction and repair materials in the days following the storm.",
        "source": "trade",
        "regions": ["FL"],
        "themes": ["building materials", "shortage", "repair", "storm"],
    },
    {
        "doc_id": "news-100",
        "published": date(2025, 9, 10),
        "headline": "Autumn apparel lines debut at national retailers",
        "body": "Clothing chains rolled out fall collections nationwide ahead of "
                "the season with promotional pricing.",
        "source": "trade",
        "regions": ["CA", "NY", "TX"],
        "themes": ["apparel", "retail", "fall"],
    },
    {
        "doc_id": "news-101",
        "published": date(2025, 8, 2),
        "headline": "Fuel prices ease heading into late summer",
        "body": "Gasoline prices drifted lower across several states as refinery "
                "output normalized.",
        "source": "wire",
        "regions": ["TX", "GA"],
        "themes": ["gas stations", "fuel", "prices"],
    },
]
