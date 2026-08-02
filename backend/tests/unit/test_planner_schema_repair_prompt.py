import sys

sys.path.insert(0, "src")

from models import SummaryState
from services.planner import PlanningService


class DummyConfig:
    strip_thinking_tokens = False


class SchemaRepairAgent:
    def __init__(self):
        self.calls = 0
        self.prompts = []

    def run(self, prompt):
        self.calls += 1
        self.prompts.append(prompt)

        if self.calls == 1:
            return '{"tasks":"hello"}'

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


def test_invalid_schema_retry_should_use_repair_prompt():
    agent = SchemaRepairAgent()

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

    retry_prompt = agent.prompts[1]

    assert "schema" in retry_prompt.lower()
    assert "tasks" in retry_prompt.lower()
    assert "json" in retry_prompt.lower()
