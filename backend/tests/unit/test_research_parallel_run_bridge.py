from agent import DeepResearchAgent
from config import Configuration
from models import (
    SummaryStateOutput,
    TodoItem,
)


def test_run_uses_initial_task_executor():
    agent = DeepResearchAgent.__new__(
        DeepResearchAgent
    )

    agent.config = Configuration(
        enable_notes=False,
        max_concurrent_research_tasks=3,
    )

    agent._last_state = None

    agent._attach_decision_case = (
        lambda state: None
    )

    agent._drain_tool_events = (
        lambda state: []
    )

    agent._persist_final_report = (
        lambda state, report: None
    )

    class Planner:
        def plan_todo_list(
            self,
            state,
        ):
            return [
                TodoItem(
                    id=1,
                    title="A",
                    intent="A",
                    query="A",
                ),
                TodoItem(
                    id=2,
                    title="B",
                    intent="B",
                    query="B",
                ),
            ]

    class Reporter:
        def generate_report(
            self,
            state,
        ):
            return "report"

    agent.planner = Planner()
    agent.reporting = Reporter()

    calls = []

    def execute_initial(
        state,
    ):
        calls.append(
            [
                item.id
                for item
                in state.todo_items
            ]
        )

        for item in state.todo_items:
            item.status = "completed"

    agent._execute_initial_tasks = (
        execute_initial
    )

    result = agent.run(
        "research topic"
    )

    assert isinstance(
        result,
        SummaryStateOutput,
    )

    assert calls == [
        [
            1,
            2,
        ]
    ]

    assert result.report_markdown == (
        "report"
    )
