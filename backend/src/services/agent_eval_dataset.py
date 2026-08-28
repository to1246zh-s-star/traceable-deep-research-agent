"""Dataset loading and serialization for Agent evaluation."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from services.agent_eval import (
    EvalCase,
    EvalCaseResult,
    EvalMetric,
    EvalSuiteResult,
)


class EvalDatasetError(ValueError):
    """Raised when an evaluation dataset is malformed."""


def load_eval_cases(
    path: str | Path,
) -> list[EvalCase]:
    """Load deterministic eval cases from a JSON dataset."""

    dataset_path = Path(path)

    raw = json.loads(
        dataset_path.read_text(
            encoding="utf-8"
        )
    )

    if not isinstance(
        raw,
        dict,
    ):
        raise EvalDatasetError(
            "Evaluation dataset must be a JSON object."
        )

    raw_cases = raw.get(
        "cases"
    )

    if not isinstance(
        raw_cases,
        list,
    ):
        raise EvalDatasetError(
            "Evaluation dataset must contain a cases list."
        )

    result: list[EvalCase] = []

    seen_ids: set[str] = set()

    for index, item in enumerate(
        raw_cases
    ):
        if not isinstance(
            item,
            dict,
        ):
            raise EvalDatasetError(
                f"Case {index} must be an object."
            )

        case_id = str(
            item.get(
                "case_id",
                "",
            )
        ).strip()

        name = str(
            item.get(
                "name",
                "",
            )
        ).strip()

        task = str(
            item.get(
                "task",
                "",
            )
        ).strip()

        if not case_id:
            raise EvalDatasetError(
                f"Case {index} has no case_id."
            )

        if case_id in seen_ids:
            raise EvalDatasetError(
                f"Duplicate case_id: {case_id}"
            )

        if not name:
            raise EvalDatasetError(
                f"Case {case_id} has no name."
            )

        if not task:
            raise EvalDatasetError(
                f"Case {case_id} has no task."
            )

        seen_ids.add(
            case_id
        )

        expected_tools = item.get(
            "expected_tool_names",
            [],
        )

        tags = item.get(
            "tags",
            [],
        )

        metadata = item.get(
            "metadata",
            {},
        )

        if not isinstance(
            expected_tools,
            list,
        ):
            raise EvalDatasetError(
                f"Case {case_id} expected_tool_names must be a list."
            )

        if not isinstance(
            tags,
            list,
        ):
            raise EvalDatasetError(
                f"Case {case_id} tags must be a list."
            )

        if not isinstance(
            metadata,
            dict,
        ):
            raise EvalDatasetError(
                f"Case {case_id} metadata must be an object."
            )

        result.append(
            EvalCase(
                case_id=case_id,
                name=name,
                task=task,
                tags=[
                    str(value)
                    for value in tags
                ],
                expected_tool_names=[
                    str(value)
                    for value
                    in expected_tools
                ],
                require_evidence=bool(
                    item.get(
                        "require_evidence",
                        False,
                    )
                ),
                require_final_answer=bool(
                    item.get(
                        "require_final_answer",
                        True,
                    )
                ),
                metadata=dict(
                    metadata
                ),
            )
        )

    return result


def _serialize_metric(
    metric: EvalMetric,
) -> dict[str, Any]:
    return asdict(
        metric
    )


def serialize_case_result(
    result: EvalCaseResult,
) -> dict[str, Any]:
    return {
        "case_id":
            result.case_id,
        "overall_status":
            result.overall_status,
        "passed_metric_count":
            result.passed_metric_count,
        "failed_metric_count":
            result.failed_metric_count,
        "unknown_metric_count":
            result.unknown_metric_count,
        "metrics": [
            _serialize_metric(
                metric
            )
            for metric
            in result.metrics
        ],
    }


def serialize_suite_result(
    result: EvalSuiteResult,
) -> dict[str, Any]:
    return {
        "case_count":
            result.case_count,
        "passed_case_count":
            result.passed_case_count,
        "failed_case_count":
            result.failed_case_count,
        "unknown_case_count":
            result.unknown_case_count,
        "metric_means":
            dict(
                result.metric_means
            ),
        "case_results": [
            serialize_case_result(
                item
            )
            for item
            in result.case_results
        ],
    }
