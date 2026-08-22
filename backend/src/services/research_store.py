"""In-memory storage for completed or active research states."""

from __future__ import annotations

import json
from dataclasses import fields, is_dataclass
import sqlite3
import uuid
from pathlib import Path
from threading import Lock
from typing import Protocol

from models import (
    AdaptiveResearchIteration,
    AdaptiveResearchState,
    AtomicClaim,
    Candidate,
    CandidateCriterionScore,
    CandidateDecisionResult,
    CandidateWeightedScore,
    Claim,
    Constraint,
    CriterionCoverage,
    DecisionCase,
    DecisionComparison,
    DecisionCriterion,
    DecisionEvaluation,
    DecisionReadiness,
    SensitivityResult,
    Evidence,
    EvidenceApplicability,
    EvidenceAssessment,
    EvidenceConflict,
    EvidenceQuality,
    EvidenceSignal,
    ExecutionEvent,
    IntegrationAssessment,
    ExecutionTrace,
    ReadinessSnapshot,
    Requirement,
    ResearchAnalysis,
    ResearchBudget,
    ResearchGap,
    ResearchStoppingDecision,
    ResearchUsage,
    SourceDiversity,
    SourceQuality,
    SummaryState,
    TechnicalContext,
    TodoItem,

    RecommendationRobustness,)


V3_MODEL_TYPES = {
    cls.__name__: cls
    for cls in (
        AdaptiveResearchIteration,
        AdaptiveResearchState,
        AtomicClaim,
        Candidate,
        CandidateCriterionScore,
        CandidateDecisionResult,
        CandidateWeightedScore,
        Constraint,
        CriterionCoverage,
        DecisionCase,
        DecisionComparison,
        DecisionCriterion,
        DecisionEvaluation,
        DecisionReadiness,
        SensitivityResult,
    RecommendationRobustness,
        EvidenceApplicability,
        EvidenceAssessment,
        EvidenceConflict,
        EvidenceQuality,
        EvidenceSignal,
        IntegrationAssessment,
        ReadinessSnapshot,
        Requirement,
        ResearchAnalysis,
        ResearchBudget,
        ResearchGap,
        ResearchStoppingDecision,
        ResearchUsage,
        SourceDiversity,
        SourceQuality,
        TechnicalContext,
    )
}


V3_STATE_FIELDS = (
    "decision_case",
    "technical_context",
    "integration_assessments",
    "decision_evaluation",
    "decision_comparison",
    "decision_sensitivity",
    "recommendation_robustness",
    "atomic_claims",
    "evidence_assessments",
    "evidence_signals",
    "research_analysis",
    "adaptive_research_state",
    "decision_readiness",
    "research_budget",
    "research_usage",
    "readiness_history",
    "stopping_decision",
)


def _encode_v3_value(value):
    """Recursively encode V3 dataclasses while preserving concrete types."""

    if is_dataclass(value):
        return {
            "__type__": type(value).__name__,
            "__data__": {
                item.name: _encode_v3_value(
                    getattr(value, item.name)
                )
                for item in fields(value)
            },
        }

    if isinstance(value, list):
        return [
            _encode_v3_value(item)
            for item in value
        ]

    if isinstance(value, tuple):
        return {
            "__tuple__": [
                _encode_v3_value(item)
                for item in value
            ]
        }

    if isinstance(value, dict):
        return {
            str(key): _encode_v3_value(item)
            for key, item in value.items()
        }

    return value


def _decode_v3_value(value):
    """Reconstruct V3 dataclasses encoded by _encode_v3_value()."""

    if isinstance(value, list):
        return [
            _decode_v3_value(item)
            for item in value
        ]

    if not isinstance(value, dict):
        return value

    if "__tuple__" in value:
        return tuple(
            _decode_v3_value(item)
            for item in value["__tuple__"]
        )

    type_name = value.get("__type__")

    if type_name is not None:
        model_type = V3_MODEL_TYPES.get(type_name)

        if model_type is None:
            raise ValueError(
                f"Unknown persisted V3 model type: {type_name}"
            )

        payload = {
            key: _decode_v3_value(item)
            for key, item in value["__data__"].items()
        }

        return model_type(**payload)

    return {
        key: _decode_v3_value(item)
        for key, item in value.items()
    }


