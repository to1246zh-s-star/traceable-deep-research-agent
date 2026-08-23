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
class TechnicalContext:
    """Technical environment and constraints surrounding a decision."""

    existing_stack: list[str] = field(default_factory=list)
    deployment_environment: list[str] = field(default_factory=list)
    infrastructure: list[str] = field(default_factory=list)
    team_capabilities: list[str] = field(default_factory=list)

    scale_requirements: list[str] = field(default_factory=list)
    performance_requirements: list[str] = field(default_factory=list)
    reliability_requirements: list[str] = field(default_factory=list)

    integration_requirements: list[str] = field(default_factory=list)
    operational_constraints: list[str] = field(default_factory=list)
    security_constraints: list[str] = field(default_factory=list)
    compliance_constraints: list[str] = field(default_factory=list)
    migration_constraints: list[str] = field(default_factory=list)
    budget_constraints: list[str] = field(default_factory=list)


@dataclass(kw_only=True)
class IntegrationAssessment:
    """Architecture-fit assessment for one candidate."""

    decision_id: str
    candidate_id: str

    integration_complexity: str = field(default="UNKNOWN")
    migration_complexity: str = field(default="UNKNOWN")
    operational_change: str = field(default="UNKNOWN")
    infrastructure_change: str = field(default="UNKNOWN")

    required_new_dependencies: list[str] = field(default_factory=list)
    affected_components: list[str] = field(default_factory=list)
    team_skill_gaps: list[str] = field(default_factory=list)

    evidence_ids: list[str] = field(default_factory=list)
    rationale: Optional[str] = field(default=None)


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
class SensitivityResult:
    """Deterministic sensitivity result for one decision criterion."""

    decision_id: str
    criterion_id: str

    baseline_weight: float
    baseline_winner_id: str
    score_margin_before: float

    recommendation_changes: bool = field(default=False)

    switch_threshold: Optional[float] = field(default=None)
    weight_delta: Optional[float] = field(default=None)
    direction_of_change: Optional[str] = field(default=None)

    competing_candidate_id: Optional[str] = field(default=None)
    score_margin_after: Optional[float] = field(default=None)


@dataclass(kw_only=True)
class RecommendationRobustness:
    """Deterministic robustness assessment for the current recommendation."""

    decision_id: str

    baseline_winner_id: Optional[str] = field(default=None)
    status: str = field(default="UNKNOWN")

    score_margin: Optional[float] = field(default=None)

    tested_criteria_count: int = field(default=0)
    flip_count: int = field(default=0)
    minimum_flip_delta: Optional[float] = field(default=None)
    minimum_relative_flip_delta: Optional[float] = field(default=None)
    unstable_criterion_ids: list[str] = field(default_factory=list)

    unresolved_candidate_ids: list[str] = field(default_factory=list)
    weak_evidence_candidate_ids: list[str] = field(default_factory=list)
    architecture_unknown_candidate_ids: list[str] = field(default_factory=list)

    readiness_status: Optional[str] = field(default=None)

    reasons: list[str] = field(default_factory=list)


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
class EvidenceSignal:
    """Structured interpretation of Evidence for one candidate criterion."""

    signal_id: str = field(
        default_factory=lambda: f"sig_{uuid.uuid4().hex[:12]}"
    )

    evidence_id: str
    candidate_id: str
    criterion_id: str

    direction: str
    strength: float

    source_confidence: float
    applicability: float

    atomic_claim_id: Optional[str] = field(default=None)
    rationale: Optional[str] = field(default=None)


@dataclass(kw_only=True)
class CriterionCoverage:
    """Evidence coverage for one candidate × criterion pair."""

    candidate_id: str
    criterion_id: str

    signal_count: int
    effective_signal_count: float

    coverage_score: float
    confidence_score: float


@dataclass(kw_only=True)
class EvidenceConflict:
    """Supporting and opposing evidence disagreement."""

    candidate_id: str
    criterion_id: str

    supporting_signal_ids: list[str] = field(default_factory=list)
    opposing_signal_ids: list[str] = field(default_factory=list)

    conflict_score: float = field(default=0.0)
    resolution_status: str = field(default="none")


@dataclass(kw_only=True)
class ResearchGap:
    """Missing or weak research discovered during evaluation."""

    gap_id: str = field(
        default_factory=lambda: f"gap_{uuid.uuid4().hex[:12]}"
    )

    candidate_id: str
    criterion_id: str

    gap_type: str
    severity: float

    description: str
    suggested_query: Optional[str] = field(default=None)

    # Phase 17.5 decision-impact enrichment.
    # priority is ordinal routing metadata, not a probability.
    decision_impact: str = field(default="UNKNOWN")
    priority: int = field(default=0)
    impact_reasons: list[str] = field(default_factory=list)
    context_dimensions: list[str] = field(default_factory=list)

    status: str = field(default="open")


@dataclass(kw_only=True)
class ResearchAnalysis:
    """Phase 11 analysis across decision evidence signals."""

    decision_id: str

    coverages: list[CriterionCoverage] = field(default_factory=list)
    conflicts: list[EvidenceConflict] = field(default_factory=list)
    research_gaps: list[ResearchGap] = field(default_factory=list)

    status: str = field(default="complete")

    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


