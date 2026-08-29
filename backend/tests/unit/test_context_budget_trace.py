from models import (
    SummaryState,
)

from services.context_budget_trace import (
    build_context_budget_trace,
    record_context_budget_trace,
)

from services.context_engineering import (
    ContextBudget,
    ContextBudgetPlanner,
    ContextSection,
    ContextSelection,
)


def _budget_result():
    selection = ContextSelection(
        purpose="task_summary",
        sections=(
            ContextSection(
                name="Critical",
                content="small",
                priority=0,
            ),
            ContextSection(
                name="Large",
                content="x" * 1000,
                priority=20,
            ),
        ),
    )

    return ContextBudgetPlanner().apply(
        selection,
        ContextBudget(
            max_units=100,
        ),
    )


def test_budget_trace_is_sanitized():
    result = _budget_result()

    trace = build_context_budget_trace(
        result
    )

    assert (
        trace.purpose
        == "task_summary"
    )

    assert len(trace.decisions) == 2

    serialized = repr(trace)

    assert "x" * 100 not in serialized
    assert "small" not in serialized


def test_budget_trace_preserves_decisions():
    result = _budget_result()

    trace = build_context_budget_trace(
        result
    )

    decisions = {
        item.section_name: item
        for item in trace.decisions
    }

    assert (
        decisions["Critical"].included
        is True
    )

    assert (
        decisions["Critical"].reason
        == "within_budget"
    )

    assert (
        decisions["Large"].included
        is False
    )

    assert (
        decisions["Large"].reason
        == "budget_exceeded"
    )


def test_record_budget_trace_appends_to_state():
    state = SummaryState(
        research_topic="Topic"
    )

    result = _budget_result()

    trace = record_context_budget_trace(
        state,
        result,
    )

    assert (
        state.context_budget_traces
        == [trace]
    )


def test_budget_trace_contains_no_section_content_field():
    result = _budget_result()

    trace = build_context_budget_trace(
        result
    )

    decision = trace.decisions[0]

    assert not hasattr(
        decision,
        "content",
    )

    assert not hasattr(
        trace,
        "rendered_text",
    )

    assert not hasattr(
        trace,
        "prompt",
    )
