import sys

sys.path.insert(0, "src")

from services.planner import PlanningService
from models import SummaryState


class DummyConfig:
    strip_thinking_tokens = False


class JsonRetryAgent:
    def __init__(self):
        self.calls = 0

    def run(self, prompt):
        self.calls += 1

        if self.calls == 1:
            return '{"tasks": [}'

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


def test_json_error_should_retry_once():
    agent = JsonRetryAgent()

    service = PlanningService(
        agent,
        DummyConfig(),
    )

    state = SummaryState(
        research_topic="test topic"
    )

    result = service.plan_todo_list(state)

    assert len(result) == 1
    assert agent.calls == 2