@dataclass(kw_only=True)
class AdaptiveResearchIteration:
    """One bounded adaptive follow-up research iteration."""

    iteration_id: str = field(
        default_factory=lambda: f"iter_{uuid.uuid4().hex[:12]}"
    )

    decision_id: str
    iteration_number: int

    gap_ids: list[str] = field(default_factory=list)
    task_ids: list[int] = field(default_factory=list)

    status: str = field(default="planned")

    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


@dataclass(kw_only=True)
class AdaptiveResearchState:
    """Tracks adaptive replanning progress and stopping state."""

    decision_id: str

    iteration_count: int = field(default=0)
    max_iterations: int = field(default=3)

    executed_gap_ids: list[str] = field(default_factory=list)
    executed_queries: list[str] = field(default_factory=list)

    iterations: list[AdaptiveResearchIteration] = field(
        default_factory=list
    )

    status: str = field(default="active")


@dataclass(kw_only=True)
class DecisionReadiness:
    """Explainable heuristic readiness assessment for a technical decision."""

    decision_id: str

    overall_score: float
    status: str

    criterion_coverage: float
    evidence_quality: float
    applicability: float
    agreement_score: float
    decision_margin: float

    blocking_reasons: list[str] = field(default_factory=list)
    research_gap_ids: list[str] = field(default_factory=list)

    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


@dataclass(kw_only=True)
class ResearchBudget:
    """Bounded research budget for adaptive V3 iterations."""

    max_iterations: int = field(default=3)
    max_tasks: int = field(default=9)
    max_searches: Optional[int] = field(default=None)
    max_duration_seconds: Optional[float] = field(default=None)
    max_tokens: Optional[int] = field(default=None)
    max_cost: Optional[float] = field(default=None)


@dataclass(kw_only=True)
class ResearchUsage:
    """Observed resource usage for one adaptive decision workflow."""

    iterations: int = field(default=0)
    tasks: int = field(default=0)
    searches: int = field(default=0)
    duration_seconds: float = field(default=0.0)
    tokens: int = field(default=0)
    cost: float = field(default=0.0)

    # Actual provider invocations performed by V3 decision intelligence.
    # Retries are counted because they consume real provider quota.
    semantic_llm_calls: int = field(default=0)
    constraint_llm_calls: int = field(default=0)


@dataclass(kw_only=True)
class ReadinessSnapshot:
    """Readiness score captured after one research iteration."""

    iteration_number: int
    overall_score: float
    status: str


@dataclass(kw_only=True)
class ResearchStoppingDecision:
    """Explainable continue/stop decision for adaptive research."""

    should_continue: bool
    reason: str

    readiness_score: float
    readiness_status: str

    readiness_improvement: Optional[float] = field(default=None)
    actionable_gap_count: int = field(default=0)

    blocking_budget_limits: list[str] = field(default_factory=list)


@dataclass(kw_only=True)
class InternalDocument:
    """Internal engineering knowledge available to V3 retrieval."""

    document_id: str = field(
        default_factory=lambda: f"doc_{uuid.uuid4().hex[:12]}"
    )

    title: str
    content: str

    source_type: str = field(default="internal_document")
    source_path: Optional[str] = field(default=None)

    metadata: dict[str, Any] = field(default_factory=dict)

    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


@dataclass(kw_only=True)
class InternalRetrievalHit:
    """One ranked internal-knowledge retrieval result."""

    document_id: str

    score: float
    matched_terms: list[str] = field(default_factory=list)


@dataclass(kw_only=True)
class HybridRetrievalResult:
    """Unified result containing internal and external Evidence."""

    query: str

    evidence_items: list[Evidence] = field(default_factory=list)

    internal_count: int = field(default=0)
    external_count: int = field(default=0)

    duplicate_count: int = field(default=0)

    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


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

    # V3 Technical Decision Intelligence state
    decision_case: Optional[DecisionCase] = field(default=None)
    technical_context: Optional[TechnicalContext] = field(default=None)
    integration_assessments: list[IntegrationAssessment] = field(
        default_factory=list
    )

    decision_evaluation: Optional[DecisionEvaluation] = field(default=None)
    decision_comparison: Optional[DecisionComparison] = field(default=None)
    decision_sensitivity: list[SensitivityResult] = field(default_factory=list)
    recommendation_robustness: Optional[RecommendationRobustness] = field(
        default=None
    )

    atomic_claims: list[AtomicClaim] = field(default_factory=list)
    evidence_assessments: list[EvidenceAssessment] = field(default_factory=list)
    evidence_signals: list[EvidenceSignal] = field(default_factory=list)

    research_analysis: Optional[ResearchAnalysis] = field(default=None)
    adaptive_research_state: Optional[AdaptiveResearchState] = field(default=None)

    decision_readiness: Optional[DecisionReadiness] = field(default=None)

    research_budget: Optional[ResearchBudget] = field(default=None)
    research_usage: Optional[ResearchUsage] = field(default=None)
    readiness_history: list[ReadinessSnapshot] = field(default_factory=list)
    stopping_decision: Optional[ResearchStoppingDecision] = field(default=None)

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

