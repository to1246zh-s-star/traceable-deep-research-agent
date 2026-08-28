import json

import pytest

from services.agent_eval_dataset import (
    EvalDatasetError,
    load_eval_cases,
)


def write_dataset(
    tmp_path,
    payload,
):
    path = (
        tmp_path
        / "cases.json"
    )

    path.write_text(
        json.dumps(
            payload
        ),
        encoding="utf-8",
    )

    return path


def test_load_eval_cases(tmp_path):
    path = write_dataset(
        tmp_path,
        {
            "version": 1,
            "cases": [
                {
                    "case_id": "case_1",
                    "name": "Case",
                    "task": "Research",
                    "tags": [
                        "research"
                    ],
                    "expected_tool_names": [
                        "web_search"
                    ],
                    "require_evidence": True,
                    "require_final_answer": True,
                }
            ],
        },
    )

    cases = load_eval_cases(
        path
    )

    assert len(cases) == 1
    assert (
        cases[0].case_id
        == "case_1"
    )

    assert (
        cases[0].expected_tool_names
        == ["web_search"]
    )


def test_duplicate_case_ids_are_rejected(
    tmp_path,
):
    path = write_dataset(
        tmp_path,
        {
            "cases": [
                {
                    "case_id": "same",
                    "name": "A",
                    "task": "A",
                },
                {
                    "case_id": "same",
                    "name": "B",
                    "task": "B",
                },
            ]
        },
    )

    with pytest.raises(
        EvalDatasetError
    ):
        load_eval_cases(
            path
        )


def test_missing_case_id_is_rejected(
    tmp_path,
):
    path = write_dataset(
        tmp_path,
        {
            "cases": [
                {
                    "name": "A",
                    "task": "A",
                }
            ]
        },
    )

    with pytest.raises(
        EvalDatasetError
    ):
        load_eval_cases(
            path
        )


def test_dataset_requires_cases_list(
    tmp_path,
):
    path = write_dataset(
        tmp_path,
        {
            "cases":
                "not-a-list"
        },
    )

    with pytest.raises(
        EvalDatasetError
    ):
        load_eval_cases(
            path
        )
