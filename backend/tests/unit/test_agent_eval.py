from services.agent_eval import (
    EVAL_FAIL,
    EVAL_PASS,
    EVAL_UNKNOWN,
    EvalCase,
    EvalObservation,
    aggregate_eval_suite,
    evaluate_case,
    evaluate_grounding_rate,
    evaluate_recovery_rate,
    evaluate_required_tools,
    evaluate_tool_success,
    evaluate_unsupported_claim_rate,
)


def make_case():
    return EvalCase(
        case_id="case_1",
        name="Research comparison",
        task="Compare A and B",
        expected_tool_names=[
            "web_search",
        ],
        require_evidence=True,
        require_final_answer=True,
    )


def test_complete_good_run_passes():
    case = make_case()

    observation = EvalObservation(
        completed=True,
        final_answer_present=True,
        planned_task_count=2,
        completed_task_count=2,
        failed_task_count=0,
        tool_call_count=2,
        successful_tool_call_count=2,
        failed_tool_call_count=0,
        called_tool_names=[
            "web_search",
        ],
        evidence_count=4,
        claim_count=2,
        grounded_claim_count=2,
        unsupported_claim_count=0,
        recoverable_failure_count=1,
        recovered_failure_count=1,
    )

    result = evaluate_case(
        case,
        observation,
    )

    assert (
        result.overall_status
        == EVAL_PASS
    )

    assert (
        result.failed_metric_count
        == 0
    )

    assert (
        result.unknown_metric_count
        == 0
    )


def test_missing_observations_are_unknown_not_failure():
    case = EvalCase(
        case_id="unknown",
        name="Unknown",
        task="Unknown",
        require_final_answer=False,
    )

    result = evaluate_case(
        case,
        EvalObservation(),
    )

    assert (
        result.overall_status
        == EVAL_UNKNOWN
    )

    assert (
        result.unknown_metric_count
        > 0
    )


def test_zero_tool_calls_do_not_create_zero_success_rate():
    metric = evaluate_tool_success(
        EvalObservation(
            tool_call_count=0,
            successful_tool_call_count=0,
        )
    )

    assert (
        metric.status
        == EVAL_UNKNOWN
    )

    assert metric.value is None


def test_tool_success_rate_fails_on_partial_failure():
    metric = evaluate_tool_success(
        EvalObservation(
            tool_call_count=4,
            successful_tool_call_count=3,
        )
    )

    assert (
        metric.status
        == EVAL_FAIL
    )

    assert (
        metric.value
        == 0.75
    )


def test_required_tool_coverage_passes():
    case = EvalCase(
        case_id="tools",
        name="Tools",
        task="Use tools",
        expected_tool_names=[
            "web_search",
            "calculator",
        ],
    )

    metric = evaluate_required_tools(
        case,
        EvalObservation(
            called_tool_names=[
                "calculator",
                "web_search",
                "unused_tool",
            ]
        ),
    )

    assert (
        metric.status
        == EVAL_PASS
    )

    assert (
        metric.value
        == 1.0
    )


def test_required_tool_coverage_reports_missing_tool():
    case = EvalCase(
        case_id="tools",
        name="Tools",
        task="Use tools",
        expected_tool_names=[
            "web_search",
            "calculator",
        ],
    )

    metric = evaluate_required_tools(
        case,
        EvalObservation(
            called_tool_names=[
                "web_search",
            ]
        ),
    )

    assert (
        metric.status
        == EVAL_FAIL
    )

    assert (
        metric.metadata[
            "missing_tools"
        ]
        == ["calculator"]
    )


def test_grounding_rate_requires_claims():
    metric = evaluate_grounding_rate(
        EvalObservation(
            claim_count=0,
            grounded_claim_count=0,
        )
    )

    assert (
        metric.status
        == EVAL_UNKNOWN
    )


def test_grounding_rate_fails_when_claim_is_ungrounded():
    metric = evaluate_grounding_rate(
        EvalObservation(
            claim_count=4,
            grounded_claim_count=3,
        )
    )

    assert (
        metric.status
        == EVAL_FAIL
    )

    assert (
        metric.value
        == 0.75
    )


def test_unsupported_claim_rate_passes_at_zero():
    metric = (
        evaluate_unsupported_claim_rate(
            EvalObservation(
                claim_count=5,
                unsupported_claim_count=0,
            )
        )
    )

    assert (
        metric.status
        == EVAL_PASS
    )

    assert (
        metric.value
        == 0.0
    )


