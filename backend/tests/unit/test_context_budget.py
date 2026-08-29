import pytest

from services.context_engineering import (
    CONTEXT_PRIORITY_CRITICAL,
    CONTEXT_PRIORITY_HIGH,
    CONTEXT_PRIORITY_LOW,
    ContextAssembler,
    ContextBudget,
    ContextBudgetPlanner,
    ContextSection,
    ContextSelection,
    ContextUnitEstimator,
)


def test_budget_keeps_sections_within_limit():
    selection = ContextSelection(
        purpose="test",
        sections=(
            ContextSection(
                name="A",
                content="aaa",
            ),
            ContextSection(
                name="B",
                content="bbb",
            ),
        ),
    )

    estimator = ContextUnitEstimator()

    required = sum(
        estimator.estimate(
            section
        )
        for section
        in selection.sections
    )

    result = ContextBudgetPlanner().apply(
        selection,
        ContextBudget(
            max_units=required,
        ),
    )

    assert len(
        result.selected_sections
    ) == 2

    assert not result.dropped_sections
    assert result.overflow is False


def test_budget_drops_lower_priority_first():
    critical = ContextSection(
        name="Critical",
        content="important",
        priority=
            CONTEXT_PRIORITY_CRITICAL,
    )

    low = ContextSection(
        name="Low",
        content="optional",
        priority=
            CONTEXT_PRIORITY_LOW,
    )

    estimator = ContextUnitEstimator()

    selection = ContextSelection(
        purpose="test",
        sections=(
            low,
            critical,
        ),
    )

    result = ContextBudgetPlanner().apply(
        selection,
        ContextBudget(
            max_units=
                estimator.estimate(
                    critical
                ),
        ),
    )

    assert (
        result.selected_sections
        == (
            critical,
        )
    )

    assert (
        result.dropped_sections
        == (
            low,
        )
    )


def test_budget_reserves_output_capacity():
    section = ContextSection(
        name="Context",
        content="abcdefghij",
    )

    estimated = (
        ContextUnitEstimator().estimate(
            section
        )
    )

    selection = ContextSelection(
        purpose="test",
        sections=(
            section,
        ),
    )

    result = ContextBudgetPlanner().apply(
        selection,
        ContextBudget(
            max_units=estimated,
            reserved_output_units=1,
        ),
    )

    assert not result.selected_sections
    assert result.dropped_sections
    assert result.available_units == (
        estimated - 1
    )


def test_budget_decisions_are_explicit():
    selection = ContextSelection(
        purpose="test",
        sections=(
            ContextSection(
                name="Important",
                content="hello",
                priority=
                    CONTEXT_PRIORITY_HIGH,
            ),
        ),
    )

    result = ContextBudgetPlanner().apply(
        selection,
        ContextBudget(
            max_units=0,
        ),
    )

    decision = result.decisions[0]

    assert (
        decision.section_name
        == "Important"
    )

    assert decision.included is False

    assert (
        decision.reason
        == "budget_exceeded"
    )


def test_empty_sections_do_not_consume_budget():
    selection = ContextSelection(
        purpose="test",
        sections=(
            ContextSection(
                name="Empty",
                content="   ",
            ),
        ),
    )

    result = ContextBudgetPlanner().apply(
        selection,
        ContextBudget(
            max_units=10,
        ),
    )

    assert result.used_units == 0
    assert not result.selected_sections

    assert (
        result.decisions[0].reason
        == "empty_section"
    )


def test_invalid_budget_rejected():
    planner = ContextBudgetPlanner()

    selection = ContextSelection(
        purpose="test"
    )

    with pytest.raises(
        ValueError
    ):
        planner.apply(
            selection,
            ContextBudget(
                max_units=-1,
            ),
        )


def test_budget_result_can_be_assembled():
    section = ContextSection(
        name="Important",
        content="hello",
        priority=
            CONTEXT_PRIORITY_HIGH,
    )

    selection = ContextSelection(
        purpose="test",
        sections=(
            section,
        ),
    )

    estimated = (
        ContextUnitEstimator().estimate(
            section
        )
    )

    budget_result = (
        ContextBudgetPlanner().apply(
            selection,
            ContextBudget(
                max_units=estimated,
            ),
        )
    )

    budgeted_selection = (
        ContextSelection(
            purpose=
                budget_result.purpose,
            sections=
                budget_result
                .selected_sections,
        )
    )

    assembled = (
        ContextAssembler().assemble(
            budgeted_selection
        )
    )

    assert "hello" in (
        assembled.rendered_text
    )


def test_budget_result_converts_back_to_selection():
    from services.context_engineering import (
        selection_from_budget_result,
    )

    section = ContextSection(
        name="Important",
        content="context",
    )

    original = ContextSelection(
        purpose="summary",
        sections=(
            section,
        ),
    )

    estimated = (
        ContextUnitEstimator().estimate(
            section
        )
    )

    result = ContextBudgetPlanner().apply(
        original,
        ContextBudget(
            max_units=estimated,
        ),
    )

    converted = (
        selection_from_budget_result(
            result
        )
    )

    assert (
        converted.purpose
        == "summary"
    )

    assert (
        converted.sections
        == (
            section,
        )
    )
