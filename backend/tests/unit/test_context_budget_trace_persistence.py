from models import (
    ContextBudgetTrace,
    ContextBudgetTraceDecision,
    SummaryState,
)

from services.research_store import (
    SQLiteResearchStore,
)


def test_context_budget_trace_round_trip(
    tmp_path,
):
    store = SQLiteResearchStore(
        tmp_path / "research.db"
    )

    state = SummaryState(
        research_topic="Context tracing"
    )

    state.context_budget_traces.append(
        ContextBudgetTrace(
            purpose="task_summary",
            available_units=10000,
            used_units=1500,
            overflow=True,
            decisions=[
                ContextBudgetTraceDecision(
                    section_name=
                        "Task Context",
                    estimated_units=20000,
                    priority=20,
                    included=False,
                    reason=
                        "budget_exceeded",
                )
            ],
        )
    )

    research_id = store.save(
        state
    )

    loaded = store.get(
        research_id
    )

    assert loaded is not None

    assert len(
        loaded.context_budget_traces
    ) == 1

    trace = (
        loaded.context_budget_traces[0]
    )

    assert (
        trace.purpose
        == "task_summary"
    )

    assert trace.overflow is True

    assert (
        trace.decisions[0]
        .section_name
        == "Task Context"
    )

    assert (
        trace.decisions[0]
        .reason
        == "budget_exceeded"
    )
