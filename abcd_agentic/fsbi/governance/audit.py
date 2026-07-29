"""
Audit log. The local stand-in for CloudTrail plus agent-level tracing.

Every agent run appends an immutable, timestamped record. Together with the typed
handoffs this gives a full, reconstructable trail of how a given explanation was
produced: which agent ran, when, and what it emitted. On AWS this ships to CloudTrail
and CloudWatch. Here it is an append-only in-memory log with an export.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone


@dataclass
class AuditEntry:
    agent: str
    summary: str
    ts: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class AuditLog:
    def __init__(self):
        self._entries: list[AuditEntry] = []

    def record(self, agent: str, summary: str) -> None:
        self._entries.append(AuditEntry(agent=agent, summary=summary))

    def entries(self) -> list[AuditEntry]:
        return list(self._entries)

    def export(self) -> str:
        return json.dumps([asdict(e) for e in self._entries], indent=2)
