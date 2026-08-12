import sys

sys.path.insert(0, "src")

from services.planner import PlanningService
from models import SummaryState


class DummyConfig:
    strip_thinking_tokens = False


class DummyAgent:
    def run(self, prompt):
        return ""

    def clear_history(self):
        pass


def test_plan_todo_list_empty_response_baseline():
    service = PlanningService(
        DummyAgent(),
        DummyConfig(),
    )

    state = SummaryState(
        research_topic="test topic"
    )

    result = service.plan_todo_list(state)

    assert result == []
    assert service.last_parse_status == "empty_output"
