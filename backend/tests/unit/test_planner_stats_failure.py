from services.planner import PlanningService
from models import SummaryState


class DummyConfig:
    strip_thinking_tokens = False


class AlwaysFailAgent:
    def __init__(self):
        self.calls = 0
        self.prompts = []

    def run(self, prompt):
        self.calls += 1
        self.prompts.append(prompt)
        return '{"tasks": [}'

    def clear_history(self):
        pass


def test_planner_should_record_retry_failure_stats():
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

    assert service.stats["calls"] == 2
    assert service.stats["retry_count"] == 1
    assert service.stats["failures"] == 1
    assert service.stats["final_status"] == "retry_failed"
