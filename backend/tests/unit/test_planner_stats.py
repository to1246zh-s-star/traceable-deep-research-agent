import sys

sys.path.insert(0, "src")

from models import SummaryState
from services.planner import PlanningService


class DummyConfig:
    strip_thinking_tokens = False


class SuccessAgent:
    def __init__(self):
        self.calls = 0

    def run(self, prompt):
        self.calls += 1
        return """
        {
          "tasks": [
            {
              "title": "test",
              "intent": "test intent",
              "query": "test query"
            }
          ]
        }
        """

    def clear_history(self):
        pass


def test_planner_should_record_success_stats():
    agent = SuccessAgent()

    service = PlanningService(
        agent,
        DummyConfig(),
    )

    state = SummaryState(
        research_topic="test topic"
    )

    result = service.plan_todo_list(state)

    assert len(result) == 1

    assert service.stats["calls"] == 1
    assert service.stats["retry_count"] == 0
    assert service.stats["final_status"] == "success"
