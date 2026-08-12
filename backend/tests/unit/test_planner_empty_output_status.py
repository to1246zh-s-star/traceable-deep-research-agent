import sys

sys.path.insert(0, "src")

from services.planner import PlanningService


class DummyConfig:
    strip_thinking_tokens = False


def test_empty_output_should_record_status():
    service = PlanningService.__new__(PlanningService)
    service._config = DummyConfig()
    service.last_parse_status = "unknown"

    result = service._extract_tasks("")

    assert result == []
    assert service.last_parse_status == "empty_output"
