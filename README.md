Traceable Deep Research Agent

A traceable and evidence-grounded deep research system that plans research tasks, searches the web, tracks execution, captures structured evidence, links claims back to sources, persists complete research runs, and exposes the entire process through an interactive web interface.

Current stable release: v2.0.0

V2 focuses on making AI research traceable and grounded.
V3 is evolving the system into an Evaluated + Adaptive Technical Decision Intelligence Agent for engineering technology selection and technical due diligence.

Why This Project?

Most AI research assistants are good at producing answers.

The harder problem is:

Can we understand how the answer was produced and verify what evidence supports it?

This project treats deep research as an inspectable engineering workflow rather than a single LLM response.

Instead of:

Question
   ↓
LLM
   ↓
Answer


V2 builds:

Research Topic
      ↓
Planner
      ↓
Research Tasks
      ↓
Concurrent Search
      ↓
Structured Evidence
      ↓
Task Summaries
      ↓
Claims
      ↓
Final Report


while preserving two parallel provenance layers:

Execution Provenance

Task
 ↓
Trace
 ↓
Execution Events


and:

Content Provenance

Claim
 ↓
Evidence
 ↓
Source


This allows the system to answer two different questions:

How did the Agent perform this research?

and:

What evidence supports this conclusion?

V2 — Traceable + Evidence-Grounded Research

v2.0.0 is the current stable release.

V2 establishes the engineering foundation required for future adaptive research.

Core Capabilities
Reliable Research Planning

The Planner converts a broad research topic into focused research tasks.

Planner reliability includes:

structured JSON output;
schema validation;
malformed-output repair;
adaptive retry;
bounded recovery behavior.
Concurrent Research Execution

Independent research tasks can execute concurrently.

Each task performs:

Task
 ↓
Search Query
 ↓
Web Search
 ↓
Source Processing
 ↓
Evidence Capture
 ↓
Task Summarization


Execution concurrency is bounded to reduce provider rate-limit pressure.

Execution Trace

Every task creates an ExecutionTrace.

Conceptually:

ExecutionTrace
├── trace_id
├── task_id
├── status
├── started_at
├── finished_at
├── duration_ms
├── current_stage
├── retry_count
├── error_type
└── error_message


This makes each research task independently inspectable.

Execution Events

Task lifecycle activity is captured using structured ExecutionEvent objects.

Current lifecycle events include:

task_started
search_started
search_finished
summarization_started
task_completed
task_failed
task_skipped


Each event records:

event ID;
trace ID;
task ID;
timestamp;
execution stage;
metadata.
Trace Inspector

The frontend exposes an interactive Trace Inspector.

Users can inspect:

research ID;
task status;
trace ID;
execution duration;
retry count;
current stage;
search backend;
source count;
event timeline;
execution failures.

This forms the Execution Observability layer.

Structured Evidence

Search results are converted into structured Evidence objects.

Evidence
├── evidence_id
├── task_id
├── trace_id
├── query
├── backend
├── source_title
├── source_url
├── snippet
├── content
├── source_rank
└── created_at


Evidence therefore preserves the relationship:

Research
 ↓
Task
 ↓
Trace
 ↓
Evidence
 ↓
Source


This is different from simply storing a list of URLs.

The system retains information about:

which task produced the evidence;
which trace retrieved it;
which query produced it;
which search backend was used;
source ranking;
source snippet;
retrieved page content.
Claim–Evidence Grounding

Completed task summaries are represented as structured Claim objects.

Claim
├── claim_id
├── task_id
├── trace_id
├── text
├── evidence_ids[]
└── created_at


Current V2 grounding is task-level:

Task Summary
     ↓
Claim
     ↓
Supporting Evidence[]


This creates an explicit provenance chain:

Claim
 ↓
Evidence
 ↓
Source URL
 ↓
Trace
 ↓
Task


Atomic claim-level grounding is planned for V3.

Evidence Inspector

The frontend also exposes an Evidence Inspector.

For each Claim, users can inspect:

