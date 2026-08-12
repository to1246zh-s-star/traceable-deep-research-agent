from threading import Lock

from agent import DeepResearchAgent
from models import (
    AdaptiveResearchState,
    ResearchAnalysis,
    ResearchGap,
    SummaryState,
)


def test_agent_executes_followup_using_existing_task_executor():
    agent = DeepResearchAgent.__new__(
        DeepResearchAgent
    )

    agent._state_lock = Lock()

    executed_task_ids = []

    def fake_execute_task(
        state,
        task,
        *,
        emit_stream,
        step=None,
    ):
        executed_task_ids.append(task.id)
        task.status = "completed"

        if False:
            yield {}

    agent._execute_task = fake_execute_task

    state = SummaryState(
        research_topic="vector database",
    )

    analysis = ResearchAnalysis(
        decision_id="dec_test",
        research_gaps=[
            ResearchGap(
                gap_id="gap_test",
                candidate_id="cand_test",
                criterion_id="crit_test",
                gap_type="low_coverage",
                severity=0.9,
                description="Need more evidence",
                suggested_query=(
                    "Qdrant reliability benchmark"
                ),
            )
        ],
    )

    adaptive_state = AdaptiveResearchState(
        decision_id="dec_test",
    )

    iteration = agent.execute_adaptive_followups(
        state,
        analysis,
        adaptive_state,
    )

    assert iteration is not None

    assert executed_task_ids == [1]

    assert len(state.todo_items) == 1

    task = state.todo_items[0]

    assert task.query == (
        "Qdrant reliability benchmark"
    )

    assert task.status == "completed"

    assert iteration.status == "completed"
    assert adaptive_state.iteration_count == 1
