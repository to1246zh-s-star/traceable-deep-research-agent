from __future__ import annotations

from threading import Barrier, Lock
from time import sleep

from agent import DeepResearchAgent
from config import Configuration
from models import (
    Claim,
    Evidence,
    ExecutionTrace,
    SummaryState,
    TodoItem,
)


def make_agent(
    workers=3,
):
    agent = DeepResearchAgent.__new__(
        DeepResearchAgent
    )

    agent.config = Configuration(
        enable_notes=False,
        max_concurrent_research_tasks=workers,
    )

    agent._state_lock = Lock()
    agent._parallel_context_buffer = None
    agent._parallel_loop_counts = None

    return agent


def tasks(count=3):
    return [
        TodoItem(
            id=index,
            title=f"Task {index}",
            intent=f"Intent {index}",
            query=f"Query {index}",
        )
        for index in range(
            1,
            count + 1,
        )
    ]


def test_parallel_execution_overlaps_workers():
    agent = make_agent(
        workers=3
    )

    state = SummaryState(
        research_topic="test",
        todo_items=tasks(3),
    )

    lock = Lock()
    active = 0
    maximum_active = 0

    def execute(
        state,
        task,
        *,
        emit_stream,
        step=None,
    ):
        nonlocal active
        nonlocal maximum_active

        with lock:
            active += 1
            maximum_active = max(
                maximum_active,
                active,
            )

        sleep(0.05)

        task.status = "completed"

        with lock:
            active -= 1

        if False:
            yield {}

    agent._execute_task = execute

    agent._execute_initial_tasks(
        state
    )

    assert maximum_active >= 2

    assert all(
        task.status == "completed"
        for task in state.todo_items
    )


def test_parallel_execution_respects_worker_bound():
    agent = make_agent(
        workers=2
    )

    state = SummaryState(
        research_topic="test",
        todo_items=tasks(4),
    )

    lock = Lock()
    active = 0
    maximum_active = 0

    def execute(
        state,
        task,
        *,
        emit_stream,
        step=None,
    ):
        nonlocal active
        nonlocal maximum_active

        with lock:
            active += 1
            maximum_active = max(
                maximum_active,
                active,
            )

        sleep(0.04)

        task.status = "completed"

        with lock:
            active -= 1

        if False:
            yield {}

    agent._execute_task = execute

    agent._execute_initial_tasks(
        state
    )

    assert maximum_active == 2


def test_worker_failure_is_isolated():
    agent = make_agent(
        workers=3
    )

    state = SummaryState(
        research_topic="test",
        todo_items=tasks(3),
    )

    def execute(
        state,
        task,
        *,
        emit_stream,
        step=None,
    ):
        if task.id == 2:
            task.status = "failed"
            raise RuntimeError(
                "task two failed"
            )

        task.status = "completed"

        if False:
            yield {}

    agent._execute_task = execute

    agent._execute_initial_tasks(
        state
    )

    assert (
        state.todo_items[0].status
        == "completed"
    )

    assert (
        state.todo_items[1].status
        == "failed"
    )

    assert (
        state.todo_items[2].status
        == "completed"
    )


def test_concurrency_one_preserves_serial_execution_order():
    agent = make_agent(
        workers=1
    )

    state = SummaryState(
        research_topic="test",
        todo_items=tasks(3),
    )

    calls = []

    def execute(
        state,
        task,
        *,
        emit_stream,
        step=None,
    ):
        calls.append(task.id)
        task.status = "completed"

        if False:
            yield {}

    agent._execute_task = execute

    agent._execute_initial_tasks(
        state
    )

    assert calls == [
        1,
        2,
        3,
    ]


def test_parallel_loop_counts_are_preallocated_deterministically():
    agent = make_agent(
        workers=3
    )

    state = SummaryState(
        research_topic="test",
        todo_items=tasks(3),
        research_loop_count=5,
    )

    observed = {}
    barrier = Barrier(3)

    def execute(
        state,
        task,
        *,
        emit_stream,
        step=None,
    ):
        barrier.wait()

        observed[task.id] = (
            agent
            ._parallel_loop_counts[
                task.id
            ]
        )

        task.status = "completed"

        if False:
            yield {}

    agent._execute_task = execute

    agent._execute_initial_tasks(
        state
    )

    assert observed == {
        1: 5,
        2: 6,
        3: 7,
    }


def test_deterministic_merge_restores_task_order():
    agent = make_agent(
        workers=3
    )

    state = SummaryState(
        research_topic="test",
        todo_items=tasks(3),
    )

    delays = {
        1: 0.06,
        2: 0.03,
        3: 0.01,
    }

    def execute(
        state,
        task,
        *,
        emit_stream,
        step=None,
    ):
        sleep(
            delays[task.id]
        )

        trace_id = (
            f"trace_{task.id}"
        )

        with agent._state_lock:
            state.execution_traces.append(
                ExecutionTrace(
                    trace_id=trace_id,
                    task_id=task.id,
                    status="completed",
                )
            )

            state.evidence_items.append(
                Evidence(
                    evidence_id=(
                        f"evi_{task.id}"
                    ),
                    task_id=task.id,
                    trace_id=trace_id,
                    query=task.query,
                    backend="test",
                    source_rank=1,
                )
            )

            state.claims.append(
                Claim(
                    claim_id=(
                        f"claim_{task.id}"
                    ),
                    task_id=task.id,
                    trace_id=trace_id,
                    text=f"claim {task.id}",
                )
            )

            agent._parallel_context_buffer[
                task.id
            ] = (
                f"context {task.id}",
                f"sources {task.id}",
            )

        task.status = "completed"

        if False:
            yield {}

    agent._execute_task = execute

    agent._execute_initial_tasks(
        state
    )

    assert [
        item.task_id
        for item in state.execution_traces
    ] == [
        1,
        2,
        3,
    ]

    assert [
        item.task_id
        for item in state.evidence_items
    ] == [
        1,
        2,
        3,
    ]

    assert [
        item.task_id
        for item in state.claims
    ] == [
        1,
        2,
        3,
    ]

    assert state.web_research_results == [
        "context 1",
        "context 2",
        "context 3",
    ]

    assert state.sources_gathered == [
        "sources 1",
        "sources 2",
        "sources 3",
    ]


def test_todo_order_itself_never_changes():
    agent = make_agent(
        workers=3
    )

    original_tasks = tasks(3)

    state = SummaryState(
        research_topic="test",
        todo_items=original_tasks,
    )

    def execute(
        state,
        task,
        *,
        emit_stream,
        step=None,
    ):
        sleep(
            0.01
            * (
                4 - task.id
            )
        )

        task.status = "completed"

        if False:
            yield {}

    agent._execute_task = execute

    agent._execute_initial_tasks(
        state
    )

    assert [
        task.id
        for task in state.todo_items
    ] == [
        1,
        2,
        3,
    ]


def test_parallel_sidecars_are_cleared_after_execution():
    agent = make_agent(
        workers=2
    )

    state = SummaryState(
        research_topic="test",
        todo_items=tasks(2),
    )

    def execute(
        state,
        task,
        *,
        emit_stream,
        step=None,
    ):
        task.status = "completed"

        if False:
            yield {}

    agent._execute_task = execute

    agent._execute_initial_tasks(
        state
    )

    assert (
        agent._parallel_context_buffer
        is None
    )

    assert (
        agent._parallel_loop_counts
        is None
    )