Claim ID;
Task ID;
Trace ID;
supporting evidence count;
evidence ID;
source rank;
search backend;
source title;
source URL;
snippet;
original search query;
retrieved content.

Evidence items can also navigate back to the corresponding execution Trace.

This forms the Evidence Grounding layer.

Persistent Research State

Research runs are persisted using SQLite.

The persistence layer is abstracted through:

ResearchStore
       ↓
SQLiteResearchStore


Current persistent entities include:

research_runs
todo_items
execution_traces
execution_events
evidence_items
claims


This means completed research can be queried after the original execution process ends.

Queryable Research APIs

V2 exposes structured APIs for inspecting stored research.

Trace APIs
GET /research/{research_id}/traces

GET /research/{research_id}/traces/{trace_id}

GET /research/{research_id}/traces/{trace_id}/events

Evidence APIs
GET /research/{research_id}/evidence

GET /research/{research_id}/evidence/{evidence_id}

Claim APIs
GET /research/{research_id}/claims

GET /research/{research_id}/claims/{claim_id}


The Claim detail endpoint resolves its supporting Evidence objects.

Real-Time Research Streaming

Research execution is streamed to the frontend using Server-Sent Events over a POST fetch stream.

The frontend streaming implementation handles:

partial network chunks;
buffered SSE blocks;
CRLF normalization;
multiple data: lines;
multiple events per network chunk;
trailing incomplete events;
explicit error events;
research persistence events.

A research run remains stream-visible while still being persisted at completion.

Source Quality Awareness

Retrieved sources are classified into deterministic source-quality tiers.

Examples include:

Source Type	Tier
Official project websites	Tier 1
Academic papers / technical reports	Tier 1
Official organization repositories	Tier 1
Authoritative technical sources	Tier 2
Blogs, forums, aggregators and unverified sources	Tier 3

Source quality information is passed into the summarization context and retained in the research output.

V3 will extend this into explicit evidence-quality and source-diversity scoring.

Safe Markdown Rendering

Generated summaries and reports are rendered through:

LLM Markdown
    ↓
marked
    ↓
DOMPurify
    ↓
Safe HTML


This allows readable Markdown output while reducing the risk of unsafe generated HTML.

System Architecture
                     User
                       │
                       ▼
                Vue 3 Frontend
                       │
                  POST /research
                  POST /research/stream
                       │
                       ▼
                FastAPI Backend
                       │
                       ▼
              DeepResearchAgent
                       │
          ┌────────────┼────────────┐
          │            │            │
          ▼            ▼            ▼
       Planner      Executor      Reporter
                        │
                        ▼
                 Research Tasks
                        │
                ┌───────┴────────┐
                ▼                ▼
             Search          Summarizer
                │
                ▼
             Evidence
                │
                ▼
              Claims
                │
                ▼
            Final Report


Observability runs alongside execution:

Task
 ↓
ExecutionTrace
 ↓
ExecutionEvent


Persistence stores:

Research State
      ↓
SQLiteResearchStore
      ↓
Trace / Event / Evidence / Claim

Technology Stack
Backend
Python
FastAPI
Uvicorn
Pydantic
SQLite
HelloAgents
OpenAI-compatible model APIs
Qwen
Tavily Search
pytest
Frontend
Vue 3
TypeScript
Vite
Fetch Streaming
Server-Sent Events
marked
DOMPurify
Development
Git
Linux
AutoDL
tmux
Project Structure
traceable-deep-research-agent/
├── backend/
│   ├── src/
│   │   ├── agents/
│   │   ├── services/
│   │   ├── tools/
│   │   ├── models.py
│   │   ├── agent.py
│   │   └── main.py
│   ├── tests/
│   ├── data/
│   └── requirements.txt
│
├── frontend/
│   ├── src/
│   │   ├── services/
│   │   └── App.vue
│   ├── package.json
│   └── vite.config.ts
│
├── docs/
│
├── README.md
└── .gitignore

Getting Started
Prerequisites

Install:

Python 3.10+
Node.js
npm
Git

You will also need credentials for the configured LLM provider and search provider.

Never commit API keys or .env files.

