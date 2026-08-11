from fastapi.testclient import TestClient

import main
from models import SummaryState, SummaryStateOutput, TodoItem


class FakeAgent:
    def __init__(self, config=None):
        self._last_state = None

    @property
    def last_state(self):
        return self._last_state

    def run(self, topic: str):
        state = SummaryState(research_topic=topic)

        state.todo_items = [
            TodoItem(
                id=1,
                title="Test task",
                intent="test",
                query="test query",
                status="completed",
                summary="summary",
            )
        ]

        self._last_state = state

        return SummaryStateOutput(
            running_summary="report",
            report_markdown="report",
            todo_items=state.todo_items,
        )


def test_research_response_contains_research_id(monkeypatch):
    monkeypatch.setattr(main, "DeepResearchAgent", FakeAgent)

    app = main.create_app()
    client = TestClient(app)

    response = client.post(
        "/research",
        json={"topic": "test topic"},
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["research_id"].startswith("research_")
    assert payload["report_markdown"] == "report"
