"""Deterministic context assembly for Agent LLM calls."""

from __future__ import annotations

from dataclasses import dataclass, field
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
