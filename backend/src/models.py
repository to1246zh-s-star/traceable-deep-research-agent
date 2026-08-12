"""State models used by the deep research workflow."""

import operator
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, List, Optional

from typing_extensions import Annotated


@dataclass(kw_only=True)
class TodoItem:
    """单个待办任务项。"""

    id: int
    title: str
    intent: str
    query: str
    status: str = field(default="pending")
    summary: Optional[str] = field(default=None)
    sources_summary: Optional[str] = field(default=None)
    notices: list[str] = field(default_factory=list)
    note_id: Optional[str] = field(default=None)
    note_path: Optional[str] = field(default=None)
    stream_token: Optional[str] = field(default=None)


@dataclass(kw_only=True)
class Evidence:
    """Structured evidence captured from one retrieved source."""

    evidence_id: str = field(
        default_factory=lambda: f"evi_{uuid.uuid4().hex[:12]}"
    )

    task_id: int
    trace_id: str

    query: str
    backend: str

    source_title: Optional[str] = field(default=None)
    source_url: Optional[str] = field(default=None)
    snippet: Optional[str] = field(default=None)
    content: Optional[str] = field(default=None)

    source_rank: Optional[int] = field(default=None)

    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


@dataclass(kw_only=True)
class Claim:
    """Research claim supported by retrieved evidence."""

    claim_id: str = field(
        default_factory=lambda: f"clm_{uuid.uuid4().hex[:12]}"
    )

    task_id: int
    trace_id: str

    text: str
    evidence_ids: list[str] = field(default_factory=list)

    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


@dataclass(kw_only=True)
class AtomicClaim:
    """Fine-grained factual claim grounded in specific Evidence."""

    atomic_claim_id: str = field(
        default_factory=lambda: f"aclm_{uuid.uuid4().hex[:12]}"
    )

    parent_claim_id: str

    task_id: int
    trace_id: str

    text: str
    evidence_ids: list[str] = field(default_factory=list)

    grounding_status: str = field(default="ungrounded")

    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


@dataclass(kw_only=True)
class ExecutionTrace:
    """Runtime trace for a single TODO task execution."""

    trace_id: str = field(
        default_factory=lambda: f"trace_{uuid.uuid4().hex[:12]}"
    )

    task_id: int
    status: str = field(default="pending")
    started_at: Optional[str] = field(default=None)
    finished_at: Optional[str] = field(default=None)
    duration_ms: Optional[float] = field(default=None)
    current_stage: Optional[str] = field(default=None)
    retry_count: int = field(default=0)
    error_type: Optional[str] = field(default=None)
    error_message: Optional[str] = field(default=None)


@dataclass(kw_only=True)
class ExecutionEvent:
    """Single runtime event emitted during task execution."""

    trace_id: str = field(
        default="trace_unknown"
    )

    task_id: int
    event_type: str
    stage: str

    schema_version: int = field(default=1)

    event_id: str = field(
        default_factory=lambda: f"evt_{uuid.uuid4().hex[:12]}"
    )

    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(kw_only=True)
class Candidate:
    """Technology candidate considered in a decision case."""

    candidate_id: str = field(
        default_factory=lambda: f"cand_{uuid.uuid4().hex[:12]}"
    )

    name: str
    description: Optional[str] = field(default=None)


@dataclass(kw_only=True)
class Requirement:
    """User requirement relevant to a technical decision."""

    requirement_id: str = field(
        default_factory=lambda: f"req_{uuid.uuid4().hex[:12]}"
    )

    text: str


@dataclass(kw_only=True)
class Constraint:
    """Hard constraint that a candidate must satisfy."""

    constraint_id: str = field(
        default_factory=lambda: f"con_{uuid.uuid4().hex[:12]}"
    )

    text: str
    source: str = field(default="user")


@dataclass(kw_only=True)
class DecisionCriterion:
    """Weighted criterion used to compare eligible candidates."""

    criterion_id: str = field(
        default_factory=lambda: f"crit_{uuid.uuid4().hex[:12]}"
    )

    name: str
    weight: float
    source: str = field(default="user")
    description: Optional[str] = field(default=None)


@dataclass(kw_only=True)
class DecisionCase:
    """Structured representation of a technical decision problem."""

    decision_id: str = field(
        default_factory=lambda: f"dec_{uuid.uuid4().hex[:12]}"
    )

    question: str
    context: Optional[str] = field(default=None)

    candidates: list[Candidate] = field(default_factory=list)
    requirements: list[Requirement] = field(default_factory=list)
    constraints: list[Constraint] = field(default_factory=list)
    criteria: list[DecisionCriterion] = field(default_factory=list)

    status: str = field(default="draft")
    recommendation: Optional[str] = field(default=None)

    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


