"""Deterministic structural attribution for research-version changes.

This module explains *what persisted structures changed*.

It must never:
- infer causality,
- infer improvement,
- prefer a version or branch,
- call an LLM,
- retrieve evidence,
- recompute scores/readiness/recommendations,
- mutate the source diff.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from services.decision_version_diff import (
    ADDED,
    CHANGED,
    REMOVED,
    DecisionVersionDiff,
    VersionFieldChange,
)


@dataclass(kw_only=True)
class ChangeAttributionItem:
    """One persisted structural change."""

    field_name: str
    change_type: str
    before: Any = None
    after: Any = None


@dataclass(kw_only=True)
class ChangeAttributionGroup:
    """Changes belonging to one structural decision area."""

    section: str
    label: str
    items: list[ChangeAttributionItem] = field(
        default_factory=list
    )

    added_count: int = 0
    removed_count: int = 0
    changed_count: int = 0

    has_changes: bool = False


@dataclass(kw_only=True)
class DecisionChangeAttribution:
    """Detailed deterministic attribution for one version edge."""

    source_research_id: str
    target_research_id: str

    has_changes: bool

    groups: list[ChangeAttributionGroup] = field(
        default_factory=list
    )

    changed_sections: list[str] = field(
        default_factory=list
    )

    unchanged_sections: list[str] = field(
        default_factory=list
    )


_SECTION_ORDER: tuple[
    tuple[str, str, str],
    ...
] = (
    (
        "decision",
        "Decision structure",
        "decision_changes",
    ),
    (
        "readiness",
        "Readiness",
        "readiness_changes",
    ),
    (
        "recommendation",
        "Recommendation",
        "recommendation_changes",
    ),
    (
        "research_gaps",
        "Research gaps",
        "research_gap_changes",
    ),
    (
        "evidence",
        "Evidence",
        "evidence_changes",
    ),
    (
        "assumptions",
        "Assumptions",
        "assumption_changes",
    ),
    (
        "reevaluation_triggers",
        "Re-evaluation triggers",
        "trigger_changes",
    ),
    (
        "architecture",
        "Architecture context",
        "architecture_changes",
    ),
)


def _to_item(
    change: VersionFieldChange,
) -> ChangeAttributionItem:
    return ChangeAttributionItem(
        field_name=change.field_name,
        change_type=change.change_type,
        before=change.before,
        after=change.after,
    )


def _count(
    changes: list[VersionFieldChange],
    change_type: str,
) -> int:
    return sum(
        1
        for change in changes
        if change.change_type == change_type
    )


def _build_group(
    *,
    section: str,
    label: str,
    changes: list[VersionFieldChange],
) -> ChangeAttributionGroup:
    items = [
        _to_item(change)
        for change in changes
    ]

    return ChangeAttributionGroup(
        section=section,
        label=label,
        items=items,
        added_count=_count(
            changes,
            ADDED,
        ),
        removed_count=_count(
            changes,
            REMOVED,
        ),
        changed_count=_count(
            changes,
            CHANGED,
        ),
        has_changes=bool(
            changes
        ),
    )


def build_change_attribution(
    diff: DecisionVersionDiff,
) -> DecisionChangeAttribution:
    """Project one persisted structural diff into attribution groups."""

    groups: list[
        ChangeAttributionGroup
    ] = []

    changed_sections: list[str] = []
    unchanged_sections: list[str] = []

    for (
        section,
        label,
        attribute_name,
    ) in _SECTION_ORDER:
        changes = list(
            getattr(
                diff,
                attribute_name,
            )
        )

        group = _build_group(
            section=section,
            label=label,
            changes=changes,
        )

        groups.append(
            group
        )

        if group.has_changes:
            changed_sections.append(
                section
            )
        else:
            unchanged_sections.append(
                section
            )

    return DecisionChangeAttribution(
        source_research_id=(
            diff.source_research_id
        ),
        target_research_id=(
            diff.target_research_id
        ),
        has_changes=diff.has_changes,
        groups=groups,
        changed_sections=(
            changed_sections
        ),
        unchanged_sections=(
            unchanged_sections
        ),
    )
