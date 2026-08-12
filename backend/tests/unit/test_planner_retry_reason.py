import sys

sys.path.insert(0, "src")

from models import SummaryState
from services.planner import PlanningService


class DummyConfig:
    strip_thinking_tokens = False


class JsonFailAgent:
    def __init__(self):
        self.calls = 0

    def run(self, prompt):
        self.calls += 1
        return '{"tasks": [}'

    def clear_history(self):
        pass


def test_retry_should_record_retry_reason():
    agent = JsonFailAgent()

    service = PlanningService(
        agent,
        DummyConfig(),
    )

    state = SummaryState(
        research_topic="test topic"
    )

    result = service.plan_todo_list(state)

    assert result == []
    assert service.retry_count == 1
    assert service.retry_reason == "json_error"
