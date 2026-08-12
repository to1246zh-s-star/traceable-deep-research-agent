"""Explainable decision-readiness scoring for V3 Phase 13."""

from models import (
    DecisionCase,
    DecisionComparison,
    DecisionReadiness,
    EvidenceAssessment,
    ResearchAnalysis,
)


READY_THRESHOLD = 0.75
TENTATIVE_THRESHOLD = 0.55

CRITICAL_COVERAGE_THRESHOLD = 0.60
CRITICAL_CONFIDENCE_THRESHOLD = 0.55

COVERAGE_WEIGHT = 0.25
EVIDENCE_QUALITY_WEIGHT = 0.25
APPLICABILITY_WEIGHT = 0.20
AGREEMENT_WEIGHT = 0.15
DECISION_MARGIN_WEIGHT = 0.15


def calculate_decision_margin(
    comparison: DecisionComparison,
) -> float:
    """
    Calculate normalized margin between the top two candidates.

    Weighted candidate scores use a 0-10 fitness scale, so the raw
    difference is normalized by 10.

    A single eligible candidate receives maximum margin.
    """

    if comparison.status != "complete":
        return 0.0

    if not comparison.candidate_scores:
        return 0.0

    if len(comparison.candidate_scores) == 1:
        return 1.0

    ranked = sorted(
        comparison.candidate_scores,
        key=lambda score: (
            score.rank if score.rank is not None else 10**9
        ),
    )

    first = ranked[0].weighted_score
    second = ranked[1].weighted_score

    return min(
        1.0,
        max(
            0.0,
            (first - second) / 10.0,
        ),
    )


def aggregate_criterion_coverage(
    analysis: ResearchAnalysis,
) -> float:
    """Average coverage across candidate × criterion pairs."""

    if not analysis.coverages:
        return 0.0

    return sum(
        coverage.coverage_score
        for coverage in analysis.coverages
    ) / len(analysis.coverages)


def aggregate_evidence_quality(
    assessments: list[EvidenceAssessment],
) -> float:
    """
    Average intrinsic evidence quality.

    Source confidence is included so the result reflects both source
    trustworthiness and evidence completeness.
    """

    if not assessments:
        return 0.0

    values = [
        assessment.source_quality.confidence
        * assessment.evidence_quality.quality_score
        for assessment in assessments
    ]

    return sum(values) / len(values)


def aggregate_applicability(
    assessments: list[EvidenceAssessment],
) -> float:
    """Average workload/context applicability across evidence."""

    if not assessments:
        return 0.0

    return sum(
        assessment.applicability.applicability_score
        for assessment in assessments
    ) / len(assessments)


def aggregate_agreement(
    analysis: ResearchAnalysis,
) -> float:
    """
    Convert conflict into agreement.

    1.0 means no meaningful conflict.
    0.0 means maximum average conflict.
    """

    if not analysis.conflicts:
        return 1.0

    average_conflict = sum(
        conflict.conflict_score
        for conflict in analysis.conflicts
    ) / len(analysis.conflicts)

    return max(
        0.0,
        1.0 - average_conflict,
    )


def find_critical_criterion_blockers(
    decision: DecisionCase,
    analysis: ResearchAnalysis,
) -> list[str]:
    """
    Block readiness when important criteria have weak evidence.

    Phase 13 baseline treats the highest-weight criterion or criteria
    as critical.
    """

    if not decision.criteria:
        return []

    max_weight = max(
        criterion.weight
        for criterion in decision.criteria
    )

    critical_ids = {
        criterion.criterion_id
        for criterion in decision.criteria
        if criterion.weight == max_weight
    }

    criterion_names = {
        criterion.criterion_id: criterion.name
        for criterion in decision.criteria
    }

    blockers: list[str] = []

    for coverage in analysis.coverages:
        if coverage.criterion_id not in critical_ids:
            continue

        if (
            coverage.coverage_score
            < CRITICAL_COVERAGE_THRESHOLD
        ):
            blockers.append(
                f"critical criterion "
                f"{criterion_names[coverage.criterion_id]!r} "
                f"has insufficient coverage"
            )

        if (
            coverage.confidence_score
            < CRITICAL_CONFIDENCE_THRESHOLD
        ):
            blockers.append(
                f"critical criterion "
                f"{criterion_names[coverage.criterion_id]!r} "
                f"has insufficient confidence"
            )

    return sorted(set(blockers))


def calculate_readiness(
    decision: DecisionCase,
    comparison: DecisionComparison,
    analysis: ResearchAnalysis,
    evidence_assessments: list[EvidenceAssessment],
) -> DecisionReadiness:
    """
    Calculate explainable heuristic decision readiness.

    This score is NOT a calibrated probability.
    """

    if comparison.decision_id != decision.decision_id:
        raise ValueError(
            "comparison does not belong to supplied decision"
        )

    if analysis.decision_id != decision.decision_id:
        raise ValueError(
            "research analysis does not belong to supplied decision"
        )

    coverage_score = aggregate_criterion_coverage(
        analysis
    )

    evidence_quality_score = aggregate_evidence_quality(
        evidence_assessments
    )

    applicability_score = aggregate_applicability(
        evidence_assessments
    )

    agreement_score = aggregate_agreement(
        analysis
    )

    decision_margin = calculate_decision_margin(
        comparison
    )

    overall_score = (
        coverage_score * COVERAGE_WEIGHT
        + evidence_quality_score
        * EVIDENCE_QUALITY_WEIGHT
        + applicability_score
        * APPLICABILITY_WEIGHT
        + agreement_score
        * AGREEMENT_WEIGHT
        + decision_margin
        * DECISION_MARGIN_WEIGHT
    )

    blocking_reasons: list[str] = []

    critical_blockers = find_critical_criterion_blockers(
        decision,
        analysis,
    )

    blocking_reasons.extend(
        critical_blockers
    )

    unresolved_conflicts = [
        conflict
        for conflict in analysis.conflicts
        if conflict.resolution_status == "unresolved"
    ]

    if unresolved_conflicts:
        blocking_reasons.append(
            "important evidence conflicts remain unresolved"
        )

    if comparison.status == "incomplete":
        blocking_reasons.append(
            "candidate eligibility remains unresolved"
        )

    research_gap_ids = [
        gap.gap_id
        for gap in analysis.research_gaps
    ]

    if comparison.status == "incomplete":
        status = "INSUFFICIENT_EVIDENCE"

    elif unresolved_conflicts:
        status = "CONFLICTED"

    elif critical_blockers:
        status = "INSUFFICIENT_EVIDENCE"

    elif overall_score >= READY_THRESHOLD:
        status = "READY"

    elif overall_score >= TENTATIVE_THRESHOLD:
        status = "TENTATIVE"

    else:
        status = "INSUFFICIENT_EVIDENCE"

    return DecisionReadiness(
        decision_id=decision.decision_id,
        overall_score=overall_score,
        status=status,
        criterion_coverage=coverage_score,
        evidence_quality=evidence_quality_score,
        applicability=applicability_score,
        agreement_score=agreement_score,
        decision_margin=decision_margin,
        blocking_reasons=blocking_reasons,
        research_gap_ids=research_gap_ids,
    )
