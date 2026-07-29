# FSBI Multi-Agent Agentic AI Platform (vertical slice)

A runnable, production-shaped implementation of the FSBI analytics pipeline. Seven
specialized LLM-orchestrated agents detect a data signal, plan an investigation,
retrieve and link evidence, reason over a causal knowledge graph, explain the result,
verify the explanation, and forecast the next move, all inside governance guardrails.

The whole thing runs on a laptop at zero cost with a deterministic mock model and an
in-memory graph. Every layer sits behind an interface, so moving to AWS is a config
flip, not a rewrite.

## Run it in 30 seconds

```
pip install -r requirements.txt
python scripts/run_slice.py      # full end-to-end walkthrough, stage by stage
python scripts/ralph_build.py    # the build-time Ralph loop and eval gate
python -m pytest -q              # the six gate tests
```

No Docker, no API keys, no network needed for the above.

## The scenario the agents solve

The synthetic data plants one true causal story. A hurricane hits Florida on
2025-09-18 and Building Materials sales in FL spike. The agents do not know this. They
must detect the spike, find the hurricane news, link it to the right sector and state,
reason the causal chain, explain it with citations, and forecast the recovery. Because
we know the ground truth, the eval harness grades them objectively.

Two unrelated Building Materials signals in other states are also present. The system
correctly refuses to ship an explanation for those, because no evidence grounds them.
That refuse-to-ship-ungrounded behavior is the core safety property.

## The seven agents and where each lives

| Step | Agent | File | What it does |
| ---- | ----- | ---- | ------------ |
| 1 | Signal detection | `fsbi/agents/signal.py` | Statistical z-score trigger on the metric table. Deterministic, not LLM. |
| 2 | Planning | `fsbi/agents/planner.py` | Cheap-tier LLM picks the investigation path. |
| 3+4 | Retrieval + entity linking | `fsbi/agents/retrieval.py` | Finds dated evidence, maps it to sector and state. |
| 5 | Reasoning | `fsbi/agents/reasoner.py` | Traverses the knowledge graph into a causal chain. |
| 6 | Narrative | `fsbi/agents/narrator.py` | Cheap-tier LLM drafts the explanation with citations. |
| 7 | Judge | `fsbi/agents/narrator.py` | Expensive-tier LLM verifies every claim maps to evidence. |

## How the code maps to the build steps

| Build step | Code |
| ---------- | ---- |
| Canonical + granular data (medallion) | `fsbi/data/canonical.py`, `fsbi/data/generate.py` |
| Semantic layer (dbt) | `fsbi/semantic/fsbi_metrics.sql`, `fsbi/semantic/semantic.py` |
| Knowledge graph (Neo4j) | `fsbi/graph/` (interface, networkx stand-in, Neo4j impl, builder) |
| Agent architecture (7 agents) | `fsbi/agents/` |
| LLM tiering (draft + judge) | `fsbi/llm/` (interface, mock, ollama, bedrock) |
| Forecasting layer | `fsbi/forecast/forecaster.py` |
| Governance and guardrails | `fsbi/governance/` (audit, guardrails) |
| Evaluation harness | `fsbi/eval/` (metrics, harness) |
| Orchestration | `fsbi/orchestration/pipeline.py` |
| Ralph runtime loop (step 17) | `fsbi/orchestration/ralph_runtime.py` |
| Ralph build loop | `scripts/ralph_build.py`, `tests/test_pipeline.py` |

## The two Ralph loops

Build-time. `scripts/ralph_build.py` and the pytest gate evaluate the pipeline against
the known scenario and pass only when faithfulness, grounding, forecast error, and
trigger recall all clear their thresholds. During development the agent edits code and
prompts and reruns this until green. In CI a red gate blocks the deploy.

Runtime. `fsbi/orchestration/ralph_runtime.py` is step 17. It loops over the signal
queue each cycle: detect, plan, execute, judge, ship what passes, hold what does not,
and feed judge outcomes back to bias future planning. Fresh context each cycle avoids
drift.

## The single flip to AWS

Nothing in the application code names a vendor. `fsbi/config.py` reads two variables:

```
LLM_BACKEND    mock  ->  ollama   ->  bedrock
GRAPH_BACKEND  networkx        ->    neo4j
```

Set them and the same code runs against real models and a real graph. The AWS mapping:

| Layer | Local stand-in | AWS |
| ----- | -------------- | --- |
| Query | DuckDB | Athena over Parquet in S3 |
| Semantic | dbt-duckdb | dbt Core on ECS |
| Graph | Neo4j Community / networkx | Neptune |
| Retrieval | pgvector / in-memory | OpenSearch Serverless or Bedrock Knowledge Bases |
| LLM | Ollama two-tier | Bedrock Claude Haiku + Sonnet |
| Orchestration | explicit sequence / LangGraph | Step Functions |
| Forecast | seasonal-naive-drift | SageMaker or Lambda |
| Guardrails | policy check | Bedrock Guardrails |
| Audit | append-only log | CloudTrail + CloudWatch |
| Ralph runtime | Prefect / bounded loop | EventBridge Scheduler + Step Functions |

`docker-compose.yml` brings up Neo4j, Postgres with pgvector, Ollama, and LocalStack so
every production path can be exercised locally before any cloud spend.

## Why the design is shaped this way

Typed handoffs (`fsbi/schemas.py`) make each agent a contract, so a bad output fails
loudly at its agent instead of corrupting downstream steps. Specialization makes each
agent auditable and independently upgradable. Draft-and-judge tiering is the cost lever:
the expensive model runs only on verification. The forecast is statistical and separate
from the LLM, so the number is defensible to a risk committee. Guardrails and the judge
gate live outside the model, so safety cannot be prompted away.

## Files at a glance

```
fsbi/
  config.py            the single flip between local and AWS
  schemas.py           typed agent handoff contracts
  data/                synthetic feed, DuckDB medallion layers, news corpus
  semantic/            dbt-style metric definitions
  graph/               knowledge graph interface + networkx + neo4j + builder
  llm/                 LLM interface + mock + ollama + bedrock
  agents/              the seven agents
  forecast/            time-series forecaster
  governance/          audit log + guardrails
  orchestration/       pipeline + runtime Ralph loop
  eval/                metrics + eval harness (build-time gate)
scripts/
  run_slice.py         end-to-end walkthrough
  ralph_build.py       build-time Ralph loop
tests/
  test_pipeline.py     the six gate tests
docs/
  architecture.md      one-page diagram + local-to-AWS map
  walkthrough_script.md the words to say while running the demo
```
