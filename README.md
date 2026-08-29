# Evidence-Aware Deep Research Agent

A traceable multi-agent research application that plans research tasks, searches the web, evaluates source quality, summarizes findings, and generates a structured research report with real-time progress streaming.

The project is designed as the first working version of a broader **Evidence-Aware Adaptive Deep Research Agent**. The current V1 focuses on building a reliable end-to-end research workflow with transparent intermediate states, source tracking, concurrent task execution, and a web-based user interface.

---

## Overview

Traditional research assistants often hide the process between receiving a question and producing an answer. This project makes the research workflow observable.

Given a research topic, the system:

1. generates a set of focused research tasks;
2. creates search queries for each task;
3. retrieves information from the web;
4. classifies the quality of each source;
5. generates a summary for every research task;
6. stores intermediate notes;
7. combines the findings into a final report;
8. streams the entire process to the frontend in real time.

```text
Research Topic
    ↓
Task Planning
    ↓
Concurrent Web Research
    ↓
Source Classification
    ↓
Task Summarization
    ↓
Intermediate Notes
    ↓
Final Report
```

---

## Key Features

### Multi-Agent Research Workflow

The backend currently contains three main agent roles:

* **TODO Planner** — decomposes a research topic into a limited set of complementary tasks.
* **Task Summarizer** — summarizes the evidence collected for each task.
* **Report Writer** — combines task-level findings into a final structured report.

### Real-Time Research Progress

The backend streams research events to the frontend using Server-Sent Events over a POST fetch stream.

The interface can display:

* current research status;
* generated TODO items;
* task progress;
* active research task;
* retrieved sources;
* source quality tiers;
* tool-call records;
* task-level summaries;
* final research report;
* error and completion states.

### Concurrent Research Workers

Independent research tasks can run concurrently.

A semaphore currently limits execution to a maximum of two research workers at the same time:

```python
Semaphore(2)
```

This reduces burst concurrency and lowers the risk of temporary provider rate limits.

### Source Quality Classification

Retrieved sources are assigned deterministic quality tiers.

Examples of the current rules include:

| Source type                                             |   Tier |
| ------------------------------------------------------- | -----: |
| Official project websites                               | Tier 1 |
| Official papers and technical reports                   | Tier 1 |
| Official organization GitHub repositories               | Tier 1 |
| General authoritative technical sources                 | Tier 2 |
| Unverified repositories, blogs, forums, and aggregators | Tier 3 |

Source tiers are passed into the task summarization context and included in the final source representation.

### Safe Markdown Rendering

Task summaries and final reports support Markdown rendering in the frontend.

The rendering pipeline is:

```text
LLM Markdown
    ↓
marked
    ↓
DOMPurify
    ↓
Safe HTML Rendering
```

This allows readable reports while reducing the risk of rendering unsafe generated HTML.

### Observable Tool Calls

Tool-call events are displayed in collapsible sections.

The collapsed view shows:

* event ID;
* agent name;
* tool name;
* note ID.

The expanded view shows:

* tool arguments;
* execution result;
* note path.

This preserves debugging information without overwhelming the main interface.

### Robust Streaming Parser

The frontend streaming parser handles:

* POST-based fetch streaming;
* CRLF normalization;
* partial network chunks;
* buffered event blocks;
* multiple `data:` lines;
* multiple events in one network chunk;
* incomplete trailing events;
* explicit `done` and `error` events.

### Output Validation and Fallbacks

Task summaries are checked before being accepted.

The current validation process includes:

* empty-output detection;
* minimum-length validation;
* internal tool-protocol residue detection;
* one automatic retry;
* a final fallback response.

The backend also includes a balanced scanner for removing leaked tool-call structures. It supports nested objects, arrays, quoted brackets, and escaped characters.

---

## System Architecture

```text
User
  │
  ▼
Vue 3 Frontend
  │
  │  POST /api/research/stream
  ▼
Vite Development Proxy
  │
  │  /api → 127.0.0.1:8000
  ▼
FastAPI Backend
  │
  ▼
DeepResearchAgent
  │
  ├── TODO Planner
  │     └── Generates focused research tasks
  │
  ├── Research Workers
  │     ├── Generate search queries
  │     ├── Call Tavily Search
  │     ├── Classify source quality
  │     ├── Generate task summaries
  │     └── Save intermediate notes
  │
  ├── Report Writer
  │     └── Produces the final report
  │
  └── SSE Event Stream
        ├── status
        ├── todo_list
        ├── task_started
        ├── source
        ├── tool_call
        ├── task_summary
        ├── report
        ├── error
        └── done
```

---

## Technology Stack

### Backend

* Python
* FastAPI
* Uvicorn
* HelloAgents
* OpenAI-compatible model API
* Qwen
* ModelScope
* Tavily Search

