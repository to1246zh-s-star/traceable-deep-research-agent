"""FastAPI entrypoint exposing the DeepResearchAgent via HTTP."""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
import sys
from copy import deepcopy
from contextlib import asynccontextmanager
from threading import Lock
from typing import Any, AsyncIterator, Dict, Iterator

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from loguru import logger
from pydantic import BaseModel, Field

from agent import DeepResearchAgent
from models import ReevaluationRequest
from services.reevaluation_preparation import (
    prepare_reevaluation,
)
from config import Configuration, SearchAPI
from services.decision_artifact import build_decision_artifact
from services.execution_trace import ExecutionTraceService
from services.decision_version_diff import compare_research_versions
from services.decision_evolution import build_decision_evolution
from services.research_store import SQLiteResearchStore
from services.report_presentation import render_user_facing_report
from services.deployment_config import (
    safe_endpoint_for_log,
    validate_deployment_config,
)
from services.llm_preflight import (
    LLMPreflightGuard,
    LLMPreflightResult,
)

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


class ResearchReevaluationRequest(BaseModel):
    """Structured observations for re-evaluating one stored decision."""

    observed_trigger_ids: list[str] = Field(
        default_factory=list
    )

    changed_source_fields: dict[
        str,
        list[str],
    ] = Field(
        default_factory=dict
    )

    observed_facts: list[str] = Field(
        default_factory=list
    )

    search_api: SearchAPI | None = Field(
        default=None,
        description=(
            "Optional search backend override "
            "for executed follow-up research"
        ),
    )


class ResearchReevaluationResponse(BaseModel):
    """Result of preparing or executing decision re-evaluation."""

    source_research_id: str

    research_id: str | None = None

    status: str
    eligible: bool
    executed: bool = False

    assessment: dict[str, Any]
    plan: dict[str, Any]
    reactivation: dict[str, Any]
    lineage: dict[str, Any] | None = None



class VersionFieldChangeResponse(BaseModel):
    """One deterministic structural change between research versions."""

    field_name: str
    change_type: str
    before: Any = None
    after: Any = None


class DeterministicVersionDiffResponse(BaseModel):
    """Pure persisted-state structural diff payload."""

    source_research_id: str
    target_research_id: str
    has_changes: bool

    decision_changes: list[
        VersionFieldChangeResponse
    ] = Field(default_factory=list)

    readiness_changes: list[
        VersionFieldChangeResponse
    ] = Field(default_factory=list)

    recommendation_changes: list[
        VersionFieldChangeResponse
    ] = Field(default_factory=list)

    research_gap_changes: list[
        VersionFieldChangeResponse
    ] = Field(default_factory=list)

    evidence_changes: list[
        VersionFieldChangeResponse
    ] = Field(default_factory=list)

    assumption_changes: list[
        VersionFieldChangeResponse
    ] = Field(default_factory=list)

    trigger_changes: list[
        VersionFieldChangeResponse
    ] = Field(default_factory=list)

    architecture_changes: list[
        VersionFieldChangeResponse
    ] = Field(default_factory=list)

    unchanged_sections: list[str] = Field(
        default_factory=list
    )

    summary_lines: list[str] = Field(
        default_factory=list
    )


class ResearchVersionDiffResponse(
    DeterministicVersionDiffResponse
):
    """Structural diff plus cross-run lineage provenance."""

    same_lineage: bool


class ChangeAttributionItemResponse(BaseModel):
    """One persisted structural attribution item."""

    field_name: str
    change_type: str
    before: Any = None
    after: Any = None


class ChangeAttributionGroupResponse(BaseModel):
    """One deterministic structural attribution group."""

    section: str
    label: str

    items: list[
        ChangeAttributionItemResponse
    ] = Field(default_factory=list)

    added_count: int = 0
    removed_count: int = 0
    changed_count: int = 0

    has_changes: bool = False


