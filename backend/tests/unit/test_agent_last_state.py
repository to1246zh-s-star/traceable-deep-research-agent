from agent import DeepResearchAgent
from models import SummaryState


def test_last_state_defaults_to_none_for_lightweight_agent():
    agent = DeepResearchAgent.__new__(DeepResearchAgent)

    assert agent.last_state is None


def test_last_state_exposes_current_research_state():
    agent = DeepResearchAgent.__new__(DeepResearchAgent)

    state = SummaryState(
        research_topic="test topic",
    )

    agent._last_state = state

    assert agent.last_state is state
    assert agent.last_state.research_topic == "test topic"
