"""Build deterministic V3 decision inputs from existing research state."""

from models import (
    DecisionCase,
    EvidenceAssessment,
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

    from models import EvidenceSignal
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