### Frontend

* Vue 3
* TypeScript
* Vite
* Fetch Streaming
* Server-Sent Events
* marked
* DOMPurify

### Development and Deployment

* tmux
* AutoDL
* SeetaCloud
* Vite development proxy

---

## Project Structure

```text
traceable-deep-research-agent/
├── backend/
│   ├── src/
│   │   ├── agents/
│   │   ├── tools/
│   │   ├── services/
│   │   └── ...
│   ├── main.py
│   ├── .env
│   └── .venv/
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── services/
│   │   └── ...
│   ├── vite.config.ts
│   ├── package.json
│   └── .env.local
│
└── README.md
```

The exact internal folders may differ depending on the current repository layout.

---

## Getting Started

### Prerequisites

Make sure the following software is available:

* Python
* Node.js and npm
* Git

You will also need valid credentials for the configured model provider and Tavily Search.

---

## Backend Setup

Navigate to the backend directory:

```bash
cd backend
```

Create and activate a Python virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
```

On Windows:

```powershell
python -m venv .venv
.venv\Scripts\activate
```

Install the backend dependencies:

```bash
pip install -r requirements.txt
```

Create a `.env` file and add the environment variables required by your model provider and search provider.

Example:

```env
MODEL_API_KEY=your_model_api_key
MODEL_BASE_URL=your_model_base_url
MODEL_NAME=your_model_name
TAVILY_API_KEY=your_tavily_api_key
```

Use the actual variable names defined by the project implementation.

Do not commit the `.env` file or any API keys to Git.

Start the backend:

```bash
set -a
source .env
set +a

unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY all_proxy ALL_PROXY

PYTHONPATH=src .venv/bin/uvicorn main:app \
  --host 0.0.0.0 \
  --port 8000
```

Check the backend health endpoint:

```bash
curl -sS http://127.0.0.1:8000/healthz
```

---

## Frontend Setup

Navigate to the frontend directory:

```bash
cd frontend
```

Install the dependencies:

```bash
npm install
```

Create `frontend/.env.local`:

```env
VITE_API_BASE_URL=/api
```

Start the development server:

```bash
npm run dev
```

The frontend is configured to run on port `6006`.

Open:

```text
http://localhost:6006
```

The Vite development server proxies frontend requests from `/api` to the FastAPI backend running on port `8000`.

Do not set `VITE_API_BASE_URL` to `http://localhost:8000` when accessing the application through a remote deployment. In a browser, `localhost` refers to the user's own computer rather than the remote server.

---

## Production Build

Create a frontend production build with:

```bash
cd frontend
npm run build
```

The generated files will be placed in the frontend build output directory.

---

## API

### Health Check

```http
GET /healthz
```

Example response:

```json
{
  "status": "ok"
}
```

### Start Research Stream

```http
POST /research/stream
```

The frontend accesses this endpoint through:

```http
POST /api/research/stream
```

The response is a stream of SSE-formatted research events.

Example event types:

```text
status
todo_list
task_started
source
tool_call
task_summary
report
error
done
```

The exact request and event payload schemas should be checked in the backend and frontend source code.

---

## Example Workflow

A user submits a topic such as:

```text
Research the architecture and main technical characteristics of Qwen3.
```

The system may generate tasks such as:

```text
1. Identify the official release information.
2. Investigate the model family and parameter configurations.
3. Compare Dense and Mixture-of-Experts architectures.
4. Examine thinking and non-thinking inference modes.
5. Summarize the main changes from the previous generation.
```

Each worker then:

1. generates a search query;
2. retrieves relevant sources;
3. assigns source tiers;
4. summarizes the findings;
5. stores an intermediate note.

The Report Writer combines the completed task summaries into the final report.

---

## Reliability Improvements Included in V1

The current version already includes several reliability improvements:

* correct consumption of generator-based non-streaming execution;
* deterministic source-tier classification;
* buffered and size-limited SSE summary chunks;
* bounded task concurrency;
* balanced removal of leaked tool-call content;
* task-summary validation and retry;
* safe Markdown rendering;
* robust frontend stream parsing;
* structured error events;
* frontend completion and failure states.

---

## Current Limitations

V1 establishes the basic research workflow, but it is not yet a fully evidence-verified research system.

Current limitations include:

* research tasks are generated only at the beginning of a run;
* the system does not dynamically create new tasks from detected knowledge gaps;
* reports are mainly generated from task summaries rather than atomic verified claims;
* citations are not yet validated at the claim level;
* URL availability does not guarantee that a source supports a nearby statement;
* local PDF and private-document retrieval are not yet implemented;
* research state is not yet fully recoverable after every interruption;
* model and search provider quotas can stop a research run;
* source-quality rules are deterministic but currently limited;
* the application does not yet provide a complete offline evaluation framework.