Backend Setup
cd backend


Create a virtual environment:

python3 -m venv .venv
source .venv/bin/activate


Install dependencies:

pip install -r requirements.txt


Configure environment variables in:

backend/.env


Example configuration depends on the selected model provider and search backend.

Do not commit this file.

Start the API:

PYTHONPATH=src .venv/bin/python -m uvicorn main:app \
  --host 0.0.0.0 \
  --port 8000


Health check:

curl http://127.0.0.1:8000/healthz


Expected response:

{
  "status": "ok"
}

Frontend Setup
cd frontend
npm install


Start development mode:

npm run dev -- --host 0.0.0.0 --port 6006


Production build:

npm run build

Testing

Run the backend test suite:

cd backend

PYTHONPATH=src .venv/bin/python -m pytest


Run the frontend production quality gate:

cd frontend

npm run build

Example Research Workflow

Example topic:

What is Retrieval-Augmented Generation?


The Planner may create tasks such as:

1. Definition and principles
2. Core technical components
3. Typical use cases
4. Main implementation frameworks
5. Performance limitations and challenges


Each task creates:

Task
 ↓
Trace
 ↓
Search
 ↓
Evidence
 ↓
Summary
 ↓
Claim


The final report combines completed task findings while preserving the underlying provenance information.

Version History
V1 — Functional Deep Research

The first working release established:

research planning;
concurrent web research;
task summarization;
report generation;
source classification;
real-time streaming;
frontend visualization.
V2 — Traceable + Grounded Research

Current stable release:

v2.0.0


V2 adds:

reliable structured Planner output;
adaptive JSON repair;
execution traces;
execution events;
trace query APIs;
SQLite persistence;
Trace Inspector;
structured Evidence;
structured Claims;
Claim → Evidence relationships;
Evidence APIs;
Claim APIs;
Evidence Inspector.

The core V2 capabilities are:

Traceable

The system records how research was executed.

Grounded

The system records what evidence supports research conclusions.

V3 — Technical Decision Intelligence

V3 is currently being designed and developed.

The main product direction is:

Evidence-grounded technical decision support for engineering technology selection and technical due diligence.

Instead of only answering:

What is Qdrant?


V3 targets questions such as:

Which vector database should our production RAG system use
given our workload, deployment constraints and engineering priorities?

V3 Target Workflow
Technical Decision
        ↓
Requirement Understanding
        ↓
Candidates
        ↓
Decision Criteria
        ↓
Research
        ↓
Evidence
        ↓
Evidence Signals
        ↓
Candidate × Criterion Evaluation
        ↓
Decision Readiness
        ↓
┌─────────────────────────┐
│ Evidence sufficient?    │
└────────────┬────────────┘
          Yes│        No
             │         │
             ▼         ▼
      Recommendation  Research Gap
                         │
                         ▼
                      Replan
                         │
                         ▼
                    Research Again

V3 Design Principles
Users define what matters

The user controls:

requirements;
hard constraints;
priorities;
criterion weights.

If the user does not specify decision criteria, the Agent may suggest reasonable defaults for confirmation.

The Agent determines what the evidence says

LLMs are responsible for interpreting unstructured information, including:

requirement extraction;
evidence interpretation;
claim extraction;
evidence-signal extraction;
research-gap interpretation.
Deterministic logic performs the final aggregation

V3 will not directly ask an LLM:

Which candidate is best?


Instead:

Evidence
 ↓
Evidence Signal
 ↓
Candidate × Criterion Score
 ↓
Weighted Candidate Score
 ↓
Decision Readiness
 ↓
Recommendation


This separates language understanding from decision logic.

V3 Planned Capabilities
Decision Modeling
DecisionCase
├── Candidates
├── Requirements
├── Hard Constraints
└── Decision Criteria

Evidence Signals

Evidence will be transformed into structured signals containing:

Candidate
Criterion
Direction
Strength
Source Confidence
Applicability

Explainable Candidate Evaluation

Each Candidate × Criterion evaluation will expose:

Fitness
Confidence
Coverage
Conflict

Decision Readiness