class DecisionChangeAttributionResponse(BaseModel):
    """Detailed deterministic attribution for one version edge."""

    source_research_id: str
    target_research_id: str

    has_changes: bool

    groups: list[
        ChangeAttributionGroupResponse
    ] = Field(default_factory=list)

    changed_sections: list[str] = Field(
        default_factory=list
    )

    unchanged_sections: list[str] = Field(
        default_factory=list
    )


class DecisionEvolutionStepResponse(BaseModel):
    """One persisted parent-to-child evolution edge."""

    source_research_id: str
    target_research_id: str
    root_research_id: str

    source_version_number: int
    target_version_number: int

    target_creation_reason: str

    created_from_trigger_ids: list[str] = Field(
        default_factory=list
    )

    diff: DeterministicVersionDiffResponse

    attribution: DecisionChangeAttributionResponse


class DecisionEvolutionResponse(BaseModel):
    """Branch-aware deterministic decision evolution."""

    requested_research_id: str
    root_research_id: str

    research_ids: list[str] = Field(
        default_factory=list
    )

    steps: list[
        DecisionEvolutionStepResponse
    ] = Field(default_factory=list)

    root_version_ids: list[str] = Field(
        default_factory=list
    )

    branch_point_ids: list[str] = Field(
        default_factory=list
    )

    leaf_version_ids: list[str] = Field(
        default_factory=list
    )

    has_branches: bool


class ResearchLineageResponse(BaseModel):
    """Immutable provenance metadata for one research run."""

    research_id: str
    root_research_id: str
    parent_research_id: str | None = None
    version_number: int
    creation_reason: str
    created_from_trigger_ids: list[str] = Field(
        default_factory=list
    )


class ResearchVersionListResponse(BaseModel):
    """Ordered research versions belonging to one root run."""

    research_id: str
    root_research_id: str
    versions: list[ResearchLineageResponse] = Field(
        default_factory=list
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
    source_type: str = "UNKNOWN"
    authority_type: str = "UNKNOWN"
    authority_level: str = "UNKNOWN"
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

class ResearchReplayTaskSourceResponse(BaseModel):
    """Source metadata linked to one persisted research task."""

    source_title: str | None = None
    source_url: str | None = None
    backend: str
    source_rank: int | None = None
    source_type: str = "UNKNOWN"
    authority_type: str = "UNKNOWN"
    authority_level: str = "UNKNOWN"


class ResearchReplayTaskResponse(BaseModel):
    """One research task in replay order."""

    task_id: int
    title: str
    intent: str
    query: str
    status: str
    summary: str | None = None
    summary_status: str
    summary_error_type: str | None = None
    evidence_count: int = 0
    sources: list[ResearchReplayTaskSourceResponse] = Field(
        default_factory=list
    )

    notices: list[str] = Field(default_factory=list)
    error_types: list[str] = Field(default_factory=list)

    trace_ids: list[str] = Field(default_factory=list)
    claim_ids: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)


class ResearchReplayEventResponse(BaseModel):
    """Normalized replay event across planning, execution and grounding."""

    timestamp: str | None = None
    event_type: str
    task_id: int | None = None
    trace_id: str | None = None
    reference_id: str | None = None
    summary: str | None = None


class ResearchReplayResponse(BaseModel):
    """Aggregated replay view for one stored research run."""

    research_id: str
    research_topic: str

    task_count: int
    trace_count: int
    claim_count: int
    evidence_count: int

    tasks: list[ResearchReplayTaskResponse] = Field(default_factory=list)
    timeline: list[ResearchReplayEventResponse] = Field(default_factory=list)
    report_markdown: str | None = None

    decision: dict[str, Any] | None = None

    runtime_notices: list[dict[str, Any]] = Field(
        default_factory=list
    )

    tool_execution_traces: list[dict[str, Any]] = Field(
        default_factory=list
    )

    llm_runtime_circuit: dict[str, Any] = Field(
        default_factory=dict
    )

    decision_artifact: dict[str, Any] | None = None

    lineage: dict[str, Any] | None = None
    versions: list[dict[str, Any]] = Field(
        default_factory=list
    )


