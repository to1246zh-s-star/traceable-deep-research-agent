"""Deterministic context assembly for Agent LLM calls."""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Iterable


CONTEXT_PRIORITY_CRITICAL = 0
CONTEXT_PRIORITY_HIGH = 10
CONTEXT_PRIORITY_NORMAL = 20
CONTEXT_PRIORITY_LOW = 30


@dataclass(kw_only=True, frozen=True)
class ContextSection:
    """One explicit section of LLM execution context."""

    name: str
    content: str

    priority: int = CONTEXT_PRIORITY_NORMAL

    source_ids: tuple[str, ...] = field(
        default_factory=tuple
    )

    required: bool = False

    metadata: tuple[
        tuple[str, str],
        ...
    ] = field(
        default_factory=tuple
    )


@dataclass(kw_only=True, frozen=True)
class ContextSelection:
    """
    Explicit context selected for one LLM invocation.

    Selection describes what the call is allowed to see.
    It is not a truth model and must not mutate SummaryState.
    """

    purpose: str

    sections: tuple[
        ContextSection,
        ...
    ] = field(
        default_factory=tuple
    )


@dataclass(kw_only=True, frozen=True)
class AssembledContext:
    """Deterministically rendered context ready for prompt composition."""

    purpose: str

    rendered_text: str

    included_section_names: tuple[
        str,
        ...
    ] = field(
        default_factory=tuple
    )

    source_ids: tuple[
        str,
        ...
    ] = field(
        default_factory=tuple
    )


class ContextAssembler:
    """
    Deterministically render selected context sections.

    This layer performs formatting only. It does not infer truth,
    rank candidates, modify evidence, or generate missing content.
    """

    def assemble(
        self,
        selection: ContextSelection,
    ) -> AssembledContext:
        sections = self._normalized_sections(
            selection.sections
        )

        rendered_parts: list[str] = []

        included_names: list[str] = []
        source_ids: list[str] = []
        seen_source_ids: set[str] = set()

        for section in sections:
            content = section.content.strip()

            if not content:
                continue

            rendered_parts.append(
                f"## {section.name}\n{content}"
            )

            included_names.append(
                section.name
            )

            for source_id in section.source_ids:
                normalized = str(
                    source_id
                ).strip()

                if (
                    not normalized
                    or normalized in seen_source_ids
                ):
                    continue

                seen_source_ids.add(
                    normalized
                )

                source_ids.append(
                    normalized
                )

        return AssembledContext(
            purpose=selection.purpose,
            rendered_text="\n\n".join(
                rendered_parts
            ),
            included_section_names=tuple(
                included_names
            ),
            source_ids=tuple(
                source_ids
            ),
        )

    @staticmethod
    def _normalized_sections(
        sections: Iterable[
            ContextSection
        ],
    ) -> list[
        ContextSection
    ]:
        """
        Return sections in deterministic priority order.

        Required sections do not receive special truth semantics.
        They only receive stable formatting precedence when priorities
        are otherwise equal.
        """

        indexed = list(
            enumerate(sections)
        )

        indexed.sort(
            key=lambda item: (
                item[1].priority,
                0 if item[1].required else 1,
                item[0],
            )
        )

        return [
            section
            for _, section in indexed
        ]


@dataclass(kw_only=True, frozen=True)
class ContextBudget:
    """
    Deterministic execution-context budget.

    Units are intentionally tokenizer-agnostic in Phase 46.2A.
    They represent an explicit size proxy, not provider token truth.
    """

    max_units: int

    reserved_output_units: int = 0

    def available_input_units(
        self,
    ) -> int:
        return max(
            0,
            self.max_units
            - self.reserved_output_units,
        )


@dataclass(kw_only=True, frozen=True)
class ContextBudgetDecision:
    """One deterministic include/drop decision for a context section."""

    section_name: str

    estimated_units: int

    included: bool

    reason: str

    priority: int


@dataclass(kw_only=True, frozen=True)
class ContextBudgetResult:
    """Result of applying one explicit context budget."""

    purpose: str

    selected_sections: tuple[
        ContextSection,
        ...
    ] = field(
        default_factory=tuple
    )

    dropped_sections: tuple[
        ContextSection,
        ...
    ] = field(
        default_factory=tuple
    )

    decisions: tuple[
        ContextBudgetDecision,
        ...
    ] = field(
        default_factory=tuple
    )

    used_units: int = 0

    available_units: int = 0

    overflow: bool = False


class ContextUnitEstimator:
    """
    Deterministic context-size estimator.

    Phase 46.2A deliberately uses character length instead of pretending
    to know provider tokenization.
    """

    def estimate(
        self,
        section: ContextSection,
    ) -> int:
        content = (
            section.content
            or ""
        ).strip()

        if not content:
            return 0

        rendered = (
            f"## {section.name}\n"
            f"{content}"
        )

        return len(rendered)


