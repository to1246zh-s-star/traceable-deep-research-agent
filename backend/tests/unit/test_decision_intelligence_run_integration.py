from agent import DeepResearchAgent
from models import (
    DecisionCase,
    SummaryState,
    TodoItem,
)


class StubPlanner:
    def plan_todo_list(self, state):
        return [
            TodoItem(
                id=1,
                title="Research",
                intent="Research decision",
                query="test query",
            )
        ]


class StubReporting:
    def __init__(self):
        self.calls = []

    def generate_report(self, state):
        self.calls.append(state)
        return "final report"


def make_agent():
    agent = object.__new__(DeepResearchAgent)

    agent.planner = StubPlanner()
    agent.reporting = StubReporting()

    agent._last_state = None
    agent._last_search_notices = []

    agent._drain_tool_events = (
        lambda state, step=None: []
    )

    agent._persist_final_report = (
        lambda state, report: None
    )

    return agent


def test_run_executes_decision_intelligence_after_research():
    agent = make_agent()

    call_order = []

    decision = DecisionCase(
        decision_id="dec_run",
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
    ):
        call_order.append("research")
        task.status = "completed"
        if False:
            yield None

    def execute_intelligence(state):
        call_order.append("decision_intelligence")
        assert state.decision_case is decision
        return state

    agent._attach_decision_case = attach_decision
    agent._execute_task = execute_task
    agent.execute_decision_intelligence = (
        execute_intelligence
    )

    result = agent.run("Choose A or B")

    assert result.report_markdown == "final report"

    assert call_order == [
        "decision_case",
        "research",
        "decision_intelligence",
    ]


def test_run_skips_decision_intelligence_for_non_decision():
    agent = make_agent()

    calls = []

    agent._attach_decision_case = (
        lambda state: None
    )

    def execute_task(
        state,
        task,
        *,
        emit_stream,
    ):
        task.status = "completed"
        if False:
            yield None

    agent._execute_task = execute_task

    agent.execute_decision_intelligence = (
        lambda state: calls.append("decision")
    )

    result = agent.run(
        "Explain transformer attention"
    )

    assert result.report_markdown == "final report"
    assert calls == []


def test_run_decision_failure_does_not_block_report():
    agent = make_agent()

    decision = DecisionCase(
        decision_id="dec_fail",
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
    ):
        task.status = "completed"
        if False:
            yield None

    def fail_decision(state):
        raise RuntimeError(
            "semantic decision failure"
        )

    agent._attach_decision_case = attach_decision
    agent._execute_task = execute_task
    agent.execute_decision_intelligence = (
        fail_decision
    )

    result = agent.run("Choose A or B")

    assert result.report_markdown == "final report"
    assert agent.reporting.calls


def test_run_executes_adaptive_loop_after_initial_decision():
    call_order = []
    agent = make_agent()

    class RecordingReporting:
        def generate_report(self, state):
            call_order.append("report")
            return "final report"

    agent.reporting = RecordingReporting()

    decision = DecisionCase(
        decision_id="dec_adaptive_run",
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
        call_order.append("research")
        task.status = "completed"

        if False:
            yield None

    def execute_intelligence(state):
        call_order.append(
            "decision_intelligence"
        )
        return state

    def execute_adaptive_loop(state):
        call_order.append(
            "adaptive_loop"
        )
        return state

    agent._attach_decision_case = attach_decision
    agent._execute_task = execute_task
    agent.execute_decision_intelligence = (
        execute_intelligence
    )
    agent.execute_adaptive_decision_loop = (
        execute_adaptive_loop
    )

    result = agent.run(
        "Choose A or B"
    )

    assert result.report_markdown == "final report"
    assert result.running_summary == "final report"

    assert call_order.index(
        "research"
    ) < call_order.index(
        "decision_intelligence"
    )

    assert call_order.index(
        "decision_intelligence"
    ) < call_order.index(
        "adaptive_loop"
    )

    assert call_order.index(
        "adaptive_loop"
    ) < call_order.index(
        "report"
    )


def test_run_adaptive_loop_failure_does_not_block_report():
    call_order = []
    agent = make_agent()

    class RecordingReporting:
        def generate_report(self, state):
            call_order.append("report")
            return "final report"

    agent.reporting = RecordingReporting()

    decision = DecisionCase(
        decision_id="dec_adaptive_fail",
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

    def execute_intelligence(state):
        call_order.append(
            "decision_intelligence"
        )
        return state

    def fail_adaptive(state):
        call_order.append(
            "adaptive_loop"
        )
        raise RuntimeError(
            "adaptive failure"
        )

    agent._attach_decision_case = attach_decision
    agent._execute_task = execute_task
    agent.execute_decision_intelligence = (
        execute_intelligence
    )
    agent.execute_adaptive_decision_loop = (
        fail_adaptive
    )

    result = agent.run(
        "Choose A or B"
    )

    assert result.report_markdown == "final report"
    assert result.running_summary == "final report"

    assert "decision_intelligence" in (
        call_order
    )
    assert "adaptive_loop" in call_order
    assert "report" in call_order
