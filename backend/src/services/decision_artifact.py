"""Deterministic Architecture Decision Record projection."""

from __future__ import annotations

from typing import Any

from models import (
    DecisionArtifact,
    SummaryState,
)


def build_decision_artifact(
    state: SummaryState,
) -> DecisionArtifact | None:
    """
    Project persisted decision-intelligence state into an ADR.

    This service never:
    - calls an LLM;
    - invents a recommendation;
    - converts a comparison winner into a recommendation;
    - predicts hypothetical winners;
    - re-evaluates evidence.
    """

    decision = state.decision_case

    if decision is None:
        return None

    recommendation = _clean_text(
        decision.recommendation
    )

    readiness = state.decision_readiness

    readiness_status = (
        str(readiness.status or "UNKNOWN").upper()
        if readiness is not None
        else "UNKNOWN"
    )

    artifact_status = _artifact_status(
        readiness_status,
        recommendation,
    )

    candidate_names = {
        item.candidate_id: item.name
        for item in decision.candidates
    }

    artifact = DecisionArtifact(
        decision_id=decision.decision_id,
        title=(
            f"ADR — {decision.question.strip()}"
        ),
        status=artifact_status,
        decision_question=decision.question,
        recommendation=recommendation,
    )

    # --------------------------------------------------
    # Context
    # --------------------------------------------------

    if decision.context:
        artifact.context_lines.append(
            decision.context.strip()
        )

    for requirement in decision.requirements:
        artifact.context_lines.append(
            f"Requirement: {requirement.text}"
        )

    # --------------------------------------------------
    # Candidates
    # --------------------------------------------------

    for candidate in decision.candidates:
        line = candidate.name

        description = _clean_text(
            getattr(
                candidate,
                "description",
                None,
            )
        )

        if description:
            line += f" — {description}"

        artifact.candidate_lines.append(line)

    # --------------------------------------------------
    # Criteria
    # --------------------------------------------------

    for criterion in decision.criteria:
        line = (
            f"{criterion.name} "
            f"(weight={criterion.weight:g})"
        )

        description = _clean_text(
            criterion.description
        )

        if description:
            line += f" — {description}"

        artifact.criterion_lines.append(line)

    # --------------------------------------------------
    # Hard constraints
    # --------------------------------------------------

    for constraint in decision.constraints:
        artifact.constraint_lines.append(
            constraint.text
        )

    # --------------------------------------------------
    # Comparison
    # Ranking is descriptive only.
    # --------------------------------------------------

    comparison = state.decision_comparison

    if comparison is not None:
        artifact.comparison_lines.append(
            f"Comparison status: {comparison.status}"
        )

        if comparison.ranked_candidate_ids:
            names = [
                candidate_names.get(
                    candidate_id,
                    candidate_id,
                )
                for candidate_id
                in comparison.ranked_candidate_ids
            ]

            artifact.comparison_lines.append(
                "Current deterministic ranking: "
                + " > ".join(names)
            )

        if comparison.unresolved_candidate_ids:
            names = [
                candidate_names.get(
                    candidate_id,
                    candidate_id,
                )
                for candidate_id
                in comparison.unresolved_candidate_ids
            ]

            artifact.comparison_lines.append(
                "Unresolved candidates: "
                + ", ".join(names)
            )

        if comparison.excluded_candidate_ids:
            names = [
                candidate_names.get(
                    candidate_id,
                    candidate_id,
                )
                for candidate_id
                in comparison.excluded_candidate_ids
            ]

            artifact.comparison_lines.append(
                "Excluded candidates: "
                + ", ".join(names)
            )

    # --------------------------------------------------
    # Readiness
    # --------------------------------------------------

    if readiness is not None:
        artifact.readiness_lines.extend(
            [
                (
                    "Readiness status: "
                    f"{readiness_status}"
                ),
                (
                    "Readiness score: "
                    f"{readiness.overall_score:.3f}"
                ),
                (
                    "Criterion coverage: "
                    f"{readiness.criterion_coverage:.3f}"
                ),
                (
                    "Evidence quality: "
                    f"{readiness.evidence_quality:.3f}"
                ),
                (
                    "Applicability: "
                    f"{readiness.applicability:.3f}"
                ),
                (
                    "Agreement score: "
                    f"{readiness.agreement_score:.3f}"
                ),
                (
                    "Decision margin: "
                    f"{readiness.decision_margin:.3f}"
                ),
            ]
        )

        for reason in (
            readiness.blocking_reasons or []
        ):
            artifact.risk_lines.append(
                f"Readiness blocker: {reason}"
            )

    # --------------------------------------------------
    # Robustness
    # --------------------------------------------------

    robustness = state.recommendation_robustness

    if robustness is not None:
        artifact.robustness_lines.append(
            f"Robustness status: {robustness.status}"
        )

        if robustness.baseline_winner_id:
            artifact.robustness_lines.append(
                "Comparison baseline winner: "
                + candidate_names.get(
                    robustness.baseline_winner_id,
                    robustness.baseline_winner_id,
                )
            )

        if robustness.score_margin is not None:
            artifact.robustness_lines.append(
                "Score margin: "
                f"{robustness.score_margin:.3f}"
            )

        artifact.robustness_lines.append(
            f"Sensitivity flips observed: "
            f"{robustness.flip_count}"
        )

        for reason in robustness.reasons:
            artifact.risk_lines.append(
                f"Robustness: {reason}"
            )

    # --------------------------------------------------
    # Sensitivity
    # --------------------------------------------------

    for item in state.decision_sensitivity:
        criterion_id = getattr(
            item,
            "criterion_id",
            "unknown",
        )

        line = (
            f"Criterion {criterion_id}: "
            f"recommendation_changes="
            f"{bool(item.recommendation_changes)}"
        )

        switch_threshold = getattr(
            item,
            "switch_threshold",
            None,
        )

        if switch_threshold is not None:
            line += (
                f", switch_threshold="
                f"{switch_threshold:.3f}"
            )

        artifact.sensitivity_lines.append(line)

    # --------------------------------------------------
    # Assumptions
    # --------------------------------------------------

    for item in state.decision_assumptions:
        artifact.assumption_lines.append(
            _describe_generic_item(
                item,
                preferred_fields=(
                    "text",
                    "description",
                    "assumption",
                    "rationale",
                ),
            )
        )

    # --------------------------------------------------
    # Research gaps / risks
    # --------------------------------------------------

    analysis = state.research_analysis

    if analysis is not None:
        for gap in analysis.research_gaps:
            if getattr(gap, "status", "open") != "open":
                continue

            artifact.risk_lines.append(
                "Research gap: "
                + _describe_generic_item(
                    gap,
                    preferred_fields=(
                        "description",
                        "gap_type",
                    ),
                )
            )

    # --------------------------------------------------
    # Re-evaluation triggers
    # --------------------------------------------------

    for item in (
        state.decision_reevaluation_triggers
    ):
        artifact.reevaluation_lines.append(
            _describe_generic_item(
                item,
                preferred_fields=(
                    "description",
                    "condition",
                    "trigger",
                    "rationale",
                ),
            )
        )

    # --------------------------------------------------
    # Evidence summary
    # --------------------------------------------------

    assessments = (
        state.evidence_assessments or []
    )

    artifact.evidence_lines.append(
        f"Assessed evidence items: "
        f"{len(assessments)}"
    )

    recognized_authorities = sorted(
        {
            assessment.source_quality.authority_type
            for assessment in assessments
            if (
                assessment.source_quality.authority_type
                and assessment.source_quality.authority_type
                != "UNKNOWN"
            )
        }
    )

    if recognized_authorities:
        artifact.evidence_lines.append(
            "Observed authority types: "
            + ", ".join(
                recognized_authorities
            )
        )

    artifact.markdown = (
        render_decision_artifact_markdown(
            artifact
        )
    )

    return artifact


