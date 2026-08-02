import sys

sys.path.insert(0, "src")

from services.planner import PlanningService


class DummyConfig:
    strip_thinking_tokens = False


service = PlanningService.__new__(PlanningService)
service._config = DummyConfig()


text = """
```json
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

result = service._extract_json_payload(text)

print(result)
