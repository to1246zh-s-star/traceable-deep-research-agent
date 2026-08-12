import sys

sys.path.insert(0, "src")

from services.planner import PlanningService


class DummyConfig:
    strip_thinking_tokens = False


def test_invalid_tasks_type_returns_empty_list():
    service = PlanningService.__new__(PlanningService)
    service._config = DummyConfig()

    result = service._extract_tasks(
        '{"tasks": "hello"}'
    )

    assert result == []
