from services.context_engineering import (
    CONTEXT_PRIORITY_CRITICAL,
    CONTEXT_PRIORITY_HIGH,
    CONTEXT_PRIORITY_LOW,
    AssembledContext,
    ContextAssembler,
    ContextSection,
    ContextSelection,
)


def test_context_assembler_renders_sections():
    assembler = ContextAssembler()

    selection = ContextSelection(
        purpose="reporting",
        sections=(
            ContextSection(
                name="Research Topic",
                content="Choose a database",
            ),
            ContextSection(
                name="Research Results",
                content="Task results",
            ),
        ),
    )

    result = assembler.assemble(
        selection
    )

    assert isinstance(
        result,
        AssembledContext,
    )

    assert result.purpose == "reporting"

    assert (
        "## Research Topic\n"
        "Choose a database"
        in result.rendered_text
    )

    assert (
        "## Research Results\n"
        "Task results"
        in result.rendered_text
    )


def test_context_assembler_orders_by_priority():
    assembler = ContextAssembler()

    selection = ContextSelection(
        purpose="test",
        sections=(
            ContextSection(
                name="Low",
                content="low",
                priority=CONTEXT_PRIORITY_LOW,
            ),
            ContextSection(
                name="Critical",
                content="critical",
                priority=
                    CONTEXT_PRIORITY_CRITICAL,
            ),
            ContextSection(
                name="High",
                content="high",
                priority=
                    CONTEXT_PRIORITY_HIGH,
            ),
        ),
    )

    result = assembler.assemble(
        selection
    )

    assert (
        result.included_section_names
        == (
            "Critical",
            "High",
            "Low",
        )
    )


def test_empty_context_sections_are_skipped():
    assembler = ContextAssembler()

    selection = ContextSelection(
        purpose="test",
        sections=(
            ContextSection(
                name="Empty",
                content="   ",
            ),
            ContextSection(
                name="Present",
                content="value",
            ),
        ),
    )

    result = assembler.assemble(
        selection
    )

    assert (
        result.included_section_names
        == (
            "Present",
        )
    )

    assert "Empty" not in (
        result.rendered_text
    )


def test_context_source_ids_are_deduplicated():
    assembler = ContextAssembler()

    selection = ContextSelection(
        purpose="grounding",
        sections=(
            ContextSection(
                name="Evidence A",
                content="A",
                source_ids=(
                    "ev_1",
                    "ev_2",
                ),
            ),
            ContextSection(
                name="Evidence B",
                content="B",
                source_ids=(
                    "ev_2",
                    "ev_3",
                ),
            ),
        ),
    )

    result = assembler.assemble(
        selection
    )

    assert result.source_ids == (
        "ev_1",
        "ev_2",
        "ev_3",
    )


def test_context_assembly_does_not_mutate_selection():
    assembler = ContextAssembler()

    section = ContextSection(
        name="Original",
        content="content",
        source_ids=(
            "ev_1",
        ),
    )

    selection = ContextSelection(
        purpose="test",
        sections=(
            section,
        ),
    )

    before = selection

    assembler.assemble(
        selection
    )

    assert selection == before
    assert (
        selection.sections[0]
        is section
    )


def test_required_only_affects_stable_ordering():
    assembler = ContextAssembler()

    selection = ContextSelection(
        purpose="test",
        sections=(
            ContextSection(
                name="Optional",
                content="optional",
                priority=10,
                required=False,
            ),
            ContextSection(
                name="Required",
                content="required",
                priority=10,
                required=True,
            ),
        ),
    )

    result = assembler.assemble(
        selection
    )

    assert (
        result.included_section_names
        == (
            "Required",
            "Optional",
        )
    )
