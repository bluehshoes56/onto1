"""
Agent base.

Every agent has one job, a name, and a typed run method. The base wraps each run in
an audit log entry so the full decision trail is reconstructable, which is what makes
the system safe to run in a regulated fintech. Specialization plus typed handoffs plus
per-agent audit is the whole governance story in three lines of design.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from ..governance.audit import AuditLog


class Agent(ABC):
    name: str = "agent"

    def __init__(self, audit: AuditLog):
        self.audit = audit

    @abstractmethod
    def _run(self, *args: Any, **kwargs: Any) -> Any:
        ...

    def run(self, *args: Any, **kwargs: Any) -> Any:
        out = self._run(*args, **kwargs)
        self.audit.record(self.name, kwargs.get("audit_summary", type(out).__name__))
        return out
