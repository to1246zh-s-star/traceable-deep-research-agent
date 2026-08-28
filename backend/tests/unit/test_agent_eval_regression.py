import pytest

from services.agent_eval_regression import (
    HIGHER_IS_BETTER,
    LOWER_IS_BETTER,
    IMPROVEMENT,
    REGRESSION,
    STABLE,
    UNKNOWN,
    EvalRegressionPolicy,
    compare_eval_payloads,
    compare_metric,
    compare_metric_means,
)


def test_higher_is_better_detects_regression():
    result = compare_metric(
        metric_name="grounded_claim_rate",
        baseline_value=0.95,
        current_value=0.80,
        policy=EvalRegressionPolicy(
            metric_name="grounded_claim_rate",
            direction=HIGHER_IS_BETTER,
        ),
    )

    assert (
        result.status
        == REGRESSION
    )

    assert (
        result.delta
        == pytest.approx(-0.15)
    )


def test_higher_is_better_detects_improvement():
    result = compare_metric(
        metric_name="tool_success_rate",
        baseline_value=0.8,
        current_value=1.0,
        policy=EvalRegressionPolicy(
            metric_name="tool_success_rate",
            direction=HIGHER_IS_BETTER,
        ),
    )

    assert (
        result.status
        == IMPROVEMENT
    )


def test_lower_is_better_detects_regression():
    result = compare_metric(
        metric_name="unsupported_claim_rate",
        baseline_value=0.05,
        current_value=0.20,
        policy=EvalRegressionPolicy(
            metric_name="unsupported_claim_rate",
            direction=LOWER_IS_BETTER,
        ),
    )

    assert (
        result.status
        == REGRESSION
    )


def test_lower_is_better_detects_improvement():
    result = compare_metric(
        metric_name="latency_ms",
        baseline_value=1000,
        current_value=800,
        policy=EvalRegressionPolicy(
            metric_name="latency_ms",
            direction=LOWER_IS_BETTER,
        ),
    )

    assert (
        result.status
        == IMPROVEMENT
    )


def test_tolerance_prevents_noise_regression():
    result = compare_metric(
        metric_name="grounded_claim_rate",
        baseline_value=0.95,
        current_value=0.94,
        policy=EvalRegressionPolicy(
            metric_name="grounded_claim_rate",
            direction=HIGHER_IS_BETTER,
            tolerance=0.02,
        ),
    )

    assert (
        result.status
        == STABLE
    )


def test_missing_current_metric_is_unknown():
    result = compare_metric(
        metric_name="tool_success_rate",
        baseline_value=1.0,
        current_value=None,
        policy=EvalRegressionPolicy(
            metric_name="tool_success_rate",
            direction=HIGHER_IS_BETTER,
        ),
    )

    assert (
        result.status
        == UNKNOWN
    )


def test_missing_baseline_metric_is_unknown():
    result = compare_metric(
        metric_name="tool_success_rate",
        baseline_value=None,
        current_value=1.0,
        policy=EvalRegressionPolicy(
            metric_name="tool_success_rate",
            direction=HIGHER_IS_BETTER,
        ),
    )

    assert (
        result.status
        == UNKNOWN
    )


def test_unknown_metric_policy_is_not_regression():
    result = compare_metric_means(
        baseline_metrics={
            "custom_metric": 1.0,
        },
        current_metrics={
            "custom_metric": 0.0,
        },
    )

    assert (
        result.regression_count
        == 0
    )

    assert (
        result.unknown_count
        == 1
    )

    assert (
        result.status
        == UNKNOWN
    )


def test_any_metric_regression_marks_result_regression():
    result = compare_metric_means(
        baseline_metrics={
            "tool_success_rate": 1.0,
            "grounded_claim_rate": 1.0,
        },
        current_metrics={
            "tool_success_rate": 1.0,
            "grounded_claim_rate": 0.5,
        },
    )

    assert (
        result.status
        == REGRESSION
    )

    assert (
        result.regression_count
        == 1
    )


def test_improvements_without_regression_are_non_regression():
    result = compare_metric_means(
        baseline_metrics={
            "tool_success_rate": 0.8,
        },
        current_metrics={
            "tool_success_rate": 1.0,
        },
    )

    assert (
        result.status
        == STABLE
    )

    assert (
        result.improvement_count
        == 1
    )


def test_unsupported_claim_rate_uses_lower_is_better_policy():
    result = compare_metric_means(
        baseline_metrics={
            "unsupported_claim_rate": 0.1,
        },
        current_metrics={
            "unsupported_claim_rate": 0.0,
        },
    )

    assert (
        result.regression_count
        == 0
    )

    assert (
        result.improvement_count
        == 1
    )


def test_serialized_payloads_can_be_compared():
    baseline = {
        "research_id": "old",
        "evaluation": {
            "metric_means": {
                "tool_success_rate": 1.0,
                "unsupported_claim_rate": 0.0,
            }
        },
    }

    current = {
        "research_id": "new",
        "evaluation": {
            "metric_means": {
                "tool_success_rate": 0.5,
                "unsupported_claim_rate": 0.0,
            }
        },
    }

    result = compare_eval_payloads(
        baseline_payload=baseline,
        current_payload=current,
    )

    assert (
        result.status
        == REGRESSION
    )
