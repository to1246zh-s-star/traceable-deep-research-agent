import sys

sys.path.insert(0, "src")

from services.planner import PlanningService


class DummyConfig:
    strip_thinking_tokens = False


def test_invalid_json_should_record_status():
    service = PlanningService.__new__(PlanningService)
    service._config = DummyConfig()
    service.last_parse_status = "unknown"

    result = service._extract_tasks(
        '{"tasks": [}'
    )

    assert result == []
    assert service.last_parse_status == "json_error"
