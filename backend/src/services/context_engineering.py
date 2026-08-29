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
