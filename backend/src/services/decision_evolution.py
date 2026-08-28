"""Deterministic decision evolution across persisted research lineage.

Evolution is represented as parent -> child edges.

Important semantics:
- version_number is lineage generation/depth, not a globally unique sequence;
- branches are preserved rather than flattened;
- every change is derived from already persisted states;
- Phase41 deterministic version diff is reused;
- no LLM, retrieval, scoring, readiness recomputation, or quality judgment;
- evolution does not imply improvement.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from models import ResearchLineage, SummaryState
from services.decision_change_attribution import (
    DecisionChangeAttribution,
    build_change_attribution,
)
from services.decision_version_diff import (
    DecisionVersionDiff,
    compare_research_versions,
)


@dataclass(kw_only=True)
class DecisionEvolutionStep:
    """One persisted parent -> child decision evolution edge."""

    source_research_id: str
    target_research_id: str

    root_research_id: str

    source_version_number: int
    target_version_number: int

    target_creation_reason: str

    created_from_trigger_ids: list[str] = field(
        default_factory=list
    )

    diff: DecisionVersionDiff
    attribution: DecisionChangeAttribution


@dataclass(kw_only=True)
class DecisionEvolutionTimeline:
    """Branch-aware deterministic evolution of one research lineage."""

    root_research_id: str

    research_ids: list[str] = field(
        default_factory=list
    )

    steps: list[DecisionEvolutionStep] = field(
        default_factory=list
    )

    root_version_ids: list[str] = field(
        default_factory=list
    )

    branch_point_ids: list[str] = field(
        default_factory=list
    )

    leaf_version_ids: list[str] = field(
        default_factory=list
    )

    has_branches: bool = False


def _lineage_sort_key(
    lineage: ResearchLineage,
) -> tuple[int, str]:
    return (
        lineage.version_number,
        lineage.research_id,
    )


def _build_lineage_index(
    lineage_items: list[ResearchLineage],
) -> dict[str, ResearchLineage]:
    return {
        item.research_id: item
        for item in lineage_items
    }


def _children_by_parent(
    lineage_items: list[ResearchLineage],
) -> dict[str, list[ResearchLineage]]:
    result: dict[
        str,
        list[ResearchLineage]
    ] = {}

    for item in lineage_items:
        parent_id = (
            item.parent_research_id
        )

        if parent_id is None:
            continue

        result.setdefault(
            parent_id,
            [],
        ).append(
            item
        )

    for children in result.values():
        children.sort(
            key=_lineage_sort_key
        )

    return result


def build_decision_evolution(
    *,
    root_research_id: str,
    lineage_items: list[ResearchLineage],
    load_state: Callable[
        [str],
        SummaryState | None,
    ],
) -> DecisionEvolutionTimeline:
    """Build branch-aware evolution from persisted lineage and states.

    Missing states are skipped conservatively. No synthetic state or
    synthetic diff is created.
    """

    relevant = [
        item
        for item in lineage_items
        if item.root_research_id
        == root_research_id
    ]

    relevant.sort(
        key=_lineage_sort_key
    )

    lineage_index = (
        _build_lineage_index(
            relevant
        )
    )

    children = (
        _children_by_parent(
            relevant
        )
    )

    root_version_ids = sorted(
        (
            item.research_id
            for item in relevant
            if item.parent_research_id
            is None
        ),
        key=lambda research_id: (
            lineage_index[
                research_id
            ].version_number,
            research_id,
        ),
    )

    branch_point_ids = sorted(
        (
            parent_id
            for parent_id, values
            in children.items()
            if len(values) > 1
        ),
        key=lambda research_id: (
            lineage_index[
                research_id
            ].version_number
            if research_id
            in lineage_index
            else 0,
            research_id,
        ),
    )

    parent_ids = {
        item.parent_research_id
        for item in relevant
        if item.parent_research_id
        is not None
    }

    leaf_version_ids = sorted(
        (
            item.research_id
            for item in relevant
            if item.research_id
            not in parent_ids
        ),
        key=lambda research_id: (
            lineage_index[
                research_id
            ].version_number,
            research_id,
        ),
    )

    steps: list[
        DecisionEvolutionStep
    ] = []

    for target in relevant:
        source_id = (
            target.parent_research_id
        )

        if source_id is None:
            continue

        source_lineage = (
            lineage_index.get(
                source_id
            )
        )

        if source_lineage is None:
            # Broken/incomplete lineage metadata.
            # Do not invent a parent.
            continue

        source_state = (
            load_state(
                source_id
            )
        )

        target_state = (
            load_state(
                target.research_id
            )
        )

        if (
            source_state is None
            or target_state is None
        ):
            # Persisted state unavailable:
            # skip rather than fabricate.
            continue

        diff = compare_research_versions(
            source_research_id=(
                source_id
            ),
            source_state=source_state,
            target_research_id=(
                target.research_id
            ),
            target_state=target_state,
        )

        attribution = (
            build_change_attribution(
                diff
            )
        )

        steps.append(
            DecisionEvolutionStep(
                source_research_id=(
                    source_id
                ),
                target_research_id=(
                    target.research_id
                ),
                root_research_id=(
                    root_research_id
                ),
                source_version_number=(
                    source_lineage.version_number
                ),
                target_version_number=(
                    target.version_number
                ),
                target_creation_reason=(
                    target.creation_reason
                ),
                created_from_trigger_ids=list(
                    target.created_from_trigger_ids
                ),
                diff=diff,
                attribution=attribution,
            )
        )

    steps.sort(
        key=lambda step: (
            step.target_version_number,
            step.source_research_id,
            step.target_research_id,
        )
    )

    return DecisionEvolutionTimeline(
        root_research_id=(
            root_research_id
        ),
        research_ids=[
            item.research_id
            for item in relevant
        ],
        steps=steps,
        root_version_ids=(
            root_version_ids
        ),
        branch_point_ids=(
            branch_point_ids
        ),
        leaf_version_ids=(
            leaf_version_ids
        ),
        has_branches=bool(
            branch_point_ids
        ),
    )
