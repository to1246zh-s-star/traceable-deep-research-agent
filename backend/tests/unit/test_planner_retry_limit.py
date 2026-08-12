import sys

sys.path.insert(0, "src")

from models import SummaryState
from services.planner import PlanningService


class DummyConfig:
    strip_thinking_tokens = False


class AlwaysFailAgent:
    def __init__(self):
        self.calls = 0

    def run(self, prompt):
        self.calls += 1
        return '{"tasks": [}'


    def clear_history(self):
        pass


def test_retry_should_only_happen_once():
    agent = AlwaysFailAgent()

    service = PlanningService(
        agent,
        DummyConfig(),
    )

    state = SummaryState(
        research_topic="test topic"
    )

    result = service.plan_todo_list(state)

    assert result == []
    assert agent.calls == 2
    assert service.retry_count == 1
