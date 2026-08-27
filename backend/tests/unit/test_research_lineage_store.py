import sqlite3

import pytest

from models import SummaryState
from services.research_store import (
    InMemoryResearchStore,
    SQLiteResearchStore,
)


def test_sqlite_initial_run_gets_root_lineage(
    tmp_path,
):
    store = SQLiteResearchStore(
        tmp_path / "research.db"
    )

    research_id = store.save(
        SummaryState(
            research_topic="initial",
        )
    )

    lineage = store.get_lineage(
        research_id
    )

    assert lineage is not None

    assert lineage.research_id == research_id
    assert (
        lineage.root_research_id
        == research_id
    )
    assert lineage.parent_research_id is None
    assert lineage.version_number == 1
    assert (
        lineage.creation_reason
        == "initial_research"
    )
    assert (
        lineage.created_from_trigger_ids
        == []
    )


def test_sqlite_child_inherits_root_and_increments_version(
    tmp_path,
):
    store = SQLiteResearchStore(
        tmp_path / "research.db"
    )

    root_id = store.save(
        SummaryState(
            research_topic="v1",
        )
    )

    child_id = store.save(
        SummaryState(
            research_topic="v2",
        ),
        parent_research_id=root_id,
        creation_reason="reevaluation",
        created_from_trigger_ids=[
            "trg_a",
        ],
    )

    lineage = store.get_lineage(
        child_id
    )

    assert lineage is not None

    assert lineage.root_research_id == root_id
    assert lineage.parent_research_id == root_id
    assert lineage.version_number == 2

    assert (
        lineage.creation_reason
        == "reevaluation"
    )

    assert (
        lineage.created_from_trigger_ids
        == ["trg_a"]
    )


def test_sqlite_grandchild_keeps_original_root(
    tmp_path,
):
    store = SQLiteResearchStore(
        tmp_path / "research.db"
    )

    v1 = store.save(
        SummaryState(
            research_topic="v1",
        )
    )

    v2 = store.save(
        SummaryState(
            research_topic="v2",
        ),
        parent_research_id=v1,
        creation_reason="reevaluation",
    )

    v3 = store.save(
        SummaryState(
            research_topic="v3",
        ),
        parent_research_id=v2,
        creation_reason="reevaluation",
    )

    lineage = store.get_lineage(v3)

    assert lineage is not None
    assert lineage.root_research_id == v1
    assert lineage.parent_research_id == v2
    assert lineage.version_number == 3


def test_sqlite_rejects_unknown_parent(
    tmp_path,
):
    store = SQLiteResearchStore(
        tmp_path / "research.db"
    )

    with pytest.raises(
        ValueError,
        match="parent research run not found",
    ):
        store.save(
            SummaryState(
                research_topic="bad",
            ),
            parent_research_id=(
                "research_missing"
            ),
            creation_reason="reevaluation",
        )


def test_sqlite_deduplicates_exact_trigger_ids(
    tmp_path,
):
    store = SQLiteResearchStore(
        tmp_path / "research.db"
    )

    parent = store.save(
        SummaryState(
            research_topic="v1",
        )
    )

    child = store.save(
        SummaryState(
            research_topic="v2",
        ),
        parent_research_id=parent,
        creation_reason="reevaluation",
        created_from_trigger_ids=[
            "trg_a",
            "trg_a",
            "",
            "  ",
            "TRG_A",
        ],
    )

    lineage = store.get_lineage(child)

    assert lineage is not None

    assert (
        lineage.created_from_trigger_ids
        == [
            "trg_a",
            "TRG_A",
        ]
    )


def test_sqlite_lineage_survives_restart(
    tmp_path,
):
    db_path = tmp_path / "research.db"

    writer = SQLiteResearchStore(
        db_path
    )

    parent = writer.save(
        SummaryState(
            research_topic="v1",
        )
    )

    child = writer.save(
        SummaryState(
            research_topic="v2",
        ),
        parent_research_id=parent,
        creation_reason="reevaluation",
        created_from_trigger_ids=[
            "trg_restart",
        ],
    )

    reader = SQLiteResearchStore(
        db_path
    )

    lineage = reader.get_lineage(
        child
    )

    assert lineage is not None
    assert lineage.root_research_id == parent
    assert lineage.parent_research_id == parent
    assert lineage.version_number == 2

    assert (
        lineage.created_from_trigger_ids
        == ["trg_restart"]
    )


def test_legacy_sqlite_row_reads_as_version_one(
    tmp_path,
):
    db_path = tmp_path / "research.db"

    # First create current schema.
    SQLiteResearchStore(db_path)

    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            INSERT INTO research_runs (
                research_id,
                research_topic
            )
            VALUES (?, ?)
            """,
            (
                "research_legacy",
                "legacy",
            ),
        )

        connection.commit()

    store = SQLiteResearchStore(
        db_path
    )

    lineage = store.get_lineage(
        "research_legacy"
    )

    assert lineage is not None

    assert (
        lineage.root_research_id
        == "research_legacy"
    )
    assert lineage.parent_research_id is None
    assert lineage.version_number == 1

    assert (
        lineage.creation_reason
        == "legacy_research"
    )


def test_get_lineage_unknown_returns_none(
    tmp_path,
):
    store = SQLiteResearchStore(
        tmp_path / "research.db"
    )

    assert (
        store.get_lineage(
            "research_missing"
        )
        is None
    )


def test_inmemory_lineage_matches_sqlite_semantics():
    store = InMemoryResearchStore()

    root = store.save(
        SummaryState(
            research_topic="v1",
        )
    )

    child = store.save(
        SummaryState(
            research_topic="v2",
        ),
        parent_research_id=root,
        creation_reason="reevaluation",
        created_from_trigger_ids=[
            "trg_a",
        ],
    )

    lineage = store.get_lineage(
        child
    )

    assert lineage is not None
    assert lineage.root_research_id == root
    assert lineage.parent_research_id == root
    assert lineage.version_number == 2
    assert (
        lineage.creation_reason
        == "reevaluation"
    )


def test_lineage_is_not_summary_state_business_data(
    tmp_path,
):
    store = SQLiteResearchStore(
        tmp_path / "research.db"
    )

    research_id = store.save(
        SummaryState(
            research_topic="clean state",
        )
    )

    state = store.get(
        research_id
    )

    assert state is not None

    assert not hasattr(
        state,
        "research_lineage",
    )

    assert not hasattr(
        state,
        "parent_research_id",
    )

    assert not hasattr(
        state,
        "version_number",
    )
