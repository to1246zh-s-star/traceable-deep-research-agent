from models import SummaryState
from services.research_store import InMemoryResearchStore


def test_store_saves_and_retrieves_research_state():
    store = InMemoryResearchStore()

    state = SummaryState(
        research_topic="test topic",
    )

    research_id = store.save(state)

    assert research_id.startswith("research_")
    assert store.get(research_id) is state


def test_store_returns_none_for_unknown_research_id():
    store = InMemoryResearchStore()

    assert store.get("research_missing") is None


def test_store_lists_saved_research_states():
    store = InMemoryResearchStore()

    first = SummaryState(research_topic="first")
    second = SummaryState(research_topic="second")

    first_id = store.save(first)
    second_id = store.save(second)

    items = store.list()

    assert len(items) == 2
    assert items[0][0] == first_id
    assert items[0][1] is first
    assert items[1][0] == second_id
    assert items[1][1] is second
