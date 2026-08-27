"""Deterministic structural diff between persisted research versions.

This module compares already-persisted research state only.

It must never:
- call an LLM,
- retrieve new evidence,
- recompute scores/readiness,
- infer that a newer version is better,
- synthesize a recommendation,
- mutate either input state.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from enum import Enum
from typing import Any

from models import SummaryState


ADDED = "ADDED"
REMOVED = "REMOVED"
CHANGED = "CHANGED"


@dataclass(kw_only=True)
class VersionFieldChange:
    """One deterministic structural field change."""

    field_name: str
    change_type: str
    before: Any = None
    after: Any = None


@dataclass(kw_only=True)
class DecisionVersionDiff:
    """Structural change summary between two persisted research states."""

    source_research_id: str
    target_research_id: str

    has_changes: bool = False

    decision_changes: list[VersionFieldChange] = field(
        default_factory=list
    )

    readiness_changes: list[VersionFieldChange] = field(
        default_factory=list
    )

    recommendation_changes: list[VersionFieldChange] = field(
        default_factory=list
    )

    research_gap_changes: list[VersionFieldChange] = field(
        default_factory=list
    )

    evidence_changes: list[VersionFieldChange] = field(
        default_factory=list
    )

    assumption_changes: list[VersionFieldChange] = field(
        default_factory=list
    )

    trigger_changes: list[VersionFieldChange] = field(
        default_factory=list
    )

    architecture_changes: list[VersionFieldChange] = field(
        default_factory=list
    )

    unchanged_sections: list[str] = field(
        default_factory=list
    )

    summary_lines: list[str] = field(
        default_factory=list
    )


def _to_plain(value: Any) -> Any:
    """Convert structured state into deterministic plain Python values."""

    if value is None:
        return None

    if isinstance(value, Enum):
        return value.value

    if is_dataclass(value):
        return {
            key: _to_plain(item)
            for key, item in asdict(value).items()
        }

    if isinstance(value, dict):
        return {
            str(key): _to_plain(item)
            for key, item in sorted(
                value.items(),
                key=lambda pair: str(pair[0]),
            )
        }

    if isinstance(value, (list, tuple)):
        return [
            _to_plain(item)
            for item in value
        ]

    if isinstance(value, set):
        return sorted(
            _to_plain(item)
            for item in value
        )

    if hasattr(value, "__dict__"):
        return {
            str(key): _to_plain(item)
            for key, item in sorted(
                vars(value).items()
            )
            if not str(key).startswith("_")
        }

    return value


def _field(
    value: Any,
    name: str,
    default: Any = None,
) -> Any:
    if value is None:
        return default

    if isinstance(value, dict):
        return value.get(
            name,
            default,
        )

    return getattr(
        value,
        name,
        default,
    )


def _append_scalar_change(
    changes: list[VersionFieldChange],
    *,
    field_name: str,
    before: Any,
    after: Any,
) -> None:
    before_plain = _to_plain(before)
    after_plain = _to_plain(after)

    if before_plain == after_plain:
        return

    if before_plain is None:
        change_type = ADDED
    elif after_plain is None:
        change_type = REMOVED
    else:
        change_type = CHANGED

    changes.append(
        VersionFieldChange(
            field_name=field_name,
            change_type=change_type,
            before=before_plain,
            after=after_plain,
        )
    )


def _stable_id(
    value: Any,
    candidates: tuple[str, ...],
) -> str | None:
    for name in candidates:
        result = _field(
            value,
            name,
        )

        if result is None:
            continue

        normalized = str(result).strip()

        if normalized:
            return normalized

    return None


def _indexed_items(
    values: list[Any] | None,
    *,
    id_fields: tuple[str, ...],
) -> dict[str, Any]:
    """Index only items that expose an explicit stable identifier.

    Items without a stable identifier are intentionally excluded rather
    than receiving synthetic semantic identity.
    """

    result: dict[str, Any] = {}

    for value in values or []:
        item_id = _stable_id(
            value,
            id_fields,
        )

        if item_id is None:
            continue

        result[item_id] = value

    return result


def _append_indexed_changes(
    changes: list[VersionFieldChange],
    *,
    field_prefix: str,
    before_values: list[Any] | None,
    after_values: list[Any] | None,
    id_fields: tuple[str, ...],
) -> None:
    before = _indexed_items(
        before_values,
        id_fields=id_fields,
    )

    after = _indexed_items(
        after_values,
        id_fields=id_fields,
    )

    all_ids = sorted(
        set(before)
        | set(after)
    )

    for item_id in all_ids:
        before_item = before.get(item_id)
        after_item = after.get(item_id)

        before_plain = _to_plain(
            before_item
        )
        after_plain = _to_plain(
            after_item
        )

        if before_plain == after_plain:
            continue

        if before_item is None:
            change_type = ADDED
        elif after_item is None:
            change_type = REMOVED
        else:
            change_type = CHANGED

        changes.append(
            VersionFieldChange(
                field_name=(
                    f"{field_prefix}.{item_id}"
                ),
                change_type=change_type,
                before=before_plain,
                after=after_plain,
            )
        )


def _decision_case_changes(
    before_state: SummaryState,
    after_state: SummaryState,
) -> list[VersionFieldChange]:
    changes: list[
        VersionFieldChange
    ] = []

    before = before_state.decision_case
    after = after_state.decision_case

    for field_name in (
        "decision_id",
        "question",
    ):
        _append_scalar_change(
            changes,
            field_name=field_name,
            before=_field(
                before,
                field_name,
            ),
            after=_field(
                after,
                field_name,
            ),
        )

    _append_indexed_changes(
        changes,
        field_prefix="candidate",
        before_values=_field(
            before,
            "candidates",
            [],
        ),
        after_values=_field(
            after,
            "candidates",
            [],
        ),
        id_fields=(
            "candidate_id",
        ),
    )

    _append_indexed_changes(
        changes,
        field_prefix="criterion",
        before_values=_field(
            before,
            "criteria",
            [],
        ),
        after_values=_field(
            after,
            "criteria",
            [],
        ),
        id_fields=(
            "criterion_id",
        ),
    )

    _append_indexed_changes(
        changes,
        field_prefix="requirement",
        before_values=_field(
            before,
            "requirements",
            [],
        ),
        after_values=_field(
            after,
            "requirements",
            [],
        ),
        id_fields=(
            "requirement_id",
        ),
    )

    _append_indexed_changes(
        changes,
        field_prefix="constraint",
        before_values=_field(
            before,
            "constraints",
            [],
        ),
        after_values=_field(
            after,
            "constraints",
            [],
        ),
        id_fields=(
            "constraint_id",
        ),
    )

    return changes


def _readiness_changes(
    before_state: SummaryState,
    after_state: SummaryState,
) -> list[VersionFieldChange]:
    changes: list[
        VersionFieldChange
    ] = []

    before = (
        before_state.decision_readiness
    )

    after = (
        after_state.decision_readiness
    )

    # Persisted outputs only. Never recompute them here.
    for field_name in (
        "status",
        "overall_score",
        "criterion_coverage",
        "evidence_quality",
        "applicability",
        "agreement_score",
        "decision_margin",
        "blocking_reasons",
        "research_gap_ids",
    ):
        _append_scalar_change(
            changes,
            field_name=field_name,
            before=_field(
                before,
                field_name,
            ),
            after=_field(
                after,
                field_name,
            ),
        )

    return changes


def _recommendation_changes(
    before_state: SummaryState,
    after_state: SummaryState,
) -> list[VersionFieldChange]:
    changes: list[
        VersionFieldChange
    ] = []

    # DecisionCase.recommendation is the authoritative structured
    # recommendation boundary. Comparison winner/ranking must never be
    # promoted into recommendation here.
    _append_scalar_change(
        changes,
        field_name=(
            "decision_case.recommendation"
        ),
        before=_field(
            before_state.decision_case,
            "recommendation",
        ),
        after=_field(
            after_state.decision_case,
            "recommendation",
        ),
    )

    return changes


def _research_gap_changes(
    before_state: SummaryState,
    after_state: SummaryState,
) -> list[VersionFieldChange]:
    changes: list[
        VersionFieldChange
    ] = []

    before_analysis = (
        before_state.research_analysis
    )

    after_analysis = (
        after_state.research_analysis
    )

    _append_indexed_changes(
        changes,
        field_prefix="research_gap",
        before_values=_field(
            before_analysis,
            "research_gaps",
            [],
        ),
        after_values=_field(
            after_analysis,
            "research_gaps",
            [],
        ),
        id_fields=(
            "gap_id",
        ),
    )

    return changes


def _evidence_changes(
    before_state: SummaryState,
    after_state: SummaryState,
) -> list[VersionFieldChange]:
    changes: list[
        VersionFieldChange
    ] = []

    _append_indexed_changes(
        changes,
        field_prefix="evidence",
        before_values=(
            before_state.evidence_items
        ),
        after_values=(
            after_state.evidence_items
        ),
        id_fields=(
            "evidence_id",
        ),
    )

    return changes


def _assumption_changes(
    before_state: SummaryState,
    after_state: SummaryState,
) -> list[VersionFieldChange]:
    changes: list[
        VersionFieldChange
    ] = []

    _append_indexed_changes(
        changes,
        field_prefix="assumption",
        before_values=(
            before_state.decision_assumptions
        ),
        after_values=(
            after_state.decision_assumptions
        ),
        id_fields=(
            "assumption_id",
        ),
    )

    return changes


def _trigger_changes(
    before_state: SummaryState,
    after_state: SummaryState,
) -> list[VersionFieldChange]:
    changes: list[
        VersionFieldChange
    ] = []

    _append_indexed_changes(
        changes,
        field_prefix="reevaluation_trigger",
        before_values=(
            before_state
            .decision_reevaluation_triggers
        ),
        after_values=(
            after_state
            .decision_reevaluation_triggers
        ),
        id_fields=(
            "trigger_id",
        ),
    )

    return changes


def _architecture_changes(
    before_state: SummaryState,
    after_state: SummaryState,
) -> list[VersionFieldChange]:
    changes: list[
        VersionFieldChange
    ] = []

    _append_scalar_change(
        changes,
        field_name="technical_context",
        before=(
            before_state.technical_context
        ),
        after=(
            after_state.technical_context
        ),
    )

    _append_indexed_changes(
        changes,
        field_prefix=(
            "integration_assessment"
        ),
        before_values=(
            before_state
            .integration_assessments
        ),
        after_values=(
            after_state
            .integration_assessments
        ),
        id_fields=(
            "candidate_id",
            "assessment_id",
        ),
    )

    return changes


def compare_research_versions(
    *,
    source_research_id: str,
    source_state: SummaryState,
    target_research_id: str,
    target_state: SummaryState,
) -> DecisionVersionDiff:
    """Compare two persisted research versions without reinterpretation."""

    decision_changes = (
        _decision_case_changes(
            source_state,
            target_state,
        )
    )

    readiness_changes = (
        _readiness_changes(
            source_state,
            target_state,
        )
    )

    recommendation_changes = (
        _recommendation_changes(
            source_state,
            target_state,
        )
    )

    research_gap_changes = (
        _research_gap_changes(
            source_state,
            target_state,
        )
    )

    evidence_changes = (
        _evidence_changes(
            source_state,
            target_state,
        )
    )

    assumption_changes = (
        _assumption_changes(
            source_state,
            target_state,
        )
    )

    trigger_changes = (
        _trigger_changes(
            source_state,
            target_state,
        )
    )

    architecture_changes = (
        _architecture_changes(
            source_state,
            target_state,
        )
    )

    sections = {
        "decision": decision_changes,
        "readiness": readiness_changes,
        "recommendation": (
            recommendation_changes
        ),
        "research_gaps": (
            research_gap_changes
        ),
        "evidence": evidence_changes,
        "assumptions": (
            assumption_changes
        ),
        "reevaluation_triggers": (
            trigger_changes
        ),
        "architecture": (
            architecture_changes
        ),
    }

    unchanged_sections = [
        section_name
        for section_name, values
        in sections.items()
        if not values
    ]

    diff = DecisionVersionDiff(
        source_research_id=(
            source_research_id
        ),
        target_research_id=(
            target_research_id
        ),
        has_changes=any(
            bool(values)
            for values in sections.values()
        ),
        decision_changes=(
            decision_changes
        ),
        readiness_changes=(
            readiness_changes
        ),
        recommendation_changes=(
            recommendation_changes
        ),
        research_gap_changes=(
            research_gap_changes
        ),
        evidence_changes=(
            evidence_changes
        ),
        assumption_changes=(
            assumption_changes
        ),
        trigger_changes=(
            trigger_changes
        ),
        architecture_changes=(
            architecture_changes
        ),
        unchanged_sections=(
            unchanged_sections
        ),
    )

    diff.summary_lines = (
        build_version_change_summary(
            diff
        )
    )

    return diff


def _count_change_types(
    changes: list[VersionFieldChange],
) -> tuple[int, int, int]:
    added = sum(
        1
        for item in changes
        if item.change_type == ADDED
    )

    removed = sum(
        1
        for item in changes
        if item.change_type == REMOVED
    )

    changed = sum(
        1
        for item in changes
        if item.change_type == CHANGED
    )

    return (
        added,
        removed,
        changed,
    )


def _section_summary(
    *,
    label: str,
    changes: list[VersionFieldChange],
) -> str | None:
    if not changes:
        return None

    added, removed, changed = (
        _count_change_types(
            changes
        )
    )

    parts: list[str] = []

    if added:
        parts.append(
            f"{added} added"
        )

    if removed:
        parts.append(
            f"{removed} removed"
        )

    if changed:
        parts.append(
            f"{changed} changed"
        )

    return (
        f"{label}: "
        + ", ".join(parts)
    )


def build_version_change_summary(
    diff: DecisionVersionDiff,
) -> list[str]:
    """Explain persisted structural changes without judging quality."""

    if not diff.has_changes:
        return [
            "No tracked structural changes were detected."
        ]

    result: list[str] = []

    sections = (
        (
            "Decision structure",
            diff.decision_changes,
        ),
        (
            "Readiness",
            diff.readiness_changes,
        ),
        (
            "Recommendation",
            diff.recommendation_changes,
        ),
        (
            "Research gaps",
            diff.research_gap_changes,
        ),
        (
            "Evidence",
            diff.evidence_changes,
        ),
        (
            "Assumptions",
            diff.assumption_changes,
        ),
        (
            "Re-evaluation triggers",
            diff.trigger_changes,
        ),
        (
            "Architecture context",
            diff.architecture_changes,
        ),
    )

    for label, changes in sections:
        summary = _section_summary(
            label=label,
            changes=changes,
        )

        if summary is not None:
            result.append(summary)

    return result
