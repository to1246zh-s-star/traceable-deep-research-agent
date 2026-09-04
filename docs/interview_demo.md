# Interview Demo Guide

This guide uses a PostgreSQL-versus-MongoDB architecture decision to show the
project in three to five minutes. Adapt the pacing to the interviewer rather
than reading it as a script.

## Canonical Prompt

> We are designing a multi-tenant B2B SaaS platform and need to choose
> PostgreSQL or MongoDB as the primary database. Orders, billing, and
> authorization require strong transaction consistency and complex queries.
> The team mainly knows PostgreSQL, but future data volume and concurrency make
> horizontal scaling relevant. Use reliable evidence, distinguish hard
> constraints from criteria and unknowns, and explain what changes could alter
> the outcome. Do not force a recommendation when evidence is insufficient.

## Before the Interview

1. Configure one working LLM and search provider in `backend/.env`.
2. Start the backend and frontend using the README quick start, or run
   `docker compose up --build`.
3. Confirm `/healthz` and `/readyz`.
4. Run the canonical prompt once if live provider latency would distract from
   the interview. Keep its `research_id` for replay.
5. Open the streaming UI and the replay endpoint in separate tabs.

## 3–5 Minute Walkthrough

### Minute 0–1: Position the project

Describe it as a traceable technical research and decision Agent, not a chat
wrapper. Point to the README architecture diagram and the authoritative
`SummaryState`. The LLM proposes or interprets bounded outputs, while explicit
services own tool execution, evidence state, budgets, scoring boundaries,
stopping, and persistence.

### Minute 1–2: Planning and tool runtime

Submit or open the canonical database prompt. Show focused TODOs and one tool
event. Explain that web search, MCP, and local integrations share the same
`ToolRegistry`/`ToolInvocation`/`ToolResult` boundary. A successful call yields
an observation; it does not become decision truth merely because a provider
returned it.

### Minute 2–3: Evidence and adaptive research

Show evidence IDs, claims, source metadata, and decision criteria/constraints.
Then show research gaps or the stopping explanation. The conditional loop is
deterministic: it continues only for actionable gaps while budget and stopping
rules permit. Missing information remains `UNKNOWN`, and an unresolved hard
constraint is not treated as satisfied or violated.

### Minute 3–4: Replay and re-evaluation

Open:

```text
GET /research/{research_id}/replay
GET /research/{research_id}/lineage
GET /research/{research_id}/versions
```

Point out that replay reads persisted state and does not call providers. For
re-evaluation, supply a realistic new fact such as “the managed PostgreSQL
service now supports the required tenant-isolation control.” The API prepares
eligibility deterministically and persists executed work as a child version;
the historical state remains immutable.

### Minute 4–5: Production engineering

Close with the engineering surfaces that are usually absent from a prototype:

- deterministic evaluation and regression handling;
- context selection, budgeting, and observable compression;
- provider-level usage accounting and explicit trusted pricing;
- wall-clock latency and sanitized runtime/tool traces;
- circuit breaking and graceful degradation;
- optional LangGraph interoperability;
- SQLite persistence, health/readiness, Dockerfiles, nginx, and Compose.

Avoid claiming benchmark superiority. The point is inspectability, conservative
semantics, and reproducible orchestration.

## What to Show

- Planner output: complementary research tasks.
- Tool runtime: invocation/result status and sanitized trace.
- State: evidence, claims, candidates, criteria, constraints, and provenance.
- Adaptation: research gaps, budget usage, and stopping reason.
- Decision artifact: readiness and definitive-versus-provisional wording.
- Replay: task/event timeline without provider calls.
- Re-evaluation: immutable parent plus a new lineage version.
- Operations: `/healthz`, `/readyz`, runtime efficiency, and Compose topology.

## Common Interview Questions

### Why not just use ChatGPT Deep Research?

This project is an engineering artifact for inspecting and controlling the
research process. It exposes state, evidence, tool boundaries, deterministic
stopping, replay, evaluation, and versioning. It does not claim to outperform
general-purpose hosted research products.

### Why not use LangGraph from the start?

The custom runtime was built to understand orchestration mechanics directly
and now owns project-specific state, budgets, replay, resilience, and decision
semantics. The optional LangGraph adapter shows that these boundaries map to
State, Nodes, Conditional Edges, and Checkpoints without making the framework a
second source of truth.

### Why build a custom runtime?

It makes lifecycle, failure, persistence, and semantic boundaries explicit.
That was a learning and design choice, not a claim that custom orchestration is
universally preferable. A team can reuse the adapter when LangGraph is the
standard integration surface.

### What happens when search succeeds but summarization fails?

Retrieved observations and persistent evidence are not erased. The failure is
recorded, optional downstream work degrades, and the LLM circuit prevents
repeated failing calls where appropriate. Missing summaries or semantics remain
unknown rather than becoming invented conclusions.

### How do you avoid hallucinated decisions?

The LLM is not the final scoring authority. Evidence, candidate/criterion
links, hard constraints, readiness, gaps, and stopping pass through explicit
conservative services. No evidence is not a bad score, and unresolved is not
false.

### How do you handle context limits?

Each invocation receives selected named sections. A deterministic estimator
applies an input budget, then optional oversized sections can be compressed at
semantic boundaries to the actual remaining capacity. Compression is traced,
execution-only, and never replaces stored evidence.

### How do you measure Agent quality?

The evaluation harness uses deterministic fixtures and metrics for planning,
coverage, evidence/citation quality, unsupported claims, recovery, budgets,
latency, and usage. Unknown metrics remain unknown rather than becoming false
regressions.

### How do you estimate LLM cost?

Usage is accepted only from provider metadata. Cost is populated only when all
calls have complete prompt/completion counts and an exact provider/model rule
exists in the explicit trusted pricing registry. Otherwise cost is `None`.

### How is state persisted?

SQLite persists the original `SummaryState` and related evidence, claims,
traces, decisions, and lineage. Compose mounts `/data` as a named volume.
Replay reads this state; re-evaluation creates a child version instead of
mutating history.

### What makes this production-oriented?

The project includes bounded orchestration, fault isolation, persistent state,
replay/versioning, context controls, evaluation, sanitized observability,
provider preflight, configuration readiness, secret hygiene, locked
dependencies, production frontend/backend images, health checks, and persistent
deployment storage.

## Visual Capture TODO

No fake screenshots are included. A future capture should contain:

1. the streaming task/tool view;
2. evidence and replay details;
3. the decision artifact and lineage view.
