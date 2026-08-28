"""Deterministic Agent evaluation primitives.

This module evaluates observed Agent behavior without using an LLM judge.

Important semantics:
- UNKNOWN is distinct from failure;
- missing denominators do not become zero scores;
- metrics describe observed behavior only;
- evaluation never mutates research or decision state;
- deterministic metrics remain separate from optional future judge metrics.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from statistics import mean
from typing import Any


EVAL_PASS = "PASS"
EVAL_FAIL = "FAIL"
EVAL_UNKNOWN = "UNKNOWN"


@dataclass(kw_only=True)
class EvalCase:
    """One reproducible Agent evaluation case."""

    case_id: str
    name: str
    task: str

    tags: list[str] = field(
        default_factory=list
    )

    expected_tool_names: list[str] = field(
        default_factory=list
    )

    require_evidence: bool = False
    require_final_answer: bool = True

    metadata: dict[str, Any] = field(
        default_factory=dict
    )


@dataclass(kw_only=True)
class EvalObservation:
    """Observed behavior from one Agent run.

    This is intentionally a neutral runtime observation model rather than
    a decision or recommendation model.
    """

    completed: bool | None = None

    final_answer_present: bool | None = None

    planned_task_count: int | None = None
    completed_task_count: int | None = None
    failed_task_count: int | None = None

    tool_call_count: int | None = None
    successful_tool_call_count: int | None = None
    failed_tool_call_count: int | None = None
    called_tool_names: list[str] = field(
        default_factory=list
    )

    evidence_count: int | None = None

    claim_count: int | None = None
    grounded_claim_count: int | None = None
    unsupported_claim_count: int | None = None

    recoverable_failure_count: int | None = None
    recovered_failure_count: int | None = None

    adaptive_iteration_count: int | None = None

    latency_ms: float | None = None
    token_usage: int | None = None
    estimated_cost: float | None = None

    metadata: dict[str, Any] = field(
        default_factory=dict
    )


@dataclass(kw_only=True)
class EvalMetric:
    """One deterministic evaluation metric."""

    name: str
    status: str

    value: float | int | bool | None = None

    numerator: int | None = None
    denominator: int | None = None

    reason: str = ""

    metadata: dict[str, Any] = field(
        default_factory=dict
    )


@dataclass(kw_only=True)
class EvalCaseResult:
    """Evaluation result for one case."""

    case_id: str
    metrics: list[EvalMetric]

    passed_metric_count: int
    failed_metric_count: int
    unknown_metric_count: int

    overall_status: str


@dataclass(kw_only=True)
class EvalSuiteResult:
    """Aggregate result across multiple evaluation cases."""

    case_count: int

    passed_case_count: int
    failed_case_count: int
    unknown_case_count: int

    metric_means: dict[str, float]

    case_results: list[EvalCaseResult] = field(
        default_factory=list
    )


def _boolean_metric(
    *,
    name: str,
    value: bool | None,
    success_reason: str,
    failure_reason: str,
    unknown_reason: str,
) -> EvalMetric:
    if value is None:
        return EvalMetric(
            name=name,
            status=EVAL_UNKNOWN,
            value=None,
            reason=unknown_reason,
        )

    if value:
        return EvalMetric(
            name=name,
            status=EVAL_PASS,
            value=True,
            reason=success_reason,
        )

    return EvalMetric(
        name=name,
        status=EVAL_FAIL,
        value=False,
        reason=failure_reason,
    )


def _ratio_metric(
    *,
    name: str,
    numerator: int | None,
    denominator: int | None,
    minimum_pass_ratio: float,
    unknown_reason: str,
) -> EvalMetric:
    if (
        numerator is None
        or denominator is None
    ):
        return EvalMetric(
            name=name,
            status=EVAL_UNKNOWN,
            reason=unknown_reason,
        )

    if denominator <= 0:
        return EvalMetric(
            name=name,
            status=EVAL_UNKNOWN,
            numerator=numerator,
            denominator=denominator,
            reason=(
                "Metric has no valid denominator."
            ),
        )

    bounded_numerator = max(
        0,
        min(
            numerator,
            denominator,
        ),
    )

    ratio = (
        bounded_numerator
        / denominator
    )

    return EvalMetric(
        name=name,
        status=(
            EVAL_PASS
            if ratio >= minimum_pass_ratio
            else EVAL_FAIL
        ),
        value=ratio,
        numerator=bounded_numerator,
        denominator=denominator,
        reason=(
            f"Observed ratio {ratio:.3f}; "
            f"required >= {minimum_pass_ratio:.3f}."
        ),
    )


def evaluate_task_success(
    observation: EvalObservation,
) -> EvalMetric:
    return _boolean_metric(
        name="task_success",
        value=observation.completed,
        success_reason=(
            "Agent run completed successfully."
        ),
        failure_reason=(
            "Agent run did not complete successfully."
        ),
        unknown_reason=(
            "Completion status was not observed."
        ),
    )


def evaluate_final_answer_presence(
    case: EvalCase,
    observation: EvalObservation,
) -> EvalMetric:
    if not case.require_final_answer:
        return EvalMetric(
            name="final_answer_presence",
            status=EVAL_PASS,
            value=True,
            reason=(
                "This evaluation case does not require a final answer."
            ),
        )

    return _boolean_metric(
        name="final_answer_presence",
        value=observation.final_answer_present,
        success_reason=(
            "Required final answer was present."
        ),
        failure_reason=(
            "Required final answer was missing."
        ),
        unknown_reason=(
            "Final-answer presence was not observed."
        ),
    )


def evaluate_planning_completion(
    observation: EvalObservation,
) -> EvalMetric:
    return _ratio_metric(
        name="planning_completion",
        numerator=(
            observation.completed_task_count
        ),
        denominator=(
            observation.planned_task_count
        ),
        minimum_pass_ratio=1.0,
        unknown_reason=(
            "Planned/completed task counts were not fully observed."
        ),
    )


def evaluate_tool_success(
    observation: EvalObservation,
) -> EvalMetric:
    return _ratio_metric(
        name="tool_success_rate",
        numerator=(
            observation.successful_tool_call_count
        ),
        denominator=(
            observation.tool_call_count
        ),
        minimum_pass_ratio=1.0,
        unknown_reason=(
            "Tool-call counts were not fully observed."
        ),
    )


def evaluate_required_tools(
    case: EvalCase,
    observation: EvalObservation,
) -> EvalMetric:
    expected = {
        name
        for name in case.expected_tool_names
        if str(name).strip()
    }

    if not expected:
        return EvalMetric(
            name="required_tool_coverage",
            status=EVAL_PASS,
            value=1.0,
            numerator=0,
            denominator=0,
            reason=(
                "No required tools were declared for this case."
            ),
        )

    called = {
        name
        for name in observation.called_tool_names
        if str(name).strip()
    }

    matched = (
        expected
        & called
    )

    ratio = (
        len(matched)
        / len(expected)
    )

    missing = sorted(
        expected
        - called
    )

    return EvalMetric(
        name="required_tool_coverage",
        status=(
            EVAL_PASS
            if ratio == 1.0
            else EVAL_FAIL
        ),
        value=ratio,
        numerator=len(matched),
        denominator=len(expected),
        reason=(
            "All required tools were observed."
            if not missing
            else (
                "Missing required tools: "
                + ", ".join(missing)
            )
        ),
        metadata={
            "matched_tools": sorted(
                matched
            ),
            "missing_tools": missing,
        },
    )


def evaluate_evidence_presence(
    case: EvalCase,
    observation: EvalObservation,
) -> EvalMetric:
    if not case.require_evidence:
        return EvalMetric(
            name="evidence_presence",
            status=EVAL_PASS,
            value=True,
            reason=(
                "This evaluation case does not require evidence."
            ),
        )

    if observation.evidence_count is None:
        return EvalMetric(
            name="evidence_presence",
            status=EVAL_UNKNOWN,
            reason=(
                "Evidence count was not observed."
            ),
        )

    present = (
        observation.evidence_count
        > 0
    )

    return EvalMetric(
        name="evidence_presence",
        status=(
            EVAL_PASS
            if present
            else EVAL_FAIL
        ),
        value=present,
        reason=(
            "Required evidence was captured."
            if present
            else (
                "Case required evidence but no evidence was captured."
            )
        ),
    )


def evaluate_grounding_rate(
    observation: EvalObservation,
) -> EvalMetric:
    return _ratio_metric(
        name="grounded_claim_rate",
        numerator=(
            observation.grounded_claim_count
        ),
        denominator=(
            observation.claim_count
        ),
        minimum_pass_ratio=1.0,
        unknown_reason=(
            "Claim grounding counts were not fully observed."
        ),
    )


def evaluate_unsupported_claim_rate(
    observation: EvalObservation,
) -> EvalMetric:
    if (
        observation.unsupported_claim_count
        is None
        or observation.claim_count
        is None
    ):
        return EvalMetric(
            name="unsupported_claim_rate",
            status=EVAL_UNKNOWN,
            reason=(
                "Unsupported-claim counts were not fully observed."
            ),
        )

    if observation.claim_count <= 0:
        return EvalMetric(
            name="unsupported_claim_rate",
            status=EVAL_UNKNOWN,
            numerator=(
                observation.unsupported_claim_count
            ),
            denominator=(
                observation.claim_count
            ),
            reason=(
                "No claims were available for unsupported-claim evaluation."
            ),
        )

    unsupported = max(
        0,
        min(
            observation.unsupported_claim_count,
            observation.claim_count,
        ),
    )

    ratio = (
        unsupported
        / observation.claim_count
    )

    return EvalMetric(
        name="unsupported_claim_rate",
        status=(
            EVAL_PASS
            if unsupported == 0
            else EVAL_FAIL
        ),
        value=ratio,
        numerator=unsupported,
        denominator=(
            observation.claim_count
        ),
        reason=(
            "No unsupported claims were observed."
            if unsupported == 0
            else (
                f"{unsupported} unsupported claim(s) "
                "were observed."
            )
        ),
    )


def evaluate_recovery_rate(
    observation: EvalObservation,
) -> EvalMetric:
    if (
        observation.recoverable_failure_count
        is None
        or observation.recovered_failure_count
        is None
    ):
        return EvalMetric(
            name="recovery_rate",
            status=EVAL_UNKNOWN,
            reason=(
                "Recovery counts were not fully observed."
            ),
        )

    if (
        observation.recoverable_failure_count
        == 0
    ):
        return EvalMetric(
            name="recovery_rate",
            status=EVAL_UNKNOWN,
            numerator=0,
            denominator=0,
            reason=(
                "No recoverable failures occurred in this run."
            ),
        )

    return _ratio_metric(
        name="recovery_rate",
        numerator=(
            observation.recovered_failure_count
        ),
        denominator=(
            observation.recoverable_failure_count
        ),
        minimum_pass_ratio=1.0,
        unknown_reason=(
            "Recovery counts were not fully observed."
        ),
    )


def evaluate_case(
    case: EvalCase,
    observation: EvalObservation,
) -> EvalCaseResult:
    """Evaluate one case using deterministic metrics only."""

    metrics = [
        evaluate_task_success(
            observation
        ),
        evaluate_final_answer_presence(
            case,
            observation,
        ),
        evaluate_planning_completion(
            observation
        ),
        evaluate_tool_success(
            observation
        ),
        evaluate_required_tools(
            case,
            observation,
        ),
        evaluate_evidence_presence(
            case,
            observation,
        ),
        evaluate_grounding_rate(
            observation
        ),
        evaluate_unsupported_claim_rate(
            observation
        ),
        evaluate_recovery_rate(
            observation
        ),
    ]

    passed = sum(
        metric.status == EVAL_PASS
        for metric in metrics
    )

    failed = sum(
        metric.status == EVAL_FAIL
        for metric in metrics
    )

    unknown = sum(
        metric.status == EVAL_UNKNOWN
        for metric in metrics
    )

    if failed:
        overall = EVAL_FAIL
    elif unknown:
        overall = EVAL_UNKNOWN
    else:
        overall = EVAL_PASS

    return EvalCaseResult(
        case_id=case.case_id,
        metrics=metrics,
        passed_metric_count=passed,
        failed_metric_count=failed,
        unknown_metric_count=unknown,
        overall_status=overall,
    )


def aggregate_eval_suite(
    results: list[EvalCaseResult],
) -> EvalSuiteResult:
    """Aggregate deterministic case results without inventing missing data."""

    metric_values: dict[
        str,
        list[float],
    ] = {}

    for result in results:
        for metric in result.metrics:
            if isinstance(
                metric.value,
                bool,
            ):
                numeric_value = (
                    1.0
                    if metric.value
                    else 0.0
                )
            elif isinstance(
                metric.value,
                (int, float),
            ):
                numeric_value = float(
                    metric.value
                )
            else:
                continue

            metric_values.setdefault(
                metric.name,
                [],
            ).append(
                numeric_value
            )

    metric_means = {
        name: mean(values)
        for name, values
        in sorted(
            metric_values.items()
        )
        if values
    }

    return EvalSuiteResult(
        case_count=len(results),
        passed_case_count=sum(
            item.overall_status
            == EVAL_PASS
            for item in results
        ),
        failed_case_count=sum(
            item.overall_status
            == EVAL_FAIL
            for item in results
        ),
        unknown_case_count=sum(
            item.overall_status
            == EVAL_UNKNOWN
            for item in results
        ),
        metric_means=metric_means,
        case_results=list(results),
    )