@dataclass(kw_only=True, frozen=True)
class ContextCompressionDecision:
    """Sanitized runtime description of one compressed section."""

    section_name: str
    original_estimated_units: int
    compressed_estimated_units: int
    strategy: str
    reason: str


@dataclass(kw_only=True, frozen=True)
class ContextCompressionResult:
    """Execution-only context plus sanitized compression decisions."""

    selection: ContextSelection
    decisions: tuple[ContextCompressionDecision, ...] = field(
        default_factory=tuple
    )


class ContextCompressor:
    """Deterministically compress oversized execution-context sections.

    Compression creates new ``ContextSection`` values. The selected source
    sections and all persistent evidence/state remain untouched.
    """

    STRATEGY = "semantic_head_tail"
    REASON = "section_exceeds_limit"
    BUDGET_REASON = "section_exceeds_remaining_budget"
    OMISSION_MARKER = "[... context compressed for execution ...]"

    def __init__(
        self,
        estimator: ContextUnitEstimator | None = None,
    ) -> None:
        self._estimator = estimator or ContextUnitEstimator()

    def compress(
        self,
        selection: ContextSelection,
        *,
        max_section_units: int,
    ) -> ContextCompressionResult:
        if max_section_units < 1:
            raise ValueError("max_section_units must be >= 1")

        sections: list[ContextSection] = []
        decisions: list[ContextCompressionDecision] = []

        for section in selection.sections:
            original_units = self._estimator.estimate(section)
            if original_units <= max_section_units:
                sections.append(section)
                continue

            compressed_content = self._compress_content(
                section.name,
                section.content,
                max_section_units,
            )
            compressed_section = ContextSection(
                name=section.name,
                content=compressed_content,
                priority=section.priority,
                source_ids=section.source_ids,
                required=section.required,
                metadata=section.metadata,
            )
            compressed_units = self._estimator.estimate(compressed_section)
            sections.append(compressed_section)
            decisions.append(
                ContextCompressionDecision(
                    section_name=section.name,
                    original_estimated_units=original_units,
                    compressed_estimated_units=compressed_units,
                    strategy=self.STRATEGY,
                    reason=self.REASON,
                )
            )

        return ContextCompressionResult(
            selection=ContextSelection(
                purpose=selection.purpose,
                sections=tuple(sections),
            ),
            decisions=tuple(decisions),
        )

    def compress_to_budget(
        self,
        selection: ContextSelection,
        budget: ContextBudget,
    ) -> ContextCompressionResult:
        """Compress optional sections against their actual remaining budget.

        Sections are evaluated in the same deterministic order used by the
        budget planner. Required sections are never compressed and their full
        estimated size is reserved before lower-priority sections are sized.
        """

        if budget.max_units < 0:
            raise ValueError("max_units must be >= 0")
        if budget.reserved_output_units < 0:
            raise ValueError("reserved_output_units must be >= 0")

        available = budget.available_input_units()
        used = 0
        replacements: dict[int, ContextSection] = {}
        decisions: list[ContextCompressionDecision] = []
        indexed_sections = list(enumerate(selection.sections))
        indexed_sections.sort(
            key=lambda item: (
                item[1].priority,
                0 if item[1].required else 1,
                item[0],
            )
        )

        for index, section in indexed_sections:
            original_units = self._estimator.estimate(section)
            if original_units == 0:
                continue

            remaining = max(0, available - used)
            if section.required or original_units <= remaining:
                used += original_units
                continue

            if remaining < self.minimum_safe_units(section.name):
                # Preserve the original immutable section. The budget planner
                # will explicitly record its normal budget_exceeded drop.
                continue

            compressed_content = self._compress_content(
                section.name,
                section.content,
                remaining,
            )
            compressed_section = ContextSection(
                name=section.name,
                content=compressed_content,
                priority=section.priority,
                source_ids=section.source_ids,
                required=section.required,
                metadata=section.metadata,
            )
            compressed_units = self._estimator.estimate(compressed_section)
            if compressed_units > remaining:
                continue

            replacements[index] = compressed_section
            used += compressed_units
            decisions.append(
                ContextCompressionDecision(
                    section_name=section.name,
                    original_estimated_units=original_units,
                    compressed_estimated_units=compressed_units,
                    strategy=self.STRATEGY,
                    reason=self.BUDGET_REASON,
                )
            )

        return ContextCompressionResult(
            selection=ContextSelection(
                purpose=selection.purpose,
                sections=tuple(
                    replacements.get(index, section)
                    for index, section in enumerate(selection.sections)
                ),
            ),
            decisions=tuple(decisions),
        )

    @classmethod
    def minimum_safe_units(cls, section_name: str) -> int:
        """Minimum rendering size that keeps a marker and both fragments."""

        return (
            len(f"## {section_name}\n")
            + len(f"\n\n{cls.OMISSION_MARKER}\n\n")
            + 2
        )

    def _compress_content(
        self,
        section_name: str,
        content: str,
        max_units: int,
    ) -> str:
        normalized = (content or "").strip()
        content_limit = max(0, max_units - len(f"## {section_name}\n"))
        marker = self.OMISSION_MARKER

        if content_limit <= len(marker):
            return marker[:content_limit]

        # Prefer paragraph, line, then sentence boundaries. The last fallback
        # handles an indivisible block while retaining both ends explicitly.
        candidates = [
            [part.strip() for part in re.split(r"\n\s*\n", normalized) if part.strip()],
            [part.strip() for part in normalized.splitlines() if part.strip()],
            [part.strip() for part in re.split(r"(?<=[.!?])\s+", normalized) if part.strip()],
        ]
        for blocks in candidates:
            if len(blocks) > 1:
                value = self._fit_blocks(blocks, content_limit, marker)
                if value:
                    return value

        separator = f"\n\n{marker}\n\n"
        remaining = max(0, content_limit - len(separator))
        head = (remaining + 1) // 2
        tail = remaining // 2
        return f"{normalized[:head]}{separator}{normalized[-tail:] if tail else ''}"

    @staticmethod
    def _fit_blocks(
        blocks: list[str],
        limit: int,
        marker: str,
    ) -> str:
        separator = "\n\n"
        kept_head: list[str] = []
        kept_tail: list[str] = []
        left = 0
        right = len(blocks) - 1

        while left <= right:
            target = kept_head if len(kept_head) <= len(kept_tail) else kept_tail
            block = blocks[left] if target is kept_head else blocks[right]
            trial_head = kept_head + ([block] if target is kept_head else [])
            trial_tail = ([block] if target is kept_tail else []) + kept_tail
            trial = separator.join(trial_head + [marker] + trial_tail)
            if len(trial) > limit:
                break
            if target is kept_head:
                kept_head.append(block)
                left += 1
            else:
                kept_tail.insert(0, block)
                right -= 1

        # A one-sided result can preserve a short label while omitting the
        # entire oversized body (for example, a two-line Task Context). Let
        # the caller use the marked character fallback unless both semantic
        # ends are represented.
        if not kept_head or not kept_tail:
            return ""
        return separator.join(kept_head + [marker] + kept_tail)