def render_decision_artifact_markdown(
    artifact: DecisionArtifact,
) -> str:
    """Render a deterministic ADR markdown document."""

    lines = [
        f"# {artifact.title}",
        "",
        f"**Status:** {artifact.status}",
        f"**Decision ID:** {artifact.decision_id}",
        "",
        "## Decision Question",
        "",
        artifact.decision_question,
        "",
        "## Decision",
        "",
    ]

    if artifact.recommendation:
        lines.append(
            artifact.recommendation
        )
    else:
        lines.append(
            "No structured recommendation recorded."
        )

    _append_section(
        lines,
        "Context",
        artifact.context_lines,
    )
    _append_section(
        lines,
        "Candidates Considered",
        artifact.candidate_lines,
    )
    _append_section(
        lines,
        "Decision Criteria",
        artifact.criterion_lines,
    )
    _append_section(
        lines,
        "Hard Constraints",
        artifact.constraint_lines,
    )
    _append_section(
        lines,
        "Current Comparison",
        artifact.comparison_lines,
    )
    _append_section(
        lines,
        "Decision Readiness",
        artifact.readiness_lines,
    )
    _append_section(
        lines,
        "Recommendation Robustness",
        artifact.robustness_lines,
    )
    _append_section(
        lines,
        "Sensitivity",
        artifact.sensitivity_lines,
    )
    _append_section(
        lines,
        "Evidence Summary",
        artifact.evidence_lines,
    )
    _append_section(
        lines,
        "Assumptions",
        artifact.assumption_lines,
    )
    _append_section(
        lines,
        "Risks and Open Questions",
        artifact.risk_lines,
    )
    _append_section(
        lines,
        "Re-evaluation Triggers",
        artifact.reevaluation_lines,
    )

    return "\n".join(lines).rstrip() + "\n"


def _artifact_status(
    readiness_status: str,
    recommendation: str | None,
) -> str:
    """
    ADR certainty mirrors reporting certainty.

    READY alone is insufficient.
    """

    if (
        readiness_status == "READY"
        and recommendation is not None
    ):
        return "ACCEPTED"

    return "PROVISIONAL"


def _append_section(
    lines: list[str],
    title: str,
    values: list[str],
) -> None:
    lines.extend(
        [
            "",
            f"## {title}",
            "",
        ]
    )

    if not values:
        lines.append("Not recorded.")
        return

    lines.extend(
        f"- {value}"
        for value in values
    )


def _clean_text(
    value: Any,
) -> str | None:
    if not isinstance(value, str):
        return None

    value = value.strip()

    return value or None


def _describe_generic_item(
    item: Any,
    *,
    preferred_fields: tuple[str, ...],
) -> str:
    for field_name in preferred_fields:
        value = _clean_text(
            getattr(
                item,
                field_name,
                None,
            )
        )

        if value:
            return value

    identifier = (
        getattr(item, "assumption_id", None)
        or getattr(item, "trigger_id", None)
        or getattr(item, "gap_id", None)
        or getattr(item, "id", None)
    )

    if identifier:
        return str(identifier)

    return type(item).__name__
