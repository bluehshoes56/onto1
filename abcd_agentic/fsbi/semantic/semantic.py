"""
Applies the semantic model.

In production dbt compiles fsbi_metrics.sql and materializes it. Here we execute
the same SQL directly so the demo has no dbt dependency, while proving the pattern:
metric logic lives in one governed file, not scattered across agent code.
"""
from __future__ import annotations

import os

import pandas as pd

from ..data.canonical import CanonicalStore

_SQL_PATH = os.path.join(os.path.dirname(__file__), "fsbi_metrics.sql")


class SemanticLayer:
    def __init__(self, store: CanonicalStore):
        self.store = store
        with open(_SQL_PATH) as f:
            self._sql = f.read()

    def metrics(self) -> pd.DataFrame:
        """The governed metric table every agent reads from."""
        return self.store.con.execute(self._sql).df()
