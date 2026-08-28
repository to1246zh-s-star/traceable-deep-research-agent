"""Run deterministic Agent evaluation over persisted research state."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from models import SummaryState
from services.agent_eval import (
    EvalCase,
    EvalCaseResult,
    EvalSuiteResult,
    aggregate_eval_suite,
    evaluate_case,
)
from services.agent_eval_observation import (
    build_eval_observation,
)


@dataclass(kw_only=True)
class ResearchEvalResult:
    research_id: str
    suite: EvalSuiteResult


def evaluate_research_state(
    *,
    research_id: str,
    state: SummaryState,
    cases: list[EvalCase],
) -> ResearchEvalResult:
    """Evaluate one persisted research state against deterministic cases."""

    observation = (
        build_eval_observation(
            state
        )
    )

    case_results: list[
        EvalCaseResult
    ] = []

    for case in cases:
        case_results.append(
            evaluate_case(
                case,
                observation,
            )
        )

    return ResearchEvalResult(
        research_id=research_id,
        suite=(
            aggregate_eval_suite(
                case_results
            )
        ),
    )


def serialize_research_eval(
    result: ResearchEvalResult,
) -> dict[str, Any]:
    from services.agent_eval_dataset import (
        serialize_suite_result,
    )

    return {
        "research_id":
            result.research_id,
        "evaluation":
            serialize_suite_result(
                result.suite
            ),
    }