def _serialize_v3_value(value: Any) -> Any:
    """Serialize V3 decision dataclasses into JSON-safe structures."""

    if value is None:
        return None

    if is_dataclass(value):
        return {
            key: _serialize_v3_value(item)
            for key, item in asdict(value).items()
        }

    if isinstance(value, dict):
        return {
            str(key): _serialize_v3_value(item)
            for key, item in value.items()
        }

    if isinstance(value, (list, tuple)):
        return [
            _serialize_v3_value(item)
            for item in value
        ]

    return value


def _serialize_decision_intelligence(
    state: Any,
) -> dict[str, Any] | None:
    """Build the persisted V3 decision-intelligence API payload."""

    if state.decision_case is None:
        return None

    return {
        "case": _serialize_v3_value(
            state.decision_case
        ),
        "technical_context": _serialize_v3_value(
            state.technical_context
        ),
        "integration_assessments": _serialize_v3_value(
            state.integration_assessments
        ),
        "evaluation": _serialize_v3_value(
            state.decision_evaluation
        ),
        "comparison": _serialize_v3_value(
            state.decision_comparison
        ),
        "sensitivity": _serialize_v3_value(
            state.decision_sensitivity
        ),
        "robustness": _serialize_v3_value(
            state.recommendation_robustness
        ),
        "readiness": _serialize_v3_value(
            state.decision_readiness
        ),
        "research_analysis": _serialize_v3_value(
            state.research_analysis
        ),
        "stopping_decision": _serialize_v3_value(
            state.stopping_decision
        ),
        "research_budget": _serialize_v3_value(
            state.research_budget
        ),
        "research_usage": _serialize_v3_value(
            state.research_usage
        ),
        "adaptive_research_state": _serialize_v3_value(
            state.adaptive_research_state
        ),
    }


def _index_evidence_assessments(state: Any) -> dict[str, Any]:
    return {
        assessment.evidence_id: assessment
        for assessment in getattr(state, "evidence_assessments", [])
    }


def _serialize_evidence(
    evidence: Any,
    assessment: Any | None = None,
) -> dict[str, Any]:
    source_quality = getattr(assessment, "source_quality", None)

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
        "source_type": (
            getattr(source_quality, "source_type", None) or "UNKNOWN"
        ),
        "authority_type": (
            getattr(source_quality, "authority_type", None) or "UNKNOWN"
        ),
        "authority_level": (
            getattr(source_quality, "authority_level", None) or "UNKNOWN"
        ),
        "created_at": evidence.created_at,
    }


def _serialize_replay_task_source(
    evidence: Any,
    assessment: Any | None = None,
) -> dict[str, Any]:
    serialized = _serialize_evidence(evidence, assessment)
    return {
        key: serialized[key]
        for key in (
            "source_title",
            "source_url",
            "backend",
            "source_rank",
            "source_type",
            "authority_type",
            "authority_level",
        )
    }


