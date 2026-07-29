# Interview Walkthrough Script

The words to say while running the demo. Each block is one stage of
`python scripts/run_slice.py`. Keep it to the point. Let the output carry the story.

## Opening (30 seconds)

"This is a production-shaped version of the FSBI multi-agent platform. Seven
specialized agents turn a raw data signal into a defensible, forecasted explanation,
inside governance guardrails. It runs end to end on this laptop at zero cost, with a
deterministic mock model standing in for the LLM. Every layer sits behind an interface,
so the move to AWS is a config flip, not a rewrite. Let me run it."

Run `python scripts/run_slice.py`.

## Stage 1, signal detection

"The pipeline starts with detection, and detection is deliberately statistical, not an
LLM. It scans the governed metric table for a daily move that breaks the trailing
baseline. Here the top signal is Building Materials in Florida on September 18, almost
15 sigma above baseline. The LLM enters later to explain the move. It never detects it.
Cheap, deterministic, explainable."

## Stage 2, planning

"The first LLM step is planning. Different signals need different investigations. A
calendar bump wants a seasonal check. A sharp unexplained spike wants a news
investigation. The planner reads the signal and routes it. It chose news-driven here,
because a 15 sigma move is far outside any seasonal range. This runs on the cheap tier."

## Stages 3 and 4, retrieval and entity linking

"Now the system grounds itself in evidence. Retrieval finds dated articles in the right
window. Entity linking maps each one to a sector and a state, so the evidence is tied to
structured entities, not just loosely relevant text. It found the hurricane landfall
story and the follow-up on supply shortages, both linked to Building Materials in
Florida. In production this is vector search over pgvector or OpenSearch."

## Stage 5, reasoning

"This is the step a flat search cannot do. The reasoning agent traverses the knowledge
graph from the hurricane event to the sector index. Hurricane drives demand for building
materials, which lifts the sales index, which raises the FSBI reading. Three connected
hops, each with a confidence and a cause-versus-association label. Labeling matters,
because overstating causality is the fastest way to lose a risk committee."

## Stage 6, narrative

"The narrative agent turns that structured chain into an analyst-ready explanation and
cites the evidence per claim. Note it only asserts links it can cite. If it cannot
ground a claim, it does not make it."

## Stage 7, judge

"Then the judge verifies. This is the expensive tier, and it runs only here, on
verification. Every claim in the narrative must map to real evidence. Faithfulness and
grounding both come back at 1.0, so it approves. That draft-then-judge split is two
things at once: the guard against hallucination, and the cost lever, because the
premium model touches only the verification step."

## Guardrails and forecast

"A guardrail gate outside the model makes the final ship decision. Safety cannot be
prompted away, because the decision does not live in the prompt. Separately, the
forecast comes from a time-series model, never the LLM. The number is statistically
defensible. The LLM only explains it."

## The runtime Ralph loop

"Now watch what happens across the whole signal queue. The system ships the hurricane
explanation, and it holds the two unrelated Building Materials signals in other states.
It holds them because no evidence grounds them. That refuse-to-ship-ungrounded behavior
is the core safety property. An enterprise agent system cannot run once, so this loops:
detect, plan, execute, judge, ship what passes, and feed judge outcomes back to bias
future planning. Fresh context each cycle avoids drift. This is step 17, the operating
model."

## The audit trail

"Every agent run is logged, immutable and timestamped. Combined with the typed handoffs
between agents, that gives a full reconstructable record of how any explanation was
produced. On AWS this ships to CloudTrail and CloudWatch."

## The build-time Ralph loop (optional second run)

Run `python scripts/ralph_build.py` or `python -m pytest -q`.

"There are two Ralph loops. That was the runtime one. This is the build-time one. It
scores the pipeline against a known planted scenario and passes only when faithfulness,
grounding, forecast error, and trigger recall all clear their thresholds. During
development the agent edits code and prompts and reruns this until green. In CI a red
gate blocks the deploy. That is how the system reaches accuracy before it ever ships."

## Anticipated questions and crisp answers

Q: Why multi-agent and not one large prompt?
A: One prompt doing everything is unreliable and impossible to govern. Specialized
agents isolate failure to one step, make each step auditable, and let me upgrade one
agent without touching the rest. The typed handoff between agents is a contract, so a
bad output fails loudly at its agent instead of corrupting the next one.

Q: How do you stop it hallucinating?
A: Three layers. Retrieval forces reasoning over evidence. The judge verifies every
citation maps to source before approval. A guardrail gate outside the model makes the
final call. And the forecast is a time-series model, so the number is never an LLM
guess.

Q: How do you control cost at scale?
A: Draft-and-judge tiering. A cheap fast model handles the high-volume steps. The
premium model runs only on verification. Serverless compute means I pay per run, not for
idle capacity.

Q: How is this safe for a regulated fintech?
A: Least privilege per agent through scoped roles. An immutable audit trail. Guardrails
that live outside the model. And an eval harness that proves quality on every change
rather than asserting it.

Q: Why do you trust the migration to AWS?
A: The whole architecture is proven locally against the same interfaces first. Same
code, same handoffs. Promotion is two environment variables. Terraform plan prints the
exact cloud footprint before a dollar is spent.

Q: What would you build next on this?
A: A second index or vertical reusing the same architecture, near-real-time streaming
ingestion in place of batch, and a formal causal-inference layer so the graph reasons
over cause rather than correlation.

## Closing

"That is the full pipeline. Detection, planning, grounded retrieval, causal reasoning,
verified explanation, statistical forecast, guardrails, and audit, running in a
self-correcting loop. Built local-first at zero cost, one flip from AWS."
