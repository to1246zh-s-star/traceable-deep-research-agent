from services.research_store import InMemoryResearchStore, ResearchStore
from models import SummaryState


def test_in_memory_store_satisfies_research_store_protocol() -> None:
    store: ResearchStore = InMemoryResearchStore()

    state = SummaryState(
        research_topic="Protocol test",
    )

    research_id = store.save(state)

    assert research_id.startswith("research_")
    assert store.get(research_id) is state
    assert store.list() == [(research_id, state)]


def test_in_memory_store_returns_none_for_unknown_research_id() -> None:
    store: ResearchStore = InMemoryResearchStore()

    assert store.get("research_missing") is None