V3 will determine whether research is sufficient before issuing a final recommendation.

Possible states include:

READY
TENTATIVE
INSUFFICIENT_EVIDENCE
CONFLICTED
DISQUALIFIED


A reliable decision system should be able to say:

There is not yet enough evidence to make a recommendation.

Adaptive Research

When evidence is incomplete:

Evaluation
 ↓
Research Gap
 ↓
Follow-up Query
 ↓
Additional Research
 ↓
Re-evaluation


The Agent therefore evolves from:

Plan once
→ Execute
→ Report


into:

Plan
→ Research
→ Evaluate
→ Replan
→ Verify
→ Stop

V3 Roadmap
Phase 7 — Decision Modeling & Evaluation Baseline
DecisionCase;
Candidate;
Requirement;
hard constraints;
DecisionCriterion;
baseline decision evaluation.
Phase 8 — Criteria-Based Candidate Comparison
Candidate × Criterion matrix;
deterministic weighted scoring;
comparison APIs and UI.
Phase 9 — Evidence Quality & Source Diversity
source-quality scoring;
evidence quality;
evidence applicability;
source diversity.
Phase 10 — Atomic Claim Grounding
atomic claim extraction;
fine-grained Claim → Evidence alignment;
claim-level grounding.
Phase 11 — Research Gap & Conflict Detection
research coverage;
weak-evidence detection;
evidence conflicts;
missing candidate information.
Phase 12 — Adaptive Replanning & Verification
targeted follow-up research;
dynamically generated tasks;
evidence verification loops.
Phase 13 — Decision Scoring & Explainable Readiness
candidate ranking;
decision margin;
decision readiness;
blocking reasons;
explainable recommendation.
Phase 14 — Budget-Aware Adaptive Stopping
task budget;
search budget;
latency budget;
token / cost limits;
diminishing-return stopping.
Phase 15 — Internal Knowledge & Hybrid Retrieval

Combine:

External Web Research
+
Internal Engineering Knowledge


Possible internal sources:

architecture documents;
incident reports;
internal benchmarks;
engineering standards;
previous technical decisions.
Phase 16 — Decision Dashboard & Research Replay

Expose:

Decision
→ Criteria
→ Candidates
→ Scores
→ Claims
→ Evidence
→ Research Gaps
→ Adaptive Iterations
→ Execution Trace

Project Evolution

The technical direction of the project is:

V1
Functional
    ↓
V2
Traceable + Grounded
    ↓
V3
Evaluated + Adaptive


Or more broadly:

Functional
    ↓
Traceable
    ↓
Grounded
    ↓
Evaluated
    ↓
Adaptive


The goal is not to combine as many Agent technologies as possible.

The goal is to build an AI research system in which:

important engineering decisions can be researched, inspected, evaluated, challenged, and traced back to supporting evidence.

Security

External content must always be treated as untrusted data.

This includes:

web pages;
search results;
uploaded documents;
tool outputs;
future internal knowledge sources;
future MCP resources.

Retrieved content must never be allowed to override system instructions or expose secrets.

Never commit:

.env
API keys
runtime databases
logs containing secrets
node_modules
frontend build artifacts

Contributing

Before submitting changes:

create a dedicated branch;
keep each commit focused on one logical change;
add or update tests;
run the backend test suite;
run the frontend production build;
verify that no credentials or runtime files are included.
Release Tags

Major milestones are preserved through Git tags.

Current milestones include:

v1.0.0
phase1-json-reliability
phase2-executor-reliability
phase3-trace-api
phase4-persistence
phase5-trace-inspector
phase6-evidence-foundation
v2.0.0

License

A project license has not yet been finalized.

Future Positioning

The target product direction is:

A traceable, evidence-grounded, evaluated and adaptive Technical Decision Intelligence Agent for engineering teams.

The long-term differentiator is not simply web search, RAG, tool calling, or multi-agent orchestration.

It is the ability to answer:

What should we choose?

while also showing:

Why?

Based on which evidence?

How reliable is that evidence?

What information is still missing?

Is the decision ready to be made?