class ContextBudgetPlanner:
    """
    Apply deterministic budget policy to selected context.

    Priority controls execution-context retention only. It must never be
    interpreted as evidence quality, candidate score, or decision truth.
    """

    def __init__(
        self,
        estimator: ContextUnitEstimator
        | None = None,
    ) -> None:
        self._estimator = (
            estimator
            or ContextUnitEstimator()
        )

    def apply(
        self,
        selection: ContextSelection,
        budget: ContextBudget,
    ) -> ContextBudgetResult:
        if budget.max_units < 0:
            raise ValueError(
                "max_units must be >= 0"
            )

        if budget.reserved_output_units < 0:
            raise ValueError(
                "reserved_output_units must be >= 0"
            )

        available = (
            budget.available_input_units()
        )

        ordered_sections = (
            ContextAssembler
            ._normalized_sections(
                selection.sections
            )
        )

        selected: list[
            ContextSection
        ] = []

        dropped: list[
            ContextSection
        ] = []

        decisions: list[
            ContextBudgetDecision
        ] = []

        used = 0

        for section in ordered_sections:
            estimated = (
                self._estimator.estimate(
                    section
                )
            )

            if estimated == 0:
                dropped.append(
                    section
                )

                decisions.append(
                    ContextBudgetDecision(
                        section_name=
                            section.name,
                        estimated_units=0,
                        included=False,
                        reason=
                            "empty_section",
                        priority=
                            section.priority,
                    )
                )

                continue

            remaining = max(
                0,
                available - used,
            )

            if estimated <= remaining:
                selected.append(
                    section
                )

                used += estimated

                decisions.append(
                    ContextBudgetDecision(
                        section_name=
                            section.name,
                        estimated_units=
                            estimated,
                        included=True,
                        reason=
                            "within_budget",
                        priority=
                            section.priority,
                    )
                )

                continue

            dropped.append(
                section
            )

            decisions.append(
                ContextBudgetDecision(
                    section_name=
                        section.name,
                    estimated_units=
                        estimated,
                    included=False,
                    reason=
                        "budget_exceeded",
                    priority=
                        section.priority,
                )
            )

        return ContextBudgetResult(
            purpose=selection.purpose,
            selected_sections=tuple(
                selected
            ),
            dropped_sections=tuple(
                dropped
            ),
            decisions=tuple(
                decisions
            ),
            used_units=used,
            available_units=available,
            overflow=bool(
                dropped
            ),
        )


def selection_from_budget_result(
    result: ContextBudgetResult,
) -> ContextSelection:
    """Convert a budget decision back into an assemblable selection."""

    return ContextSelection(
        purpose=result.purpose,
        sections=result.selected_sections,
    )
