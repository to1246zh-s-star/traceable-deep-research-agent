from agent import DeepResearchAgent
from models import DecisionCase, TodoItem


class StubPlanner:
    def plan_todo_list(self, state):
        return [
            TodoItem(
                id=1,
                title="Research A",
                intent="Research candidate A",
                query="candidate A",
            ),
            TodoItem(
                id=2,
                title="Research B",
                intent="Research candidate B",
                query="candidate B",
            ),
        ]

    def create_fallback_task(self, state):
        raise AssertionError("fallback should not be used")


class StubReporting:
    def __init__(self, call_order):
        self.call_order = call_order

    def generate_report(self, state):
        self.call_order.append("report")
        return "stream final report"


def make_agent(call_order):
    agent = object.__new__(DeepResearchAgent)

    agent.planner = StubPlanner()
    agent.reporting = StubReporting(call_order)

    agent._last_state = None
    agent._last_search_notices = []

    agent._drain_tool_events = lambda state, step=None: []
    agent._set_tool_event_sink = lambda sink: None
    agent._persist_final_report = lambda state, report: None

    return agent


def test_stream_runs_decision_after_all_research_before_report():
    call_order = []
    agent = make_agent(call_order)

    decision = DecisionCase(
        decision_id="dec_stream",
        question="Choose A or B",
    )

    def attach_decision(state):
        state.decision_case = decision
        call_order.append("decision_case")
        return decision

    def execute_task(
        state,
        task,
        *,
        emit_stream,
        step=None,
    ):
        call_order.append(f"research_{task.id}")
        task.status = "completed"

        yield {
            "type": "task_status",
            "task_id": task.id,
            "status": "completed",
        }

    def execute_intelligence(state):
        completed = {
            task.id
            for task in state.todo_items
            if task.status == "completed"
        }

        assert completed == {1, 2}

        call_order.append("decision_intelligence")
        return state

    agent._attach_decision_case = attach_decision
    agent._execute_task = execute_task
    agent.execute_decision_intelligence = execute_intelligence

    events = list(
        agent.run_stream("Choose A or B")
    )

    assert call_order.index(
        "decision_intelligence"
    ) > call_order.index("research_1")

    assert call_order.index(
        "decision_intelligence"
    ) > call_order.index("research_2")

    assert call_order.index(
        "decision_intelligence"
    ) < call_order.index("report")

    assert events[-2]["type"] == "final_report"
    assert events[-1]["type"] == "done"


def test_stream_skips_decision_for_non_decision():
    call_order = []
    agent = make_agent(call_order)

    agent._attach_decision_case = lambda state: None

    def execute_task(
        state,
        task,
        *,
        emit_stream,
        step=None,
    ):
        task.status = "completed"

        yield {
            "type": "task_status",
            "task_id": task.id,
            "status": "completed",
        }

    agent._execute_task = execute_task

    agent.execute_decision_intelligence = (
        lambda state: call_order.append(
            "decision_intelligence"
        )
    )

    events = list(
        agent.run_stream(
            "Explain transformer attention"
        )
    )

    assert "decision_intelligence" not in call_order
    assert "report" in call_order
    assert events[-1]["type"] == "done"


def test_stream_decision_failure_does_not_block_report():
    call_order = []
    agent = make_agent(call_order)

    decision = DecisionCase(
        decision_id="dec_stream_fail",
        question="Choose A or B",
    )

    def attach_decision(state):
        state.decision_case = decision
        return decision

    def execute_task(
        state,
        task,
        *,
        emit_stream,
        step=None,
    ):
        task.status = "completed"

        if False:
            yield None

    def fail_decision(state):
        call_order.append("decision_intelligence")
        raise RuntimeError(
            "semantic decision failure"
        )

    agent._attach_decision_case = attach_decision
    agent._execute_task = execute_task
    agent.execute_decision_intelligence = fail_decision

    events = list(
        agent.run_stream("Choose A or B")
    )

    assert "decision_intelligence" in call_order
    assert "report" in call_order

    assert call_order.index(
        "decision_intelligence"
    ) < call_order.index("report")

    assert any(
        event.get("type") == "final_report"
        for event in events
    )

    assert events[-1]["type"] == "done"
