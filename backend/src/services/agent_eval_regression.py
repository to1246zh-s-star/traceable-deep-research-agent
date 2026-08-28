"""Deterministic regression comparison for Agent evaluation results."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


REGRESSION = "REGRESSION"
IMPROVEMENT = "IMPROVEMENT"
STABLE = "STABLE"
UNKNOWN = "UNKNOWN"

HIGHER_IS_BETTER = "higher"
LOWER_IS_BETTER = "lower"


@dataclass(kw_only=True)
class EvalRegressionPolicy:
    metric_name: str
    direction: str
    tolerance: float = 0.0


@dataclass(kw_only=True)
class EvalMetricComparison:
    metric_name: str
    status: str

    baseline_value: float | None = None
    current_value: float | None = None
    delta: float | None = None

    direction: str | None = None
    tolerance: float = 0.0

    reason: str = ""


@dataclass(kw_only=True)
class EvalRegressionResult:
    status: str

    compared_metric_count: int
    regression_count: int
    improvement_count: int
    stable_count: int
    unknown_count: int

    comparisons: list[
        EvalMetricComparison
    ] = field(default_factory=list)


DEFAULT_REGRESSION_POLICIES = {
    policy.metric_name: policy
    for policy in [
        EvalRegressionPolicy(
            metric_name="task_success",
            direction=HIGHER_IS_BETTER,
        ),
        EvalRegressionPolicy(
            metric_name="final_answer_presence",
            direction=HIGHER_IS_BETTER,
        ),
        EvalRegressionPolicy(
            metric_name="planning_completion",
            direction=HIGHER_IS_BETTER,
        ),
        EvalRegressionPolicy(
            metric_name="tool_success_rate",
            direction=HIGHER_IS_BETTER,
        ),
        EvalRegressionPolicy(
            metric_name="required_tool_coverage",
            direction=HIGHER_IS_BETTER,
        ),
        EvalRegressionPolicy(
            metric_name="evidence_presence",
            direction=HIGHER_IS_BETTER,
        ),
        EvalRegressionPolicy(
            metric_name="grounded_claim_rate",
            direction=HIGHER_IS_BETTER,
        ),
        EvalRegressionPolicy(
            metric_name="unsupported_claim_rate",
            direction=LOWER_IS_BETTER,
        ),
        EvalRegressionPolicy(
            metric_name="recovery_rate",
            direction=HIGHER_IS_BETTER,
        ),

        # Future explicit runtime accounting.
        EvalRegressionPolicy(
            metric_name="latency_ms",
            direction=LOWER_IS_BETTER,
        ),
        EvalRegressionPolicy(
            metric_name="token_usage",
            direction=LOWER_IS_BETTER,
        ),
        EvalRegressionPolicy(
            metric_name="estimated_cost",
            direction=LOWER_IS_BETTER,
        ),
    ]
}


def _numeric(
    value: Any,
) -> float | None:
    if isinstance(
        value,
        bool,
    ):
        return (
            1.0
            if value
            else 0.0
        )

    if isinstance(
        value,
        (int, float),
    ):
        return float(
            value
        )

    return None


def compare_metric(
    *,
    metric_name: str,
    baseline_value: Any,
    current_value: Any,
    policy: EvalRegressionPolicy,
) -> EvalMetricComparison:
    baseline = _numeric(
        baseline_value
    )
    current = _numeric(
        current_value
    )

    if baseline is None:
        return EvalMetricComparison(
            metric_name=metric_name,
            status=UNKNOWN,
            current_value=current,
            direction=policy.direction,
            tolerance=policy.tolerance,
            reason=(
                "Baseline metric is unavailable."
            ),
        )

    if current is None:
        return EvalMetricComparison(
            metric_name=metric_name,
            status=UNKNOWN,
            baseline_value=baseline,
            direction=policy.direction,
            tolerance=policy.tolerance,
            reason=(
                "Current metric is unavailable."
            ),
        )

    delta = (
        current
        - baseline
    )

    tolerance = max(
        0.0,
        float(
            policy.tolerance
        ),
    )

    if (
        policy.direction
        == HIGHER_IS_BETTER
    ):
        if delta < -tolerance:
            status = REGRESSION
        elif delta > tolerance:
            status = IMPROVEMENT
        else:
            status = STABLE

    elif (
        policy.direction
        == LOWER_IS_BETTER
    ):
        if delta > tolerance:
            status = REGRESSION
        elif delta < -tolerance:
            status = IMPROVEMENT
        else:
            status = STABLE

    else:
        raise ValueError(
            "Unsupported regression direction: "
            f"{policy.direction}"
        )

    return EvalMetricComparison(
        metric_name=metric_name,
        status=status,
        baseline_value=baseline,
        current_value=current,
        delta=delta,
        direction=policy.direction,
        tolerance=tolerance,
        reason=(
            f"Baseline={baseline:.6f}, "
            f"current={current:.6f}, "
            f"delta={delta:+.6f}."
        ),
    )


def compare_metric_means(
    *,
    baseline_metrics: dict[str, Any],
    current_metrics: dict[str, Any],
    policies: dict[
        str,
        EvalRegressionPolicy,
    ] | None = None,
) -> EvalRegressionResult:
    """Compare deterministic suite-level metric means."""

    active_policies = (
        policies
        or DEFAULT_REGRESSION_POLICIES
    )

    metric_names = sorted(
        set(
            baseline_metrics
        )
        | set(
            current_metrics
        )
    )

    comparisons: list[
        EvalMetricComparison
    ] = []

    for metric_name in metric_names:
        policy = active_policies.get(
            metric_name
        )

        if policy is None:
            comparisons.append(
                EvalMetricComparison(
                    metric_name=metric_name,
                    status=UNKNOWN,
                    baseline_value=_numeric(
                        baseline_metrics.get(
                            metric_name
                        )
                    ),
                    current_value=_numeric(
                        current_metrics.get(
                            metric_name
                        )
                    ),
                    reason=(
                        "No regression policy is defined "
                        "for this metric."
                    ),
                )
            )
            continue

        comparisons.append(
            compare_metric(
                metric_name=metric_name,
                baseline_value=(
                    baseline_metrics.get(
                        metric_name
                    )
                ),
                current_value=(
                    current_metrics.get(
                        metric_name
                    )
                ),
                policy=policy,
            )
        )

    regression_count = sum(
        item.status == REGRESSION
        for item in comparisons
    )

    improvement_count = sum(
        item.status == IMPROVEMENT
        for item in comparisons
    )

    stable_count = sum(
        item.status == STABLE
        for item in comparisons
    )

    unknown_count = sum(
        item.status == UNKNOWN
        for item in comparisons
    )

    compared_metric_count = (
        regression_count
        + improvement_count
        + stable_count
    )

    if regression_count:
        overall = REGRESSION
    elif compared_metric_count:
        overall = STABLE
    else:
        overall = UNKNOWN

    return EvalRegressionResult(
        status=overall,
        compared_metric_count=(
            compared_metric_count
        ),
        regression_count=(
            regression_count
        ),
        improvement_count=(
            improvement_count
        ),
        stable_count=stable_count,
        unknown_count=unknown_count,
        comparisons=comparisons,
    )


def serialize_regression_result(
    result: EvalRegressionResult,
) -> dict[str, Any]:
    return {
        "status":
            result.status,
        "compared_metric_count":
            result.compared_metric_count,
        "regression_count":
            result.regression_count,
        "improvement_count":
            result.improvement_count,
        "stable_count":
            result.stable_count,
        "unknown_count":
            result.unknown_count,
        "comparisons": [
            {
                "metric_name":
                    item.metric_name,
                "status":
                    item.status,
                "baseline_value":
                    item.baseline_value,
                "current_value":
                    item.current_value,
                "delta":
                    item.delta,
                "direction":
                    item.direction,
                "tolerance":
                    item.tolerance,
                "reason":
                    item.reason,
            }
            for item
            in result.comparisons
        ],
    }


def compare_eval_payloads(
    *,
    baseline_payload: dict[str, Any],
    current_payload: dict[str, Any],
) -> EvalRegressionResult:
    """Compare two serialized research-eval payloads."""

    baseline_eval = baseline_payload.get(
        "evaluation"
    )

    current_eval = current_payload.get(
        "evaluation"
    )

    if not isinstance(
        baseline_eval,
        dict,
    ):
        raise ValueError(
            "Baseline payload has no evaluation object."
        )

    if not isinstance(
        current_eval,
        dict,
    ):
        raise ValueError(
            "Current payload has no evaluation object."
        )

    baseline_metrics = (
        baseline_eval.get(
            "metric_means"
        )
    )

    current_metrics = (
        current_eval.get(
            "metric_means"
        )
    )

    if not isinstance(
        baseline_metrics,
        dict,
    ):
        raise ValueError(
            "Baseline evaluation has no metric_means object."
        )

    if not isinstance(
        current_metrics,
        dict,
    ):
        raise ValueError(
            "Current evaluation has no metric_means object."
        )

    return compare_metric_means(
        baseline_metrics=(
            baseline_metrics
        ),
        current_metrics=(
            current_metrics
        ),
    )
