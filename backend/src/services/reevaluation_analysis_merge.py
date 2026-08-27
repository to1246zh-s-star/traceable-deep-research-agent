"""Provenance-safe merge of re-evaluation gaps into research analysis."""

from __future__ import annotations

from dataclasses import replace

from models import (
    ResearchAnalysis,
    ResearchGap,
)


def merge_reevaluation_research_gaps(
    analysis: ResearchAnalysis,
    reevaluation_gaps: list[ResearchGap],
) -> ResearchAnalysis:
    """
    Merge deterministic re-evaluation gaps into an existing ResearchAnalysis.

    Existing research state is authoritative and is never overwritten.

    Rules:
    - preserve existing gap order and objects;
    - append only new re-evaluation gaps;
    - deduplicate by gap_id;
    - an existing gap wins on gap_id collision;
    - never synthesize candidate × criterion linkage;
    - never mutate coverage or conflict analysis;
    - never mutate either input;
    - merge does not execute research.
    """

    for gap in reevaluation_gaps:
        if gap.gap_type != "reevaluation":
            raise ValueError(
                "reevaluation merge accepts only "
                "gap_type='reevaluation'"
            )

    existing_ids = {
        gap.gap_id
        for gap in analysis.research_gaps
    }

    additions: list[ResearchGap] = []
    added_ids: set[str] = set()

    for gap in reevaluation_gaps:
        if gap.gap_id in existing_ids:
            continue

        if gap.gap_id in added_ids:
            continue

        additions.append(gap)
        added_ids.add(gap.gap_id)

    if not additions:
        return analysis

    merged_gaps = [
        *analysis.research_gaps,
        *additions,
    ]

    return replace(
        analysis,
        research_gaps=merged_gaps,
        status="gaps_detected",
    )
