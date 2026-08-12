"""Build deterministic V3 decision inputs from existing research state."""

from models import (
    CandidateCriterionScore,
    DecisionCase,
    EvidenceAssessment,
    EvidenceSignal,
    SummaryState,
)
from services.evidence_quality import assess_evidence


def build_evidence_assessments(
    state: SummaryState,
    decision: DecisionCase,
) -> list[EvidenceAssessment]:
    """
    Assess all persisted Evidence against one DecisionCase.

    This builder intentionally does not infer candidates, criteria,
    constraint outcomes, criterion scores, or signal direction.
    """

    assessments: list[EvidenceAssessment] = []

    for evidence in state.evidence_items:
        assessments.append(
            assess_evidence(
                evidence,
                decision,
            )
        )

    return assessments


def attach_evidence_assessments(
    state: SummaryState,
    decision: DecisionCase,
) -> SummaryState:
    """Build and store Phase 9 evidence assessments on SummaryState."""

    state.evidence_assessments = build_evidence_assessments(
        state,
        decision,
    )

    return state


def build_evidence_signals(
    state: SummaryState,
    decision: DecisionCase,
) -> list:
    """
    Build conservative EvidenceSignal objects from research evidence.

    Baseline rules:
    - candidate name must appear in evidence text
    - criterion name must overlap evidence text
    - unmatched evidence is skipped
    - direction remains neutral unless explicitly inferable later
    """

    from services.hybrid_retrieval import tokenize

    signals: list[EvidenceSignal] = []

    assessment_by_evidence = {
        item.evidence_id: item
        for item in state.evidence_assessments
    }

    for evidence in state.evidence_items:
        evidence_text = " ".join(
            part
            for part in (
                evidence.source_title,
                evidence.snippet,
                evidence.content,
            )
            if part
        )

        evidence_tokens = tokenize(evidence_text)

        if not evidence_tokens:
            continue

        assessment = assessment_by_evidence.get(
            evidence.evidence_id
        )

        for candidate in decision.candidates:
            candidate_tokens = tokenize(candidate.name)

            if not candidate_tokens:
                continue

            if not candidate_tokens.issubset(
                evidence_tokens
            ):
                continue

            for criterion in decision.criteria:
                criterion_tokens = tokenize(
                    criterion.name
                )

                if not criterion_tokens:
                    continue

                overlap = (
                    criterion_tokens
                    & evidence_tokens
                )

                if not overlap:
                    continue

                source_confidence = (
                    assessment.source_quality.confidence
                    if assessment
                    else 0.5
                )

                applicability = (
                    assessment.applicability.applicability_score
                    if assessment
                    else 0.5
                )

                signals.append(
                    EvidenceSignal(
                        evidence_id=evidence.evidence_id,
                        candidate_id=candidate.candidate_id,
                        criterion_id=criterion.criterion_id,
                        direction="neutral",
                        strength=min(
                            1.0,
                            len(overlap)
                            / max(
                                len(criterion_tokens),
                                1,
                            ),
                        ),
                        source_confidence=source_confidence,
                        applicability=applicability,
                        rationale=(
                            "Candidate and criterion terms "
                            "matched retrieved evidence."
                        ),
                    )
                )

    return signals


def attach_evidence_signals(
    state: SummaryState,
    decision: DecisionCase,
) -> SummaryState:
    """Build and store conservative evidence signals."""

    state.evidence_signals = build_evidence_signals(
        state,
        decision,
    )

    return state



def build_candidate_criterion_scores(
    decision: DecisionCase,
    signals: list[EvidenceSignal],
) -> list[CandidateCriterionScore]:
    """
    Derive conservative 0-10 candidate criterion scores.

    Only directional evidence participates:
    - positive evidence contributes above the neutral midpoint
    - negative evidence contributes below the neutral midpoint
    - neutral evidence is intentionally ignored

    Candidate × criterion pairs without directional evidence are omitted.
    The pipeline will therefore remain incomplete instead of inventing a
    score for unsupported pairs.
    """

    valid_candidate_ids = {
        candidate.candidate_id
        for candidate in decision.candidates
    }

    valid_criterion_ids = {
        criterion.criterion_id
        for criterion in decision.criteria
    }

    grouped: dict[
        tuple[str, str],
        list[EvidenceSignal],
    ] = {}

    for signal in signals:
        if signal.candidate_id not in valid_candidate_ids:
            continue

        if signal.criterion_id not in valid_criterion_ids:
            continue

        if signal.direction not in {"positive", "negative"}:
            continue

        grouped.setdefault(
            (
                signal.candidate_id,
                signal.criterion_id,
            ),
            [],
        ).append(signal)

    scores: list[CandidateCriterionScore] = []

    for candidate in decision.candidates:
        for criterion in decision.criteria:
            pair = (
                candidate.candidate_id,
                criterion.criterion_id,
            )

            pair_signals = grouped.get(pair, [])

            if not pair_signals:
                continue

            signed_total = 0.0
            weight_total = 0.0

            for signal in pair_signals:
                confidence_weight = (
                    max(0.0, min(1.0, signal.source_confidence))
                    * max(0.0, min(1.0, signal.applicability))
                )

                if confidence_weight <= 0.0:
                    continue

                strength = max(
                    0.0,
                    min(1.0, signal.strength),
                )

                direction = (
                    1.0
                    if signal.direction == "positive"
                    else -1.0
                )

                signed_total += (
                    direction
                    * strength
                    * confidence_weight
                )

                weight_total += confidence_weight

            if weight_total <= 0.0:
                continue

            signed_mean = signed_total / weight_total

            fitness_score = max(
                0.0,
                min(
                    10.0,
                    5.0 + 5.0 * signed_mean,
                ),
            )

            scores.append(
                CandidateCriterionScore(
                    candidate_id=candidate.candidate_id,
                    criterion_id=criterion.criterion_id,
                    fitness_score=fitness_score,
                    rationale=(
                        "Derived deterministically from "
                        f"{len(pair_signals)} directional "
                        "evidence signal(s)."
                    ),
                )
            )

    return scores
