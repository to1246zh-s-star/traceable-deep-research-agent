"""Coverage, conflict, and research-gap analysis for V3 Phase 11."""

from collections import defaultdict

from models import (
    DecisionCase,
    EvidenceConflict,
    EvidenceSignal,
    CriterionCoverage,
    ResearchAnalysis,
    ResearchGap,
)


VALID_DIRECTIONS = {
    "positive",
    "negative",
    "neutral",
}

MIN_SIGNAL_STRENGTH = 0.0
MAX_SIGNAL_STRENGTH = 1.0

DEFAULT_COVERAGE_THRESHOLD = 0.60
DEFAULT_CONFIDENCE_THRESHOLD = 0.55
DEFAULT_CONFLICT_THRESHOLD = 0.35


def validate_evidence_signals(
    decision: DecisionCase,
    signals: list[EvidenceSignal],
) -> None:
    """Validate evidence-signal structure against a DecisionCase."""

    candidate_ids = {
        candidate.candidate_id
        for candidate in decision.candidates
    }

    criterion_ids = {
        criterion.criterion_id
        for criterion in decision.criteria
    }

    seen_signal_ids: set[str] = set()
    errors: list[str] = []

    for signal in signals:
        if signal.signal_id in seen_signal_ids:
            errors.append(
                f"duplicate signal_id {signal.signal_id!r}"
            )

        seen_signal_ids.add(signal.signal_id)

        if signal.candidate_id not in candidate_ids:
            errors.append(
                f"unknown candidate_id {signal.candidate_id!r}"
            )

        if signal.criterion_id not in criterion_ids:
            errors.append(
                f"unknown criterion_id {signal.criterion_id!r}"
            )

        if signal.direction not in VALID_DIRECTIONS:
            errors.append(
                f"invalid signal direction {signal.direction!r}"
            )

        if not (
            MIN_SIGNAL_STRENGTH
            <= signal.strength
            <= MAX_SIGNAL_STRENGTH
        ):
            errors.append(
                "signal strength must be between 0 and 1"
            )

        if not 0.0 <= signal.source_confidence <= 1.0:
            errors.append(
                "source_confidence must be between 0 and 1"
            )

        if not 0.0 <= signal.applicability <= 1.0:
            errors.append(
                "applicability must be between 0 and 1"
            )

    if errors:
        raise ValueError("; ".join(errors))


def signal_effective_weight(
    signal: EvidenceSignal,
) -> float:
    """
    Calculate the usable contribution of one signal.

    Strength, source confidence, and applicability remain separate in the
    data model, but are combined here for deterministic analysis.
    """

    return (
        signal.strength
        * signal.source_confidence
        * signal.applicability
    )


def calculate_coverage(
    candidate_id: str,
    criterion_id: str,
    signals: list[EvidenceSignal],
) -> CriterionCoverage:
    """
    Calculate explainable heuristic coverage.

    Coverage approaches 1 as multiple strong, trustworthy, applicable
    evidence signals accumulate.
    """

    pair_signals = [
        signal
        for signal in signals
        if (
            signal.candidate_id == candidate_id
            and signal.criterion_id == criterion_id
        )
    ]

    effective_weights = [
        signal_effective_weight(signal)
        for signal in pair_signals
    ]

    effective_signal_count = sum(effective_weights)

    # Two fully effective signals are treated as baseline full coverage.
    coverage_score = min(
        1.0,
        effective_signal_count / 2.0,
    )

    if effective_weights:
        confidence_score = (
            sum(effective_weights)
            / len(effective_weights)
        )
    else:
        confidence_score = 0.0

    return CriterionCoverage(
        candidate_id=candidate_id,
        criterion_id=criterion_id,
        signal_count=len(pair_signals),
        effective_signal_count=effective_signal_count,
        coverage_score=coverage_score,
        confidence_score=confidence_score,
    )


def detect_conflict(
    candidate_id: str,
    criterion_id: str,
    signals: list[EvidenceSignal],
) -> EvidenceConflict:
    """Detect meaningful positive-versus-negative evidence disagreement."""

    pair_signals = [
        signal
        for signal in signals
        if (
            signal.candidate_id == candidate_id
            and signal.criterion_id == criterion_id
        )
    ]

    positive = [
        signal
        for signal in pair_signals
        if signal.direction == "positive"
    ]

    negative = [
        signal
        for signal in pair_signals
        if signal.direction == "negative"
    ]

    positive_weight = sum(
        signal_effective_weight(signal)
        for signal in positive
    )

    negative_weight = sum(
        signal_effective_weight(signal)
        for signal in negative
    )

    total_directional_weight = (
        positive_weight + negative_weight
    )

    if (
        positive_weight <= 0.0
        or negative_weight <= 0.0
        or total_directional_weight <= 0.0
    ):
        conflict_score = 0.0
        resolution_status = "none"
    else:
        # Maximum conflict occurs when support and opposition have
        # approximately equal effective weight.
        conflict_score = (
            2.0
            * min(positive_weight, negative_weight)
            / total_directional_weight
        )

        resolution_status = (
            "unresolved"
            if conflict_score >= DEFAULT_CONFLICT_THRESHOLD
            else "minor"
        )

    return EvidenceConflict(
        candidate_id=candidate_id,
        criterion_id=criterion_id,
        supporting_signal_ids=[
            signal.signal_id
            for signal in positive
        ],
        opposing_signal_ids=[
            signal.signal_id
            for signal in negative
        ],
        conflict_score=conflict_score,
        resolution_status=resolution_status,
    )


