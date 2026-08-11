"""FastAPI entrypoint exposing the DeepResearchAgent via HTTP."""

from __future__ import annotations

import json
import sys
from contextlib import asynccontextmanager
from threading import Lock
from typing import Any, AsyncIterator, Dict, Iterator, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from loguru import logger
from pydantic import BaseModel, Field

from agent import DeepResearchAgent
from config import Configuration, SearchAPI
from services.execution_trace import ExecutionTraceService
from services.research_store import SQLiteResearchStore

# 添加控制台日志处理程序
logger.add(
    sys.stderr,
    level="INFO",
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <4}</level> | <cyan>using_function:{function}</cyan> | <cyan>{file}:{line}</cyan> | <level>{message}</level>",
    colorize=True,
)


# 添加错误日志文件处理程序
logger.add(
    sink=sys.stderr,
    level="ERROR",
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <4}</level> | <cyan>using_function:{function}</cyan> | <cyan>{file}:{line}</cyan> | <level>{message}</level>",
    colorize=True,
)


class ResearchRequest(BaseModel):
    """Payload for triggering a research run."""

    topic: str = Field(..., description="Research topic supplied by the user")
    search_api: SearchAPI | None = Field(
        default=None,
        description="Override the default search backend configured via env",
    )


class ResearchResponse(BaseModel):
    """HTTP response containing the generated report and structured tasks."""

    research_id: str = Field(
        ...,
        description="Identifier used to inspect the stored research run",
    )
    report_markdown: str = Field(
        ..., description="Markdown-formatted research report including sections"
    )
    todo_items: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Structured TODO items with summaries and sources",
    )



class ExecutionTraceResponse(BaseModel):
    """Serialized execution trace exposed by the HTTP API."""

    trace_id: str
    task_id: int
    status: str
    started_at: str | None = None
    finished_at: str | None = None
    duration_ms: float | None = None
    current_stage: str | None = None
    retry_count: int = 0
    error_type: str | None = None
    error_message: str | None = None


class ExecutionEventResponse(BaseModel):
    """Serialized execution event exposed by the HTTP API."""

    schema_version: int
    event_id: str
    trace_id: str
    timestamp: str
    task_id: int
    event_type: str
    stage: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class EvidenceResponse(BaseModel):
    """Serialized retrieved evidence exposed by the HTTP API."""

    evidence_id: str
    task_id: int
    trace_id: str
    query: str
    backend: str
    source_title: str | None = None
    source_url: str | None = None
    snippet: str | None = None
    content: str | None = None
    source_rank: int | None = None
    created_at: str


class EvidenceListResponse(BaseModel):
    """Response containing evidence captured for one research run."""

    research_id: str
    evidence: list[EvidenceResponse] = Field(default_factory=list)


class EvidenceDetailResponse(BaseModel):
    """Response containing one evidence item."""

    research_id: str
    evidence: EvidenceResponse


class ClaimResponse(BaseModel):
    """Serialized research claim exposed by the HTTP API."""

    claim_id: str
    task_id: int
    trace_id: str
    text: str
    evidence_ids: list[str] = Field(default_factory=list)
    created_at: str


class ClaimListResponse(BaseModel):
    """Response containing claims for one research run."""

    research_id: str
    claims: list[ClaimResponse] = Field(default_factory=list)


class ClaimDetailResponse(BaseModel):
    """One claim together with its supporting evidence."""

    research_id: str
    claim: ClaimResponse
    evidence: list[EvidenceResponse] = Field(default_factory=list)


class TraceListResponse(BaseModel):
    """Response containing all traces for one research run."""

    research_id: str
    traces: list[ExecutionTraceResponse] = Field(default_factory=list)


class TraceDetailResponse(BaseModel):
    """Response containing one trace and its related execution events."""

    research_id: str
    trace: ExecutionTraceResponse
    events: list[ExecutionEventResponse] = Field(default_factory=list)


class TraceEventsResponse(BaseModel):
    """Response containing execution events associated with one trace."""

    research_id: str
    trace_id: str
    events: list[ExecutionEventResponse] = Field(default_factory=list)

def _serialize_evidence(evidence: Any) -> dict[str, Any]:
    return {
        "evidence_id": evidence.evidence_id,
        "task_id": evidence.task_id,
        "trace_id": evidence.trace_id,
        "query": evidence.query,
        "backend": evidence.backend,
        "source_title": evidence.source_title,
        "source_url": evidence.source_url,
        "snippet": evidence.snippet,
        "content": evidence.content,
        "source_rank": evidence.source_rank,
        "created_at": evidence.created_at,
    }


def _serialize_claim(claim: Any) -> dict[str, Any]:
    return {
        "claim_id": claim.claim_id,
        "task_id": claim.task_id,
        "trace_id": claim.trace_id,
        "text": claim.text,
        "evidence_ids": list(claim.evidence_ids),
        "created_at": claim.created_at,
    }


