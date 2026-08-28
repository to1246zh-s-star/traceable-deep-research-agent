import json
import subprocess
import sys
from pathlib import Path

from models import (
    Claim,
    Evidence,
    ExecutionTrace,
    SummaryState,
    TodoItem,
)
from services.research_store import (
    SQLiteResearchStore,
)


def test_eval_cli_runs_against_sqlite(
    tmp_path,
):
    db_path = (
        tmp_path
        / "research.db"
    )

    cases_path = (
        tmp_path
        / "cases.json"
    )

    output_path = (
        tmp_path
        / "result.json"
    )

    cases_path.write_text(
        json.dumps(
            {
                "cases": [
                    {
                        "case_id":
                            "case_1",
                        "name":
                            "Case",
                        "task":
                            "Research",
                        "expected_tool_names":
                            [],
                        "require_evidence":
                            True,
                        "require_final_answer":
                            True,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    store = SQLiteResearchStore(
        db_path
    )

    state = SummaryState(
        research_topic="Eval",
        structured_report="# Report",
    )

    state.todo_items = [
        TodoItem(
            id=1,
            title="Task",
            intent="Research",
            query="query",
            status="completed",
        )
    ]

    state.execution_traces = [
        ExecutionTrace(
            trace_id="trace_1",
            task_id=1,
            status="completed",
        )
    ]

    state.evidence_items = [
        Evidence(
            task_id=1,
            trace_id="trace_1",
            query="query",
            backend="test",
            source_rank=1,
        )
    ]

    state.claims = [
        Claim(
            task_id=1,
            trace_id="trace_1",
            text="Claim",
            evidence_ids=[
                "evidence_1"
            ],
        )
    ]

    research_id = store.save(
        state
    )

    script = (
        Path(__file__)
        .resolve()
        .parents[2]
        / "scripts"
        / "run_agent_eval.py"
    )

    completed = subprocess.run(
        [
            sys.executable,
            str(script),
            "--research-id",
            research_id,
            "--db-path",
            str(db_path),
            "--cases",
            str(cases_path),
            "--output",
            str(output_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert (
        completed.returncode
        == 0
    ), completed.stderr

    payload = json.loads(
        output_path.read_text(
            encoding="utf-8"
        )
    )

    assert (
        payload["research_id"]
        == research_id
    )


def test_eval_cli_returns_three_on_regression(
    tmp_path,
):
    db_path = (
        tmp_path
        / "research.db"
    )

    cases_path = (
        tmp_path
        / "cases.json"
    )

    baseline_path = (
        tmp_path
        / "baseline.json"
    )

    cases_path.write_text(
        json.dumps(
            {
                "cases": [
                    {
                        "case_id": "case_1",
                        "name": "Case",
                        "task": "Research",
                        "expected_tool_names": [],
                        "require_evidence": True,
                        "require_final_answer": True,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    baseline_path.write_text(
        json.dumps(
            {
                "research_id": "baseline",
                "evaluation": {
                    "metric_means": {
                        "task_success": 1.0,
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    store = SQLiteResearchStore(
        db_path
    )

    state = SummaryState(
        research_topic="Eval",
        structured_report="# Report",
    )

    state.todo_items = [
        TodoItem(
            id=1,
            title="Task",
            intent="Research",
            query="query",
            status="failed",
        )
    ]

    research_id = store.save(
        state
    )

    script = (
        Path(__file__)
        .resolve()
        .parents[2]
        / "scripts"
        / "run_agent_eval.py"
    )

    completed = subprocess.run(
        [
            sys.executable,
            str(script),
            "--research-id",
            research_id,
            "--db-path",
            str(db_path),
            "--cases",
            str(cases_path),
            "--baseline",
            str(baseline_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert (
        completed.returncode
        == 3
    )

    payload = json.loads(
        completed.stdout
    )

    assert (
        payload["regression"]["status"]
        == "REGRESSION"
    )


def test_eval_cli_unknown_metric_is_not_regression(
    tmp_path,
):
    db_path = (
        tmp_path
        / "research.db"
    )

    cases_path = (
        tmp_path
        / "cases.json"
    )

    baseline_path = (
        tmp_path
        / "baseline.json"
    )

    cases_path.write_text(
        json.dumps(
            {
                "cases": [
                    {
                        "case_id": "case_1",
                        "name": "Case",
                        "task": "Research",
                        "expected_tool_names": [],
                        "require_evidence": False,
                        "require_final_answer": False,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    baseline_path.write_text(
        json.dumps(
            {
                "research_id": "baseline",
                "evaluation": {
                    "metric_means": {
                        "custom_metric": 1.0,
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    store = SQLiteResearchStore(
        db_path
    )

    state = SummaryState(
        research_topic="Eval",
    )

    state.todo_items = [
        TodoItem(
            id=1,
            title="Task",
            intent="Research",
            query="query",
            status="completed",
        )
    ]

    research_id = store.save(
        state
    )

    script = (
        Path(__file__)
        .resolve()
        .parents[2]
        / "scripts"
        / "run_agent_eval.py"
    )

    completed = subprocess.run(
        [
            sys.executable,
            str(script),
            "--research-id",
            research_id,
            "--db-path",
            str(db_path),
            "--cases",
            str(cases_path),
            "--baseline",
            str(baseline_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert (
        completed.returncode
        == 0
    )
