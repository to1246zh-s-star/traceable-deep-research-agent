import sys

sys.path.insert(0, "src")

from services.planner import PlanningService


class DummyConfig:
    strip_thinking_tokens = False


def test_invalid_schema_should_record_status():
    service = PlanningService.__new__(PlanningService)
    service._config = DummyConfig()

    result = service._extract_tasks(
        '{"tasks":"hello"}'
    )

    assert result == []
    assert service.last_parse_status == "invalid_schema"