def test_unsupported_claim_rate_fails_when_present():
    metric = (
        evaluate_unsupported_claim_rate(
            EvalObservation(
                claim_count=5,
                unsupported_claim_count=1,
            )
        )
    )

    assert (
        metric.status
        == EVAL_FAIL
    )

    assert (
        metric.value
        == 0.2
    )


def test_recovery_rate_unknown_when_no_failure_occurs():
    metric = evaluate_recovery_rate(
        EvalObservation(
            recoverable_failure_count=0,
            recovered_failure_count=0,
        )
    )

    assert (
        metric.status
        == EVAL_UNKNOWN
    )


def test_recovery_rate_passes_when_all_recovered():
    metric = evaluate_recovery_rate(
        EvalObservation(
            recoverable_failure_count=2,
            recovered_failure_count=2,
        )
    )

    assert (
        metric.status
        == EVAL_PASS
    )

    assert (
        metric.value
        == 1.0
    )


def test_failed_metric_makes_case_fail():
    result = evaluate_case(
        make_case(),
        EvalObservation(
            completed=False,
            final_answer_present=False,
            planned_task_count=2,
            completed_task_count=1,
            tool_call_count=1,
            successful_tool_call_count=1,
            called_tool_names=[
                "web_search",
            ],
            evidence_count=1,
            claim_count=1,
            grounded_claim_count=1,
            unsupported_claim_count=0,
            recoverable_failure_count=0,
            recovered_failure_count=0,
        ),
    )

    assert (
        result.overall_status
        == EVAL_FAIL
    )


def test_suite_aggregation_counts_case_statuses():
    passing = evaluate_case(
        make_case(),
        EvalObservation(
            completed=True,
            final_answer_present=True,
            planned_task_count=1,
            completed_task_count=1,
            tool_call_count=1,
            successful_tool_call_count=1,
            called_tool_names=[
                "web_search",
            ],
            evidence_count=1,
            claim_count=1,
            grounded_claim_count=1,
            unsupported_claim_count=0,
            recoverable_failure_count=1,
            recovered_failure_count=1,
        ),
    )

    unknown = evaluate_case(
        EvalCase(
            case_id="unknown_case",
            name="Unknown",
            task="Unknown",
            require_final_answer=False,
        ),
        EvalObservation(),
    )

    suite = aggregate_eval_suite(
        [
            passing,
            unknown,
        ]
    )

    assert suite.case_count == 2

    assert (
        suite.passed_case_count
        == 1
    )

    assert (
        suite.unknown_case_count
        == 1
    )


def test_suite_means_ignore_unknown_metric_values():
    first = evaluate_case(
        make_case(),
        EvalObservation(
            completed=True,
            final_answer_present=True,
            planned_task_count=1,
            completed_task_count=1,
            tool_call_count=1,
            successful_tool_call_count=1,
            called_tool_names=[
                "web_search",
            ],
            evidence_count=1,
            claim_count=1,
            grounded_claim_count=1,
            unsupported_claim_count=0,
            recoverable_failure_count=0,
            recovered_failure_count=0,
        ),
    )

    second = evaluate_case(
        EvalCase(
            case_id="second",
            name="Second",
            task="Second",
            require_final_answer=False,
        ),
        EvalObservation(),
    )

    suite = aggregate_eval_suite(
        [
            first,
            second,
        ]
    )

    assert (
        suite.metric_means[
            "tool_success_rate"
        ]
        == 1.0
    )


def test_eval_models_do_not_contain_decision_truth():
    observation = EvalObservation(
        completed=True
    )

    forbidden = {
        "candidate_score",
        "recommendation",
        "decision_readiness",
        "decision_truth",
    }

    assert not (
        forbidden
        & set(vars(observation))
    )


def test_case_metadata_does_not_change_metric_semantics():
    base = EvalCase(
        case_id="metadata",
        name="Metadata",
        task="Test",
        require_final_answer=False,
    )

    enriched = EvalCase(
        case_id="metadata",
        name="Metadata",
        task="Test",
        require_final_answer=False,
        metadata={
            "preferred_answer": "A",
            "score": 999,
        },
    )

    observation = EvalObservation(
        completed=True,
    )

    first = evaluate_case(
        base,
        observation,
    )

    second = evaluate_case(
        enriched,
        observation,
    )

    assert [
        (
            metric.name,
            metric.status,
            metric.value,
        )
        for metric in first.metrics
    ] == [
        (
            metric.name,
            metric.status,
            metric.value,
        )
        for metric in second.metrics
    ]