def _mask_secret(value: Optional[str], visible: int = 4) -> str:
    """Mask sensitive tokens while keeping leading and trailing characters."""
    if not value:
        return "unset"

    if len(value) <= visible * 2:
        return "*" * len(value)

    return f"{value[:visible]}...{value[-visible:]}"


def _build_config(payload: ResearchRequest) -> Configuration:
    overrides: Dict[str, Any] = {}

    if payload.search_api is not None:
        overrides["search_api"] = payload.search_api

    return Configuration.from_env(overrides=overrides)


def create_app() -> FastAPI:
    config = Configuration.from_env()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:

        if config.llm_provider == "ollama":
            base_url = config.sanitized_ollama_url()
        elif config.llm_provider == "lmstudio":
            base_url = config.lmstudio_base_url
        else:
            base_url = config.llm_base_url or "unset"

        logger.info(
            "DeepResearch configuration loaded: provider=%s model=%s base_url=%s search_api=%s "
            "max_loops=%s fetch_full_page=%s tool_calling=%s strip_thinking=%s api_key=%s",
            config.llm_provider,
            config.resolved_model() or "unset",
            base_url,
            (config.search_api.value if isinstance(config.search_api, SearchAPI) else config.search_api),
            config.max_web_research_loops,
            config.fetch_full_page,
            config.use_tool_calling,
            config.strip_thinking_tokens,
            _mask_secret(config.llm_api_key),
        )

        yield

    app = FastAPI(
        title="HelloAgents Deep Researcher",
        lifespan=lifespan,
    )

    app.state.research_store = SQLiteResearchStore(
        config.research_db_path
    )
    app.state.execution_trace_service = ExecutionTraceService(
        lock=Lock(),
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/healthz")
    def health_check() -> Dict[str, str]:
        return {"status": "ok"}

    @app.get(
        "/research/{research_id}/evidence",
        response_model=EvidenceListResponse,
    )
    def list_research_evidence(research_id: str) -> dict[str, Any]:
        """Return all structured evidence captured for one research run."""

        state = app.state.research_store.get(research_id)

        if state is None:
            raise HTTPException(
                status_code=404,
                detail="Research run not found",
            )

        return {
            "research_id": research_id,
            "evidence": [
                _serialize_evidence(evidence)
                for evidence in state.evidence_items
            ],
        }

    @app.get(
        "/research/{research_id}/evidence/{evidence_id}",
        response_model=EvidenceDetailResponse,
    )
    def get_research_evidence(
        research_id: str,
        evidence_id: str,
    ) -> dict[str, Any]:
        """Return one structured evidence item."""

        state = app.state.research_store.get(research_id)

        if state is None:
            raise HTTPException(
                status_code=404,
                detail="Research run not found",
            )

        evidence = next(
            (
                item
                for item in state.evidence_items
                if item.evidence_id == evidence_id
            ),
            None,
        )

        if evidence is None:
            raise HTTPException(
                status_code=404,
                detail="Evidence not found",
            )

        return {
            "research_id": research_id,
            "evidence": _serialize_evidence(evidence),
        }

    @app.get(
        "/research/{research_id}/claims",
        response_model=ClaimListResponse,
    )
    def list_research_claims(research_id: str) -> dict[str, Any]:
        """Return all claims generated for one research run."""

        state = app.state.research_store.get(research_id)

        if state is None:
            raise HTTPException(
                status_code=404,
                detail="Research run not found",
            )

        return {
            "research_id": research_id,
            "claims": [
                _serialize_claim(claim)
                for claim in state.claims
            ],
        }

    @app.get(
        "/research/{research_id}/claims/{claim_id}",
        response_model=ClaimDetailResponse,
    )
    def get_research_claim(
        research_id: str,
        claim_id: str,
    ) -> dict[str, Any]:
        """Return one claim and its supporting evidence."""

        state = app.state.research_store.get(research_id)

        if state is None:
            raise HTTPException(
                status_code=404,
                detail="Research run not found",
            )

        claim = next(
            (
                item
                for item in state.claims
                if item.claim_id == claim_id
            ),
            None,
        )

        if claim is None:
            raise HTTPException(
                status_code=404,
                detail="Claim not found",
            )

        evidence_by_id = {
            evidence.evidence_id: evidence
            for evidence in state.evidence_items
        }

        supporting_evidence = [
            evidence_by_id[evidence_id]
            for evidence_id in claim.evidence_ids
            if evidence_id in evidence_by_id
        ]

        return {
            "research_id": research_id,
            "claim": _serialize_claim(claim),
            "evidence": [
                _serialize_evidence(evidence)
                for evidence in supporting_evidence
            ],
        }

    @app.get(
        "/research/{research_id}/traces",
        response_model=TraceListResponse,
    )
    def list_research_traces(research_id: str) -> dict[str, Any]:
        """Return execution traces for a stored research run."""

        state = app.state.research_store.get(research_id)

        if state is None:
            raise HTTPException(
                status_code=404,
                detail="Research run not found",
            )

        traces = [
            {
                "trace_id": trace.trace_id,
                "task_id": trace.task_id,
                "status": trace.status,
                "started_at": trace.started_at,
                "finished_at": trace.finished_at,
                "duration_ms": trace.duration_ms,
                "current_stage": trace.current_stage,
                "retry_count": trace.retry_count,
                "error_type": trace.error_type,
                "error_message": trace.error_message,
            }
            for trace in state.execution_traces
        ]

        return {
            "research_id": research_id,
            "traces": traces,
        }

    @app.get(
        "/research/{research_id}/traces/{trace_id}",
        response_model=TraceDetailResponse,
    )
    def get_research_trace(
        research_id: str,
        trace_id: str,
    ) -> dict[str, Any]:
        """Return one execution trace and its related events."""

        state = app.state.research_store.get(research_id)

        if state is None:
            raise HTTPException(
                status_code=404,
                detail="Research run not found",
            )

        result = app.state.execution_trace_service.serialize_trace(
            state,
            trace_id,
        )

        if result["trace"]["trace_id"] is None:
            raise HTTPException(
                status_code=404,
                detail="Execution trace not found",
            )

        return {
            "research_id": research_id,
            **result,
        }

    @app.get(
        "/research/{research_id}/traces/{trace_id}/events",
        response_model=TraceEventsResponse,
    )
    def get_research_trace_events(
        research_id: str,
        trace_id: str,
    ) -> dict[str, Any]:
        """Return execution events associated with one trace."""

        state = app.state.research_store.get(research_id)

        if state is None:
            raise HTTPException(
                status_code=404,
                detail="Research run not found",
            )

        trace_result = app.state.execution_trace_service.get_trace(
            state,
            trace_id,
        )

        if trace_result["trace"] is None:
            raise HTTPException(
                status_code=404,
                detail="Execution trace not found",
            )

        events = app.state.execution_trace_service.get_events(
            state,
            trace_id=trace_id,
        )

        return {
            "research_id": research_id,
            "trace_id": trace_id,
            "events": [
                {
                    "schema_version": event.schema_version,
                    "event_id": event.event_id,
                    "trace_id": event.trace_id,
                    "timestamp": event.timestamp,
                    "task_id": event.task_id,
                    "event_type": event.event_type,
                    "stage": event.stage,
                    "metadata": event.metadata,
                }
                for event in events
            ],
        }

    @app.post("/research", response_model=ResearchResponse)
    def run_research(payload: ResearchRequest) -> ResearchResponse:
        try:
            config = _build_config(payload)
            agent = DeepResearchAgent(config=config)
            result = agent.run(payload.topic)

            state = agent.last_state
            if state is None:
                raise RuntimeError("Research state was not captured")

            research_id = app.state.research_store.save(state)
        except ValueError as exc:  # Likely due to unsupported configuration
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:  # pragma: no cover - defensive guardrail
            raise HTTPException(status_code=500, detail="Research failed") from exc

        todo_payload = [
            {
                "id": item.id,
                "title": item.title,
                "intent": item.intent,
                "query": item.query,
                "status": item.status,
                "summary": item.summary,
                "sources_summary": item.sources_summary,
                "note_id": item.note_id,
                "note_path": item.note_path,
            }
            for item in result.todo_items
        ]

        return ResearchResponse(
            research_id=research_id,
            report_markdown=(result.report_markdown or result.running_summary or ""),
            todo_items=todo_payload,
        )

    @app.post("/research/stream")
    def stream_research(payload: ResearchRequest) -> StreamingResponse:
        try:
            config = _build_config(payload)
            agent = DeepResearchAgent(config=config)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        def event_iterator() -> Iterator[str]:
            try:
                for event in agent.run_stream(payload.topic):
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

                state = agent.last_state

                if state is None:
                    raise RuntimeError(
                        "Research state was not captured"
                    )

                research_id = app.state.research_store.save(
                    state
                )

                stored_payload = {
                    "type": "research_stored",
                    "research_id": research_id,
                }

                yield (
                    f"data: {json.dumps(stored_payload, ensure_ascii=False)}\n\n"
                )

            except Exception as exc:  # pragma: no cover - defensive guardrail
                logger.exception("Streaming research failed")
                error_payload = {"type": "error", "detail": str(exc)}
                yield f"data: {json.dumps(error_payload, ensure_ascii=False)}\n\n"

        return StreamingResponse(
            event_iterator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            },
        )

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
