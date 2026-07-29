"""
Central configuration.

Everything that differs between the free local build and the AWS production
deploy is a single environment variable read here. The application code never
names a vendor directly. It asks config for an implementation. That is what
makes promotion to AWS a config change rather than a rewrite.

Walkthrough note for a reviewer:
    LLM_BACKEND   mock  -> deterministic, zero dependencies (used in this demo)
                  ollama-> local models on your machine
                  bedrock-> Claude Haiku (draft) + Claude Sonnet (judge) on AWS

    GRAPH_BACKEND networkx -> in-memory local stand-in (used in this demo)
                  neo4j    -> Neo4j Community locally or Neptune on AWS
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass
class Config:
    # ---- backend selection (the one flip) ----
    llm_backend: str = field(default_factory=lambda: os.getenv("LLM_BACKEND", "mock"))
    graph_backend: str = field(default_factory=lambda: os.getenv("GRAPH_BACKEND", "networkx"))

    # ---- LLM tiering ----
    # A cheap fast model drafts. A stronger model judges. This is the cost lever.
    draft_model: str = field(default_factory=lambda: os.getenv("DRAFT_MODEL", "mock-draft"))
    judge_model: str = field(default_factory=lambda: os.getenv("JUDGE_MODEL", "mock-judge"))

    # ---- Neo4j / Neptune connection (used only when graph_backend=neo4j) ----
    neo4j_uri: str = field(default_factory=lambda: os.getenv("NEO4J_URI", "bolt://localhost:7687"))
    neo4j_user: str = field(default_factory=lambda: os.getenv("NEO4J_USER", "neo4j"))
    neo4j_password: str = field(default_factory=lambda: os.getenv("NEO4J_PASSWORD", "password"))

    # ---- Ollama connection (used only when llm_backend=ollama) ----
    ollama_host: str = field(default_factory=lambda: os.getenv("OLLAMA_HOST", "http://localhost:11434"))

    # ---- AWS (used only when llm_backend=bedrock) ----
    aws_region: str = field(default_factory=lambda: os.getenv("AWS_REGION", "us-east-1"))

    # ---- signal detection ----
    # Absolute z-score above which a daily move is treated as a signal worth investigating.
    signal_z_threshold: float = field(default_factory=lambda: float(os.getenv("SIGNAL_Z", "2.5")))

    # ---- eval gates (the build-time Ralph loop will not pass below these) ----
    min_faithfulness: float = field(default_factory=lambda: float(os.getenv("MIN_FAITHFULNESS", "0.80")))
    min_grounding: float = field(default_factory=lambda: float(os.getenv("MIN_GROUNDING", "0.80")))
    max_forecast_mape: float = field(default_factory=lambda: float(os.getenv("MAX_FORECAST_MAPE", "0.20")))


def load_config() -> Config:
    return Config()