@dataclass(kw_only=True)
class CandidateDecisionResult:
    """Deterministic hard-constraint evaluation for one candidate."""

    candidate_id: str

    status: str
    violated_constraint_ids: list[str] = field(default_factory=list)
    missing_constraint_ids: list[str] = field(default_factory=list)


@dataclass(kw_only=True)
class DecisionEvaluation:
    """Baseline deterministic evaluation of a DecisionCase."""

    decision_id: str

    status: str
    candidate_results: list[CandidateDecisionResult] = field(
        default_factory=list
    )

    eligible_candidate_ids: list[str] = field(default_factory=list)
    disqualified_candidate_ids: list[str] = field(default_factory=list)
    unresolved_candidate_ids: list[str] = field(default_factory=list)

    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


@dataclass(kw_only=True)
class CandidateCriterionScore:
    """Fitness of one candidate under one decision criterion."""

    candidate_id: str
    criterion_id: str

    fitness_score: float
    rationale: Optional[str] = field(default=None)


@dataclass(kw_only=True)
class CandidateWeightedScore:
    """Deterministic weighted score for one eligible candidate."""

    candidate_id: str
    weighted_score: float

    criterion_scores: list[CandidateCriterionScore] = field(
        default_factory=list
    )

    rank: Optional[int] = field(default=None)


@dataclass(kw_only=True)
class DecisionComparison:
    """Deterministic comparison result across eligible candidates."""

    decision_id: str

    status: str

    candidate_scores: list[CandidateWeightedScore] = field(
        default_factory=list
    )

    ranked_candidate_ids: list[str] = field(default_factory=list)
    excluded_candidate_ids: list[str] = field(default_factory=list)
    unresolved_candidate_ids: list[str] = field(default_factory=list)

    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


@dataclass(kw_only=True)
class SourceQuality:
    """Quality assessment for the source behind one Evidence item."""

    evidence_id: str

    source_type: str
    confidence: float

    rationale: Optional[str] = field(default=None)


@dataclass(kw_only=True)
class EvidenceQuality:
    """Intrinsic quality assessment for one Evidence item."""

    evidence_id: str

    quality_score: float
    completeness: float

    rationale: Optional[str] = field(default=None)


@dataclass(kw_only=True)
class EvidenceApplicability:
    """Applicability of Evidence to the current DecisionCase."""

    evidence_id: str
    decision_id: str

    applicability_score: float

    rationale: Optional[str] = field(default=None)


@dataclass(kw_only=True)
class EvidenceAssessment:
    """Combined Phase 9 assessment for one Evidence item."""

    evidence_id: str
    decision_id: str

    source_quality: SourceQuality
    evidence_quality: EvidenceQuality
    applicability: EvidenceApplicability

    overall_score: float


@dataclass(kw_only=True)
class SourceDiversity:
    """Diversity summary across a set of assessed Evidence items."""

    evidence_count: int
    source_type_count: int

    diversity_score: float

    source_types: list[str] = field(default_factory=list)


@dataclass(kw_only=True)
class SummaryState:
    research_topic: str = field(default=None)  # Report topic
    search_query: str = field(default=None)  # Deprecated placeholder
    web_research_results: Annotated[list, operator.add] = field(default_factory=list)
    sources_gathered: Annotated[list, operator.add] = field(default_factory=list)
    research_loop_count: int = field(default=0)  # Research loop count
    running_summary: str = field(default=None)  # Legacy summary field
    todo_items: Annotated[list, operator.add] = field(default_factory=list)
    execution_traces: list[ExecutionTrace] = field(default_factory=list)
    execution_events: list[ExecutionEvent] = field(default_factory=list)
    execution_event_history: list[ExecutionEvent] = field(default_factory=list)
    evidence_items: list[Evidence] = field(default_factory=list)
    claims: list[Claim] = field(default_factory=list)
    structured_report: Optional[str] = field(default=None)
    report_note_id: Optional[str] = field(default=None)
    report_note_path: Optional[str] = field(default=None)


@dataclass(kw_only=True)
class SummaryStateInput:
    research_topic: str = field(default=None)  # Report topic


@dataclass(kw_only=True)
class SummaryStateOutput:
    running_summary: str = field(default=None)  # Backward-compatible文本
    report_markdown: Optional[str] = field(default=None)
    todo_items: List[TodoItem] = field(default_factory=list)