def _serialize_v3_state(state: SummaryState) -> str:
    """Serialize all V3 decision-intelligence state into one JSON payload."""

    payload = {
        field_name: _encode_v3_value(
            getattr(state, field_name)
        )
        for field_name in V3_STATE_FIELDS
    }

    return json.dumps(
        payload,
        ensure_ascii=False,
    )


def _deserialize_v3_state(raw: str | None) -> dict:
    """Deserialize persisted V3 state with backward-compatible defaults."""

    if not raw:
        return {}

    payload = json.loads(raw)

    return {
        key: _decode_v3_value(value)
        for key, value in payload.items()
        if key in V3_STATE_FIELDS
    }


class ResearchStore(Protocol):
    """Storage contract for research states."""

    def save(self, state: SummaryState) -> str:
        """Store a research state and return its research id."""
        ...

    def get(self, research_id: str) -> SummaryState | None:
        """Return a stored research state, if present."""
        ...

    def list(self) -> list[tuple[str, SummaryState]]:
        """Return stored research states."""
        ...


class SQLiteResearchStore:
    """SQLite-backed persistent store for research states."""

    def __init__(self, db_path: str | Path) -> None:
        self._db_path = Path(db_path)
        self._lock = Lock()
        self._initialize_schema()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _initialize_schema(self) -> None:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)

        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS research_runs (
                    research_id TEXT PRIMARY KEY,
                    research_topic TEXT,
                    search_query TEXT,
                    research_loop_count INTEGER NOT NULL DEFAULT 0,
                    running_summary TEXT,
                    structured_report TEXT,
                    report_note_id TEXT,
                    report_note_path TEXT
                );

                CREATE TABLE IF NOT EXISTS todo_items (
                    research_id TEXT NOT NULL,
                    task_id INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    intent TEXT NOT NULL,
                    query TEXT NOT NULL,
                    status TEXT NOT NULL,
                    summary TEXT,
                    sources_summary TEXT,
                    notices_json TEXT NOT NULL,
                    note_id TEXT,
                    note_path TEXT,
                    stream_token TEXT,
                    PRIMARY KEY (research_id, task_id),
                    FOREIGN KEY (research_id)
                        REFERENCES research_runs(research_id)
                        ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS execution_traces (
                    trace_id TEXT NOT NULL,
                    research_id TEXT NOT NULL,
                    task_id INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    started_at TEXT,
                    finished_at TEXT,
                    duration_ms REAL,
                    current_stage TEXT,
                    retry_count INTEGER NOT NULL DEFAULT 0,
                    error_type TEXT,
                    error_message TEXT,
                    PRIMARY KEY (research_id, trace_id),
                    FOREIGN KEY (research_id)
                        REFERENCES research_runs(research_id)
                        ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS evidence_items (
                research_id TEXT NOT NULL,
                evidence_id TEXT NOT NULL,
                task_id INTEGER NOT NULL,
                trace_id TEXT NOT NULL,
                query TEXT NOT NULL,
                backend TEXT NOT NULL,
                source_title TEXT,
                source_url TEXT,
                snippet TEXT,
                content TEXT,
                source_rank INTEGER,
                created_at TEXT NOT NULL,
                PRIMARY KEY (research_id, evidence_id),
                FOREIGN KEY (research_id)
                    REFERENCES research_runs(research_id)
                    ON DELETE CASCADE,
                FOREIGN KEY (research_id, trace_id)
                    REFERENCES execution_traces(research_id, trace_id)
                    ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS claims (
                research_id TEXT NOT NULL,
                claim_id TEXT NOT NULL,
                task_id INTEGER NOT NULL,
                trace_id TEXT NOT NULL,
                text TEXT NOT NULL,
                evidence_ids TEXT NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY (research_id, claim_id),
                FOREIGN KEY (research_id)
                    REFERENCES research_runs(research_id)
                    ON DELETE CASCADE,
                FOREIGN KEY (research_id, trace_id)
                    REFERENCES execution_traces(research_id, trace_id)
                    ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS execution_events (
                    event_id TEXT NOT NULL,
                    research_id TEXT NOT NULL,
                    trace_id TEXT NOT NULL,
                    task_id INTEGER NOT NULL,
                    schema_version INTEGER NOT NULL,
                    timestamp TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    stage TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    PRIMARY KEY (research_id, event_id),
                    FOREIGN KEY (research_id)
                        REFERENCES research_runs(research_id)
                        ON DELETE CASCADE,
                    FOREIGN KEY (research_id, trace_id)
                        REFERENCES execution_traces(
                            research_id,
                            trace_id
                        )
                        ON DELETE CASCADE
                );
                """
            )

        with self._connect() as connection:
            columns = {
                row["name"]
                for row in connection.execute(
                    "PRAGMA table_info(research_runs)"
                ).fetchall()
            }

            if "v3_state_json" not in columns:
                connection.execute(
                    "ALTER TABLE research_runs "
                    "ADD COLUMN v3_state_json TEXT"
                )
                connection.commit()

    def save(self, state: SummaryState) -> str:
        """Persist one complete research state and return its research id."""

        research_id = f"research_{uuid.uuid4().hex[:12]}"

        with self._lock:
            with self._connect() as connection:
                connection.execute(
                    """
                    INSERT INTO research_runs (
                        research_id,
                        research_topic,
                        search_query,
                        research_loop_count,
                        running_summary,
                        structured_report,
                        report_note_id,
                        report_note_path
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        research_id,
                        state.research_topic,
                        state.search_query,
                        state.research_loop_count,
                        state.running_summary,
                        state.structured_report,
                        state.report_note_id,
                        state.report_note_path,
                    ),
                )

                connection.executemany(
                    """
                    INSERT INTO todo_items (
                        research_id,
                        task_id,
                        title,
                        intent,
                        query,
                        status,
                        summary,
                        sources_summary,
                        notices_json,
                        note_id,
                        note_path,
                        stream_token
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        (
                            research_id,
                            item.id,
                            item.title,
                            item.intent,
                            item.query,
                            item.status,
                            item.summary,
                            item.sources_summary,
                            json.dumps(item.notices, ensure_ascii=False),
                            item.note_id,
                            item.note_path,
                            item.stream_token,
                        )
                        for item in state.todo_items
                    ],
                )

                connection.executemany(
                    """
                    INSERT INTO execution_traces (
                        trace_id,
                        research_id,
                        task_id,
                        status,
                        started_at,
                        finished_at,
                        duration_ms,
                        current_stage,
                        retry_count,
                        error_type,
                        error_message
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        (
                            trace.trace_id,
                            research_id,
                            trace.task_id,
                            trace.status,
                            trace.started_at,
                            trace.finished_at,
                            trace.duration_ms,
                            trace.current_stage,
                            trace.retry_count,
                            trace.error_type,
                            trace.error_message,
                        )
                        for trace in state.execution_traces
                    ],
                )

                connection.executemany(
                    """
                    INSERT INTO evidence_items (
                        research_id,
                        evidence_id,
                        task_id,
                        trace_id,
                        query,
                        backend,
                        source_title,
                        source_url,
                        snippet,
                        content,
                        source_rank,
                        created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        (
                            research_id,
                            evidence.evidence_id,
                            evidence.task_id,
                            evidence.trace_id,
                            evidence.query,
                            evidence.backend,
                            evidence.source_title,
                            evidence.source_url,
                            evidence.snippet,
                            evidence.content,
                            evidence.source_rank,
                            evidence.created_at,
                        )
                        for evidence in state.evidence_items
                    ],
                )

                connection.executemany(
                    """
                    INSERT INTO claims (
                        research_id,
                        claim_id,
                        task_id,
                        trace_id,
                        text,
                        evidence_ids,
                        created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        (
                            research_id,
                            claim.claim_id,
                            claim.task_id,
                            claim.trace_id,
                            claim.text,
                            json.dumps(
                                claim.evidence_ids,
                                ensure_ascii=False,
                            ),
                            claim.created_at,
                        )
                        for claim in state.claims
                    ],
                )

                connection.executemany(
                    """
                    INSERT INTO execution_events (
                        event_id,
                        research_id,
                        trace_id,
                        task_id,
                        schema_version,
                        timestamp,
                        event_type,
                        stage,
                        metadata_json
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        (
                            event.event_id,
                            research_id,
                            event.trace_id,
                            event.task_id,
                            event.schema_version,
                            event.timestamp,
                            event.event_type,
                            event.stage,
                            json.dumps(event.metadata, ensure_ascii=False),
                        )
                        for event in state.execution_event_history
                    ],
                )

        with self._lock:
            with self._connect() as connection:
                connection.execute(
                    """
                    UPDATE research_runs
                    SET v3_state_json = ?
                    WHERE research_id = ?
                    """,
                    (
                        _serialize_v3_state(state),
                        research_id,
                    ),
                )
                connection.commit()

        return research_id

    def get(self, research_id: str) -> SummaryState | None:
        """Load and reconstruct one research state."""

        with self._lock:
            with self._connect() as connection:
                research_row = connection.execute(
                    """
                    SELECT
                        research_topic,
                        search_query,
                        research_loop_count,
                        running_summary,
                        structured_report,
                        report_note_id,
                        report_note_path,
                        v3_state_json
                    FROM research_runs
                    WHERE research_id = ?
                    """,
                    (research_id,),
                ).fetchone()

                if research_row is None:
                    return None

                todo_rows = connection.execute(
                    """
                    SELECT
                        task_id,
                        title,
                        intent,
                        query,
                        status,
                        summary,
                        sources_summary,
                        notices_json,
                        note_id,
                        note_path,
                        stream_token
                    FROM todo_items
                    WHERE research_id = ?
                    ORDER BY task_id
                    """,
                    (research_id,),
                ).fetchall()

                trace_rows = connection.execute(
                    """
                    SELECT
                        trace_id,
                        task_id,
                        status,
                        started_at,
                        finished_at,
                        duration_ms,
                        current_stage,
                        retry_count,
                        error_type,
                        error_message
                    FROM execution_traces
                    WHERE research_id = ?
                    ORDER BY task_id, trace_id
                    """,
                    (research_id,),
                ).fetchall()

                evidence_rows = connection.execute(
                    """
                    SELECT
                        evidence_id,
                        task_id,
                        trace_id,
                        query,
                        backend,
                        source_title,
                        source_url,
                        snippet,
                        content,
                        source_rank,
                        created_at
                    FROM evidence_items
                    WHERE research_id = ?
                    ORDER BY task_id, source_rank, evidence_id
                    """,
                    (research_id,),
                ).fetchall()

                claim_rows = connection.execute(
                    """
                    SELECT
                        claim_id,
                        task_id,
                        trace_id,
                        text,
                        evidence_ids,
                        created_at
                    FROM claims
                    WHERE research_id = ?
                    ORDER BY task_id, claim_id
                    """,
                    (research_id,),
                ).fetchall()

                event_rows = connection.execute(
                    """
                    SELECT
                        event_id,
                        trace_id,
                        task_id,
                        schema_version,
                        timestamp,
                        event_type,
                        stage,
                        metadata_json
                    FROM execution_events
                    WHERE research_id = ?
                    ORDER BY timestamp, event_id
                    """,
                    (research_id,),
                ).fetchall()

        todo_items = [
            TodoItem(
                id=row["task_id"],
                title=row["title"],
                intent=row["intent"],
                query=row["query"],
                status=row["status"],
                summary=row["summary"],
                sources_summary=row["sources_summary"],
                notices=json.loads(row["notices_json"]),
                note_id=row["note_id"],
                note_path=row["note_path"],
                stream_token=row["stream_token"],
            )
            for row in todo_rows
        ]

        execution_traces = [
            ExecutionTrace(
                trace_id=row["trace_id"],
                task_id=row["task_id"],
                status=row["status"],
                started_at=row["started_at"],
                finished_at=row["finished_at"],
                duration_ms=row["duration_ms"],
                current_stage=row["current_stage"],
                retry_count=row["retry_count"],
                error_type=row["error_type"],
                error_message=row["error_message"],
            )
            for row in trace_rows
        ]

        evidence_items = [
            Evidence(
                evidence_id=row["evidence_id"],
                task_id=row["task_id"],
                trace_id=row["trace_id"],
                query=row["query"],
                backend=row["backend"],
                source_title=row["source_title"],
                source_url=row["source_url"],
                snippet=row["snippet"],
                content=row["content"],
                source_rank=row["source_rank"],
                created_at=row["created_at"],
            )
            for row in evidence_rows
        ]

        claims = [
            Claim(
                claim_id=row["claim_id"],
                task_id=row["task_id"],
                trace_id=row["trace_id"],
                text=row["text"],
                evidence_ids=json.loads(row["evidence_ids"]),
                created_at=row["created_at"],
            )
            for row in claim_rows
        ]

        execution_event_history = [
            ExecutionEvent(
                event_id=row["event_id"],
                trace_id=row["trace_id"],
                task_id=row["task_id"],
                schema_version=row["schema_version"],
                timestamp=row["timestamp"],
                event_type=row["event_type"],
                stage=row["stage"],
                metadata=json.loads(row["metadata_json"]),
            )
            for row in event_rows
        ]

        v3_state = _deserialize_v3_state(
            research_row["v3_state_json"]
        )

        return SummaryState(
            research_topic=research_row["research_topic"],
            search_query=research_row["search_query"],
            research_loop_count=research_row["research_loop_count"],
            running_summary=research_row["running_summary"],
            todo_items=todo_items,
            execution_traces=execution_traces,
            execution_events=[],
            execution_event_history=execution_event_history,
            evidence_items=evidence_items,
            claims=claims,
            structured_report=research_row["structured_report"],
            report_note_id=research_row["report_note_id"],
            report_note_path=research_row["report_note_path"],
            **v3_state,
        )

    def list(self) -> list[tuple[str, SummaryState]]:
        """Return all stored research states."""

        with self._lock:
            with self._connect() as connection:
                rows = connection.execute(
                    """
                    SELECT research_id
                    FROM research_runs
                    ORDER BY rowid
                    """
                ).fetchall()

        result: list[tuple[str, SummaryState]] = []

        for row in rows:
            state = self.get(row["research_id"])
            if state is not None:
                result.append((row["research_id"], state))

        return result



class InMemoryResearchStore:
    """Thread-safe in-memory store for research states."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._states: dict[str, SummaryState] = {}

    def save(self, state: SummaryState) -> str:
        """Store a research state and return its generated research id."""

        research_id = f"research_{uuid.uuid4().hex[:12]}"

        with self._lock:
            self._states[research_id] = state

        return research_id

    def get(self, research_id: str) -> SummaryState | None:
        """Return the stored state for a research id, if present."""

        with self._lock:
            return self._states.get(research_id)

    def list(self) -> list[tuple[str, SummaryState]]:
        """Return stored research states in insertion order."""

        with self._lock:
            return list(self._states.items())