def detect_research_gaps(
    decision: DecisionCase,
    coverages: list[CriterionCoverage],
    conflicts: list[EvidenceConflict],
) -> list[ResearchGap]:
    """Convert weak coverage and unresolved conflict into actionable gaps."""

    candidate_names = {
        candidate.candidate_id: candidate.name
        for candidate in decision.candidates
    }

    criterion_names = {
        criterion.criterion_id: criterion.name
        for criterion in decision.criteria
    }

    gaps: list[ResearchGap] = []

    coverage_by_pair = {
        (
            coverage.candidate_id,
            coverage.criterion_id,
        ): coverage
        for coverage in coverages
    }

    conflict_by_pair = {
        (
            conflict.candidate_id,
            conflict.criterion_id,
        ): conflict
        for conflict in conflicts
    }

    for candidate in decision.candidates:
        for criterion in decision.criteria:
            pair = (
                candidate.candidate_id,
                criterion.criterion_id,
            )

            coverage = coverage_by_pair[pair]
            conflict = conflict_by_pair[pair]

            if coverage.signal_count == 0:
                gaps.append(
                    ResearchGap(
                        gap_id=(
                            f"gap_{candidate.candidate_id}_"
                            f"{criterion.criterion_id}_missing_evidence"
                        ),
                        candidate_id=candidate.candidate_id,
                        criterion_id=criterion.criterion_id,
                        gap_type="missing_evidence",
                        severity=1.0,
                        description=(
                            f"No evidence signals exist for "
                            f"{candidate.name} × {criterion.name}."
                        ),
                        suggested_query=(
                            f"{candidate.name} "
                            f"{criterion.name} "
                            f"technical evidence"
                        ),
                    )
                )

            elif coverage.coverage_score < DEFAULT_COVERAGE_THRESHOLD:
                severity = (
                    1.0 - coverage.coverage_score
                )

                gaps.append(
                    ResearchGap(
                        gap_id=(
                            f"gap_{candidate.candidate_id}_"
                            f"{criterion.criterion_id}_low_coverage"
                        ),
                        candidate_id=candidate.candidate_id,
                        criterion_id=criterion.criterion_id,
                        gap_type="low_coverage",
                        severity=severity,
                        description=(
                            f"Evidence coverage is weak for "
                            f"{candidate.name} × {criterion.name}."
                        ),
                        suggested_query=(
                            f"{candidate.name} "
                            f"{criterion.name} "
                            f"benchmark documentation"
                        ),
                    )
                )

            if (
                coverage.signal_count > 0
                and coverage.confidence_score
                < DEFAULT_CONFIDENCE_THRESHOLD
            ):
                gaps.append(
                    ResearchGap(
                        gap_id=(
                            f"gap_{candidate.candidate_id}_"
                            f"{criterion.criterion_id}_weak_source"
                        ),
                        candidate_id=candidate.candidate_id,
                        criterion_id=criterion.criterion_id,
                        gap_type="weak_source",
                        severity=(
                            1.0
                            - coverage.confidence_score
                        ),
                        description=(
                            f"Current evidence is weak or poorly applicable "
                            f"for {candidate.name} × {criterion.name}."
                        ),
                        suggested_query=(
                            f"{candidate.name} "
                            f"{criterion.name} "
                            f"official independent source"
                        ),
                    )
                )

            if conflict.resolution_status == "unresolved":
                gaps.append(
                    ResearchGap(
                        gap_id=(
                            f"gap_{candidate.candidate_id}_"
                            f"{criterion.criterion_id}_conflicting_evidence"
                        ),
                        candidate_id=candidate.candidate_id,
                        criterion_id=criterion.criterion_id,
                        gap_type="conflicting_evidence",
                        severity=conflict.conflict_score,
                        description=(
                            f"Supporting and opposing evidence conflict for "
                            f"{candidate.name} × {criterion.name}."
                        ),
                        suggested_query=(
                            f"{candidate.name} "
                            f"{criterion.name} "
                            f"independent verification"
                        ),
                    )
                )

    gaps.sort(
        key=lambda gap: (
            -gap.severity,
            gap.candidate_id,
            gap.criterion_id,
            gap.gap_type,
        )
    )

    return gaps


def analyze_research(
    decision: DecisionCase,
    signals: list[EvidenceSignal],
) -> ResearchAnalysis:
    """Run Phase 11 coverage, conflict, and gap analysis."""

    validate_evidence_signals(
        decision,
        signals,
    )

    coverages: list[CriterionCoverage] = []
    conflicts: list[EvidenceConflict] = []

    for candidate in decision.candidates:
        for criterion in decision.criteria:
            coverages.append(
                calculate_coverage(
                    candidate.candidate_id,
                    criterion.criterion_id,
                    signals,
                )
            )

            conflicts.append(
                detect_conflict(
                    candidate.candidate_id,
                    criterion.criterion_id,
                    signals,
                )
            )

    research_gaps = detect_research_gaps(
        decision,
        coverages,
        conflicts,
    )

    status = (
        "gaps_detected"
        if research_gaps
        else "complete"
    )

    return ResearchAnalysis(
        decision_id=decision.decision_id,
        coverages=coverages,
        conflicts=conflicts,
        research_gaps=research_gaps,
        status=status,
    )
