from models import (
    SummaryState,
    TodoItem,
)

from services.reporter import (
    ReportingService,
)


class RecordingAgent:
    def __init__(self):
        self.prompts = []

    def run(self, prompt):
        self.prompts.append(prompt)
        return "final report"

    def clear_history(self):
        pass


class Config:
    strip_thinking_tokens = False


def test_reporter_uses_assembled_context():
    agent = RecordingAgent()

    service = ReportingService(
        agent,
        Config(),
    )

    state = SummaryState(
        research_topic="Choose database",
        todo_items=[
            TodoItem(
                id=1,
                title="Performance",
                intent="Compare performance",
                query="database benchmark",
                status="completed",
                summary="PostgreSQL performed well",
                sources_summary="Benchmark source",
            )
        ],
    )

    result = service.generate_report(
        state
    )

    assert result == "final report"

    prompt = agent.prompts[0]

    assert "## Research Topic" in prompt
    assert "Choose database" in prompt

    assert "## Research Tasks" in prompt
    assert (
        "PostgreSQL performed well"
        in prompt
    )

    assert "REPORT INSTRUCTION:" in prompt


def test_reporter_context_keeps_tool_instruction():
    agent = RecordingAgent()

    service = ReportingService(
        agent,
        Config(),
    )

    state = SummaryState(
        research_topic="Topic",
        todo_items=[
            TodoItem(
                id=1,
                title="Task",
                intent="Intent",
                query="Query",
                note_id="note_123",
            )
        ],
    )

    service.generate_report(
        state
    )

    prompt = agent.prompts[0]

    assert "note_123" in prompt
    assert "[TOOL_CALL:note:" in prompt
