import pytest
from pydantic import ValidationError

from config import Configuration


def test_default_parallel_worker_count_is_three():
    config = Configuration()

    assert (
        config.max_concurrent_research_tasks
        == 3
    )


def test_parallel_worker_count_can_be_one():
    config = Configuration(
        max_concurrent_research_tasks=1
    )

    assert (
        config.max_concurrent_research_tasks
        == 1
    )


def test_parallel_worker_count_rejects_zero():
    with pytest.raises(
        ValidationError
    ):
        Configuration(
            max_concurrent_research_tasks=0
        )


def test_parallel_worker_count_rejects_excessive_value():
    with pytest.raises(
        ValidationError
    ):
        Configuration(
            max_concurrent_research_tasks=9
        )


def test_parallel_worker_count_reads_environment(
    monkeypatch,
):
    monkeypatch.setenv(
        "MAX_CONCURRENT_RESEARCH_TASKS",
        "4",
    )

    config = Configuration.from_env()

    assert (
        config.max_concurrent_research_tasks
        == 4
    )