def _serialize_runtime_efficiency(state: Any) -> dict[str, Any]:
    """Expose run observability without turning it into decision truth."""

    efficiency = getattr(state, "runtime_efficiency", None)
    field_names = (
        "latency_ms",
        "llm_call_count",
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
        "llm_usage_complete",
        "estimated_cost",
        "cost_currency",
        "cost_basis",
    )
    return {
        name: getattr(efficiency, name, None)
        for name in field_names
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


def _build_research_replay(
    research_id: str,
    state: Any,
) -> dict[str, Any]:
    """Build deterministic task-centric replay data from stored research state."""

    traces_by_task: dict[int, list[Any]] = {}

    for trace in state.execution_traces:
        traces_by_task.setdefault(
            trace.task_id,
            [],
        ).append(trace)

    claims_by_task: dict[int, list[Any]] = {}

    for claim in state.claims:
        claims_by_task.setdefault(
            claim.task_id,
            [],
        ).append(claim)

    evidence_by_task: dict[int, list[Any]] = {}

    for evidence in state.evidence_items:
        evidence_by_task.setdefault(
            evidence.task_id,
            [],
        ).append(evidence)

    evidence_assessments = _index_evidence_assessments(state)

    tasks: list[dict[str, Any]] = []

    for task in state.todo_items:
        task_traces = traces_by_task.get(
            task.id,
            [],
        )
        task_claims = claims_by_task.get(
            task.id,
            [],
        )
        task_evidence = evidence_by_task.get(
            task.id,
            [],
        )
        summary_error_type = next(
            (
                notice.split(":", 1)[1] or "unknown"
                for notice in task.notices
                if notice.startswith("summarization_failed:")
            ),
            None,
        )
        summary = (
            task.summary.strip()
            if isinstance(task.summary, str) and task.summary.strip()
            else None
        )
        if summary_error_type is not None:
            summary_status = "failed"
        elif summary is not None:
            summary_status = "available"
        else:
            summary_status = "unavailable"

        tasks.append(
            {
                "task_id": task.id,
                "title": task.title,
                "intent": task.intent,
                "query": task.query,
                "status": task.status,
                "summary": summary,
                "summary_status": summary_status,
                "summary_error_type": summary_error_type,
                "evidence_count": len(task_evidence),
                "sources": [
                    _serialize_replay_task_source(
                        evidence,
                        evidence_assessments.get(evidence.evidence_id),
                    )
                    for evidence in task_evidence[:5]
                ],
                "notices": list(
                    task.notices
                ),
                "error_types": sorted(
                    {
                        trace.error_type
                        for trace in task_traces
                        if trace.error_type
                    }
                ),
                "trace_ids": [
                    trace.trace_id
                    for trace in task_traces
                ],
                "claim_ids": [
                    claim.claim_id
                    for claim in task_claims
                ],
                "evidence_ids": [
                    evidence.evidence_id
                    for evidence in task_evidence
                ],
            }
        )

    timeline: list[dict[str, Any]] = []

    for trace in state.execution_traces:
        timeline.append(
            {
                "timestamp": trace.started_at,
                "event_type": "trace_started",
                "task_id": trace.task_id,
                "trace_id": trace.trace_id,
                "reference_id": trace.trace_id,
                "summary": (
                    f"Task {trace.task_id} execution started"
                ),
            }
        )

        if trace.finished_at:
            timeline.append(
                {
                    "timestamp": trace.finished_at,
                    "event_type": (
                        "trace_completed"
                        if trace.status == "completed"
                        else "trace_finished"
                    ),
                    "task_id": trace.task_id,
                    "trace_id": trace.trace_id,
                    "reference_id": trace.trace_id,
                    "summary": (
                        f"Task {trace.task_id} execution "
                        f"finished with status {trace.status}"
                    ),
                }
            )

    for event in state.execution_events:
        timeline.append(
            {
                "timestamp": event.timestamp,
                "event_type": event.event_type,
                "task_id": event.task_id,
                "trace_id": event.trace_id,
                "reference_id": event.event_id,
                "summary": event.stage,
            }
        )

    for evidence in state.evidence_items:
        timeline.append(
            {
                "timestamp": evidence.created_at,
                "event_type": "evidence_captured",
                "task_id": evidence.task_id,
                "trace_id": evidence.trace_id,
                "reference_id": evidence.evidence_id,
                "summary": (
                    evidence.source_title
                    or evidence.source_url
                    or "Evidence captured"
                ),
            }
        )

    for claim in state.claims:
        timeline.append(
            {
                "timestamp": claim.created_at,
                "event_type": "claim_grounded",
                "task_id": claim.task_id,
                "trace_id": claim.trace_id,
                "reference_id": claim.claim_id,
                "summary": claim.text,
            }
        )

    timeline.sort(
        key=lambda item: (
            item["timestamp"] is None,
            item["timestamp"] or "",
            item["task_id"]
            if item["task_id"] is not None
            else -1,
            item["event_type"],
            item["reference_id"] or "",
        )
    )

    return {
        "research_id": research_id,
        "research_topic": state.research_topic,
        "task_count": len(state.todo_items),
        "trace_count": len(state.execution_traces),
        "claim_count": len(state.claims),
        "evidence_count": len(state.evidence_items),
        "tasks": tasks,
        "timeline": timeline,
        "report_markdown": render_user_facing_report(state),
        "decision": _serialize_decision_intelligence(
            state
        ),
        "decision_artifact": _serialize_v3_value(
            build_decision_artifact(state)
        ),
        "runtime_notices": [
            dict(notice)
            for notice in getattr(
                state,
                "runtime_notices",
                [],
            )
        ],
        "runtime_efficiency": _serialize_runtime_efficiency(state),
        "tool_execution_traces": [
            dict(trace)
            for trace in getattr(
                state,
                "tool_execution_traces",
                [],
            )
            if isinstance(trace, dict)
        ],
        "llm_runtime_circuit": dict(
            getattr(
                state,
                "llm_runtime_circuit",
                {},
            )
        ),
    }


def _build_config(payload: ResearchRequest) -> Configuration:
    overrides: Dict[str, Any] = {}

    if payload.search_api is not None:
        overrides["search_api"] = payload.search_api

    return Configuration.from_env(overrides=overrides)


def _probe_llm(
    agent: DeepResearchAgent,
) -> object:
    """
    Execute one minimal LLM availability probe.

    This intentionally bypasses the research workflow. The result content
    is irrelevant; successful invocation alone establishes short-lived
    provider availability.
    """

    messages = [
        {
            "role": "user",
            "content": "Reply with OK.",
        }
    ]

    return agent.llm.invoke(
        messages,
        max_tokens=4,
    )


def _llm_unavailable_detail(
    result: LLMPreflightResult,
    *,
    provider: str,
) -> dict[str, str]:
    """Build a safe public API error payload."""

    return {
        "code": result.code,
        "reason": result.reason,
        "provider": provider or "unknown",
    }


def create_app() -> FastAPI:
    config = Configuration.from_env()
    deployment_status = validate_deployment_config(config)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:

        if config.llm_provider == "ollama":
            base_url = safe_endpoint_for_log(config.sanitized_ollama_url())
        elif config.llm_provider == "lmstudio":
            base_url = safe_endpoint_for_log(config.lmstudio_base_url)
        else:
            base_url = safe_endpoint_for_log(config.llm_base_url)

        logger.info(
            "DeepResearch configuration loaded: provider=%s model=%s base_url=%s search_api=%s "
            "max_loops=%s fetch_full_page=%s tool_calling=%s strip_thinking=%s config_ready=%s",
            config.llm_provider,
            config.resolved_model() or "unset",
            base_url,
            (config.search_api.value if isinstance(config.search_api, SearchAPI) else config.search_api),
            config.max_web_research_loops,
            config.fetch_full_page,
            config.use_tool_calling,
            config.strip_thinking_tokens,
            deployment_status.ready,
        )

        yield

    app = FastAPI(
        title="HelloAgents Deep Researcher",
        lifespan=lifespan,
    )

    app.state.research_store = SQLiteResearchStore(
        config.research_db_path
    )
    app.state.deployment_config_status = deployment_status
    app.state.execution_trace_service = ExecutionTraceService(
        lock=Lock(),
    )

    app.state.llm_preflight_guard = LLMPreflightGuard(
        success_ttl_seconds=60.0,
        failure_ttl_seconds=15.0,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    def ensure_llm_available(
        agent: DeepResearchAgent,
        config: Configuration,
    ) -> None:
        """
        Fail before starting research when the configured LLM is unavailable.

        The guard caches recent results so healthy requests do not add an
        extra provider call for every research run.
        """

        result = app.state.llm_preflight_guard.check(
            lambda: _probe_llm(agent)
        )

        if result.available:
            return

        logger.warning(
            "LLM preflight failed: provider=%s code=%s reason=%s",
            config.llm_provider,
            result.code,
            result.reason,
        )

        raise HTTPException(
            status_code=503,
            detail=_llm_unavailable_detail(
                result,
                provider=config.llm_provider,
            ),
        )


    @app.get("/healthz")
    def health_check() -> Dict[str, str]:
        return {"status": "ok"}

    @app.get("/readyz")
    def readiness_check() -> JSONResponse:
        """Report configuration readiness without probing providers."""
        status = app.state.deployment_config_status
        return JSONResponse(
            status_code=200 if status.ready else 503,
            content=status.as_dict(),
        )

    @app.get(
        "/research/{research_id}/replay",
        response_model=ResearchReplayResponse,
    )
    def get_research_replay(
        research_id: str,
    ) -> dict[str, Any]:
        """Return an aggregated replay of one stored research run."""

        state = app.state.research_store.get(
            research_id
        )

        if state is None:
            raise HTTPException(
                status_code=404,
                detail="Research run not found",
            )

        replay = _build_research_replay(
            research_id,
            state,
        )

        lineage = None
        versions = []

        get_lineage = getattr(
            app.state.research_store,
            "get_lineage",
            None,
        )

        if callable(get_lineage):
            lineage = get_lineage(
                research_id
            )

        if lineage is not None:
            list_lineage = getattr(
                app.state.research_store,
                "list_lineage",
                None,
            )

            if callable(list_lineage):
                versions = list_lineage(
                    lineage.root_research_id
                )

        replay["lineage"] = (
            _serialize_v3_value(
                lineage
            )
        )

        replay["versions"] = [
            _serialize_v3_value(item)
            for item in versions
        ]

        return replay


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

        assessments = _index_evidence_assessments(state)

        return {
            "research_id": research_id,
            "evidence": [
                _serialize_evidence(
                    evidence,
                    assessments.get(evidence.evidence_id),
                )
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

        assessments = _index_evidence_assessments(state)

        return {
            "research_id": research_id,
            "evidence": _serialize_evidence(
                evidence,
                assessments.get(evidence.evidence_id),
            ),
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

        assessments = _index_evidence_assessments(state)

        return {
            "research_id": research_id,
            "claim": _serialize_claim(claim),
            "evidence": [
                _serialize_evidence(
                    evidence,
                    assessments.get(evidence.evidence_id),
                )
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

    @app.get(
        "/research/{research_id}/evolution",
        response_model=DecisionEvolutionResponse,
    )
    def get_research_evolution(
        research_id: str,
    ) -> DecisionEvolutionResponse:
        """Return deterministic branch-aware evolution for one lineage."""

        state = app.state.research_store.get(
            research_id
        )

        if state is None:
            raise HTTPException(
                status_code=404,
                detail="Research run not found",
            )

        get_lineage = getattr(
            app.state.research_store,
            "get_lineage",
            None,
        )

        list_lineage = getattr(
            app.state.research_store,
            "list_lineage",
            None,
        )

        if (
            not callable(get_lineage)
            or not callable(list_lineage)
        ):
            raise HTTPException(
                status_code=409,
                detail=(
                    "Research lineage is unavailable "
                    "for this store"
                ),
            )

        lineage = get_lineage(
            research_id
        )

        if lineage is None:
            raise HTTPException(
                status_code=404,
                detail="Research lineage not found",
            )

        lineage_items = list_lineage(
            lineage.root_research_id
        )

        evolution = build_decision_evolution(
            root_research_id=(
                lineage.root_research_id
            ),
            lineage_items=lineage_items,
            load_state=(
                app.state.research_store.get
            ),
        )

        return DecisionEvolutionResponse(
            requested_research_id=(
                research_id
            ),
            **_serialize_v3_value(
                evolution
            ),
        )


    @app.get(
        "/research/{target_research_id}/diff/{source_research_id}",
        response_model=ResearchVersionDiffResponse,
    )
    def get_research_version_diff(
        target_research_id: str,
        source_research_id: str,
    ) -> ResearchVersionDiffResponse:
        """Compare two persisted research runs deterministically."""

        source_state = (
            app.state.research_store.get(
                source_research_id
            )
        )

        if source_state is None:
            raise HTTPException(
                status_code=404,
                detail="Source research run not found",
            )

        target_state = (
            app.state.research_store.get(
                target_research_id
            )
        )

        if target_state is None:
            raise HTTPException(
                status_code=404,
                detail="Target research run not found",
            )

        source_lineage = None
        target_lineage = None

        get_lineage = getattr(
            app.state.research_store,
            "get_lineage",
            None,
        )

        if callable(get_lineage):
            source_lineage = get_lineage(
                source_research_id
            )
            target_lineage = get_lineage(
                target_research_id
            )

        same_lineage = bool(
            source_lineage is not None
            and target_lineage is not None
            and source_lineage.root_research_id
            == target_lineage.root_research_id
        )

        diff = compare_research_versions(
            source_research_id=(
                source_research_id
            ),
            source_state=source_state,
            target_research_id=(
                target_research_id
            ),
            target_state=target_state,
        )

        return ResearchVersionDiffResponse(
            same_lineage=same_lineage,
            **_serialize_v3_value(diff),
        )


    @app.get(
        "/research/{research_id}/lineage",
        response_model=ResearchLineageResponse,
    )
    def get_research_lineage(
        research_id: str,
    ) -> ResearchLineageResponse:
        """Return immutable provenance metadata for one research run."""

        lineage = (
            app.state.research_store.get_lineage(
                research_id
            )
        )

        if lineage is None:
            raise HTTPException(
                status_code=404,
                detail="Research run not found",
            )

        return ResearchLineageResponse(
            **_serialize_v3_value(
                lineage
            )
        )


    @app.get(
        "/research/{research_id}/versions",
        response_model=ResearchVersionListResponse,
    )
    def get_research_versions(
        research_id: str,
    ) -> ResearchVersionListResponse:
        """Return the complete ordered version chain for one run."""

        lineage = (
            app.state.research_store.get_lineage(
                research_id
            )
        )

        if lineage is None:
            raise HTTPException(
                status_code=404,
                detail="Research run not found",
            )

        versions = (
            app.state.research_store.list_lineage(
                lineage.root_research_id
            )
        )

        return ResearchVersionListResponse(
            research_id=research_id,
            root_research_id=(
                lineage.root_research_id
            ),
            versions=[
                ResearchLineageResponse(
                    **_serialize_v3_value(
                        item
                    )
                )
                for item in versions
            ],
        )


    @app.post(
        "/research/{research_id}/reevaluate",
        response_model=ResearchReevaluationResponse,
    )
    def reevaluate_research(
        research_id: str,
        payload: ResearchReevaluationRequest,
    ) -> ResearchReevaluationResponse:
        """
        Re-evaluate one persisted technical decision.

        Historical research is immutable at this API boundary:
        execution always happens on a deep-copied working state and,
        when research is actually executed, is saved as a new
        research_id.
        """

        historical_state = (
            app.state.research_store.get(
                research_id
            )
        )

        if historical_state is None:
            raise HTTPException(
                status_code=404,
                detail="Research run not found",
            )

        if historical_state.decision_case is None:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Research run has no "
                    "technical decision"
                ),
            )

        if historical_state.research_analysis is None:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Research run has no "
                    "research analysis"
                ),
            )

        if (
            historical_state.adaptive_research_state
            is None
        ):
            raise HTTPException(
                status_code=400,
                detail=(
                    "Research run has no "
                    "adaptive research state"
                ),
            )

        # Never mutate the historical replay state.
        working_state = deepcopy(
            historical_state
        )

        decision = working_state.decision_case

        request = ReevaluationRequest(
            decision_id=decision.decision_id,
            observed_trigger_ids=list(
                payload.observed_trigger_ids
            ),
            changed_source_fields={
                source_type: list(fields)
                for source_type, fields
                in payload.changed_source_fields.items()
            },
            observed_facts=list(
                payload.observed_facts
            ),
        )

        preparation = prepare_reevaluation(
            decision,
            working_state.research_analysis,
            working_state.adaptive_research_state,
            request,
            list(
                working_state
                .decision_reevaluation_triggers
            ),
            research_budget=(
                working_state.research_budget
            ),
            research_usage=(
                working_state.research_usage
            ),
            stopping_decision=(
                working_state.stopping_decision
            ),
        )

        response_base = {
            "source_research_id": research_id,
            "status": preparation.assessment.status,
            "eligible": (
                preparation.reactivation.eligible
            ),
            "assessment": _serialize_v3_value(
                preparation.assessment
            ),
            "plan": _serialize_v3_value(
                preparation.plan
            ),
            "reactivation": _serialize_v3_value(
                preparation.reactivation
            ),
        }

        # Assessment/plan are useful even when execution is blocked,
        # but no new research version is created for a no-op.
        if (
            preparation.reactivation.status
            != "ELIGIBLE"
            or not preparation.reactivation.eligible
            or not preparation.reactivation.actionable_gap_ids
        ):
            return ResearchReevaluationResponse(
                **response_base,
                research_id=None,
                executed=False,
            )

        overrides: Dict[str, Any] = {}

        if payload.search_api is not None:
            overrides["search_api"] = (
                payload.search_api
            )

        reevaluation_config = (
            Configuration.from_env(
                overrides=overrides
            )
        )

        agent = DeepResearchAgent(
            config=reevaluation_config
        )

        ensure_llm_available(
            agent,
            reevaluation_config,
        )

        agent.execute_prepared_reevaluation(
            working_state,
            preparation,
        )

        # The historical report describes the old decision state.
        # Generate a fresh report for the new research version.
        report = agent.reporting.generate_report(
            working_state
        )

        working_state.structured_report = report
        working_state.running_summary = report

        # Old report-note references must never point at the newly
        # generated version.
        working_state.report_note_id = None
        working_state.report_note_path = None

        new_research_id = (
            app.state.research_store.save(
                working_state,
                parent_research_id=research_id,
                creation_reason="reevaluation",
                created_from_trigger_ids=list(
                    preparation.assessment.matched_trigger_ids
                ),
            )
        )

        lineage = (
            app.state.research_store.get_lineage(
                new_research_id
            )
        )

        return ResearchReevaluationResponse(
            **response_base,
            research_id=new_research_id,
            executed=True,
            lineage=_serialize_v3_value(
                lineage
            ),
        )


    @app.post("/research", response_model=ResearchResponse)
    def run_research(payload: ResearchRequest) -> ResearchResponse:
        try:
            config = _build_config(payload)
            agent = DeepResearchAgent(config=config)

            ensure_llm_available(
                agent,
                config,
            )

            result = agent.run(payload.topic)

            state = agent.last_state
            if state is None:
                raise RuntimeError("Research state was not captured")

            research_id = app.state.research_store.save(state)
        except HTTPException:
            raise
        except ValueError as exc:  # Likely due to unsupported configuration
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:  # pragma: no cover - defensive guardrail
            logger.exception("Research failed")
            raise HTTPException(
                status_code=500,
                detail="Research failed",
            ) from exc

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

            ensure_llm_available(
                agent,
                config,
            )

        except HTTPException:
            raise
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