A model provider quota error may occur before task generation begins. This is an external API limitation rather than a frontend, proxy, SSE, or application-rendering failure.

---

## Roadmap

### Phase 1 — Reliability

* robust JSON parsing and repair;
* search retry and provider fallback;
* empty-result recovery;
* URL normalization and deduplication;
* structured runtime metrics;
* persistent research state;
* checkpoint recovery;
* task-level retries;
* improved cancellation and timeout handling;
* offline baseline evaluation.

### Phase 2 — Evidence-Aware Research

* Research Brief;
* unified evidence model;
* Claim–Evidence Ledger;
* claim extraction;
* Citation Validator;
* Coverage Evaluator;
* knowledge-gap detection;
* dynamic research tasks;
* Budget Manager.

The planned research loop is:

```text
Research Brief
    ↓
Initial Tasks
    ↓
Budget-Constrained Retrieval
    ↓
Claim–Evidence Ledger
    ↓
Citation Validation
    ↓
Coverage Evaluation
    ↓
Knowledge-Gap Detection
    ↓
Dynamic Tasks
    ↓
Final Report
```

### Phase 3 — Hybrid Retrieval and Extensibility

* local-document ingestion;
* PDF parsing with page and section metadata;
* keyword and vector retrieval;
* hybrid reranking;
* web and local evidence fusion;
* MCP tool adapters;
* human-in-the-loop review modes;
* evidence-derived knowledge graphs;
* report export and research history.

---

## Planned Evaluation

Future versions will be evaluated using more than visual report quality.

Planned evaluation areas include:

* end-to-end completion rate;
* planner JSON validity;
* task coverage;
* search success rate;
* evidence precision and recall;
* source authority ratio;
* citation precision;
* citation coverage;
* unsupported claim rate;
* knowledge-gap detection;
* dynamic-task utility;
* budget compliance;
* SSE event completeness;
* recovery success rate;
* latency, token usage, and estimated cost.

No performance or accuracy improvements should be claimed until they have been measured on a reproducible evaluation set.

---

## Security Considerations

External content must be treated as untrusted data.

This includes:

* web pages;
* search results;
* uploaded documents;
* tool outputs;
* future MCP resources.

The system should never allow retrieved content to override system instructions, expose API keys, or independently authorize sensitive tool calls.

API credentials must remain in environment variables and must never be committed to the repository.

Recommended `.gitignore` entries include:

```gitignore
.env
.env.*
!.env.example

.venv/
__pycache__/
*.py[cod]

node_modules/
dist/

.DS_Store
.vscode/
.idea/
```

---

## Screenshots

Add screenshots or a demo GIF here after uploading them to the repository.

```markdown
![Research interface](docs/images/research-interface.png)

![Streaming research process](docs/images/research-stream.gif)
```

---

## Future Project Positioning

### LangGraph compatibility

The production Agent uses a custom orchestration runtime because this project
was built to explore orchestration mechanics directly. That runtime already
owns persistent `SummaryState`, tool execution, context budgets, deterministic
stopping, replay/version history, resilience, evaluation, and technical
decision semantics.

Phase 47 adds an optional, thin LangGraph adapter rather than rewriting those
responsibilities. The mapping is direct: `SummaryState` is referenced by a
thin graph state; planning, research, decision enrichment, and reporting are
nodes; the existing stopping decision controls a conditional edge; and the
existing research store is the checkpoint-compatible persistence boundary.
The unified tool runtime remains responsible for external tool execution.

This compatibility is useful for teams that already use LangGraph and makes
the architecture easy to discuss in terms of State, Nodes, Conditional Edges,
and Checkpoints. It is an interoperability option, not a claim that custom
orchestration is universally preferable. LangGraph remains optional:

```bash
uv sync --extra langgraph
python -m services.langgraph_demo
```

The long-term goal of this repository is to become:

> A traceable, evidence-aware, and adaptive deep research agent with budget-aware planning, claim–evidence alignment, citation validation, and hybrid retrieval.

The core objective is not to combine as many agent technologies as possible. It is to build a research process in which important conclusions can be inspected, evaluated, and traced back to supporting evidence.

---

## Contributing

Contributions, bug reports, and implementation suggestions are welcome.

Before submitting a pull request:

1. create a dedicated branch;
2. keep changes focused on one logical problem;
3. add or update relevant tests;
4. verify the frontend build;
5. verify the backend health endpoint;
6. ensure that no secrets are included.

---

## License

Add the selected open-source license to the repository and update this section accordingly.

For example:

```text
MIT License
```

---

## Acknowledgements

This project uses open-source tools and external services including:

* FastAPI
* Vue.js
* Vite
* marked
* DOMPurify
* Tavily
* Qwen
* ModelScope
