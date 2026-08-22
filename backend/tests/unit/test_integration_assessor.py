import json

from models import (
    Candidate,
    DecisionCase,
    Evidence,
    SummaryState,
    TechnicalContext,
)
from services.integration_assessor import (
    IntegrationAssessor,
)


class StubAgent:
    def __init__(self, responses):
        self.responses = list(responses)
        self.prompts = []
        self.clear_count = 0

    def run(self, prompt):
        self.prompts.append(prompt)
        return self.responses.pop(0)

    def clear_history(self):
        self.clear_count += 1


class StubConfig:
    strip_thinking_tokens = False


def make_decision():
    return DecisionCase(
        decision_id="dec_arch",
        question="Choose Qdrant or Milvus",
        candidates=[
            Candidate(
                candidate_id="cand_qdrant",
                name="Qdrant",
            ),
            Candidate(
                candidate_id="cand_milvus",
                name="Milvus",
            ),
        ],
    )


def make_context():
    return TechnicalContext(
        existing_stack=[
            "Python",
            "FastAPI",
        ],
        deployment_environment=[
            "Docker-only",
        ],
        team_capabilities=[
            "Limited DevOps capacity",
        ],
    )


def make_state():
    return SummaryState(
        evidence_items=[
            Evidence(
                evidence_id="evi_qdrant",
                task_id=1,
                trace_id="trace_q",
                query="Qdrant deployment",
                backend="web",
                source_title="Qdrant docs",
                snippet=(
                    "Qdrant provides Docker "
                    "deployment."
                ),
                source_rank=1,
            ),
            Evidence(
                evidence_id="evi_milvus",
                task_id=2,
                trace_id="trace_m",
                query="Milvus deployment",
                backend="web",
                source_title="Milvus docs",
                snippet=(
                    "Milvus deployment uses "
                    "multiple infrastructure "
                    "components."
                ),
                source_rank=1,
            ),
        ]
    )


def payload():
    return {
        "results": [
            {
                "candidate_id":
                    "cand_qdrant",
                "integration_complexity":
                    "LOW",
                "migration_complexity":
                    "LOW",
                "operational_change":
                    "LOW",
                "infrastructure_change":
                    "LOW",
                "required_new_dependencies":
                    [],
                "affected_components":
                    ["API service"],
                "team_skill_gaps":
                    [],
                "evidence_ids":
                    ["evi_qdrant"],
                "rationale":
                    "Fits Docker deployment.",
            },
            {
                "candidate_id":
                    "cand_milvus",
                "integration_complexity":
                    "HIGH",
                "migration_complexity":
                    "MEDIUM",
                "operational_change":
                    "HIGH",
                "infrastructure_change":
                    "HIGH",
                "required_new_dependencies":
                    ["additional services"],
                "affected_components":
                    ["deployment"],
                "team_skill_gaps":
                    ["operations"],
                "evidence_ids":
                    ["evi_milvus"],
                "rationale":
                    "More operational change.",
            },
        ]
    }


def make_assessor(*responses):
    agent = StubAgent(responses)

    assessor = IntegrationAssessor(
        agent,
        StubConfig(),
    )

    return assessor, agent


def test_assesses_all_candidates_in_one_call():
    assessor, agent = make_assessor(
        json.dumps(payload())
    )

    results = assessor.assess(
        make_state(),
        make_decision(),
        make_context(),
    )

    assert len(results) == 2
    assert assessor.llm_call_count == 1
    assert agent.clear_count == 1

    assert (
        results[0].candidate_id
        == "cand_qdrant"
    )
    assert (
        results[0].integration_complexity
        == "LOW"
    )

    assert (
        results[1].candidate_id
        == "cand_milvus"
    )
    assert (
        results[1].operational_change
        == "HIGH"
    )

    assert all(
        result.decision_id == "dec_arch"
        for result in results
    )


def test_no_context_returns_unknown_without_llm():
    assessor, _ = make_assessor()

    results = assessor.assess(
        make_state(),
        make_decision(),
        None,
    )

    assert len(results) == 2
    assert all(
        result.integration_complexity
        == "UNKNOWN"
        for result in results
    )
    assert assessor.llm_call_count == 0


def test_empty_context_returns_unknown_without_llm():
    assessor, _ = make_assessor()

    results = assessor.assess(
        make_state(),
        make_decision(),
        TechnicalContext(),
    )

    assert all(
        result.operational_change
        == "UNKNOWN"
        for result in results
    )

    assert assessor.llm_call_count == 0


def test_missing_candidate_evidence_is_unknown():
    state = make_state()

    state.evidence_items = [
        state.evidence_items[0]
    ]

    partial = {
        "results": [
            payload()["results"][0]
        ]
    }

    assessor, _ = make_assessor(
        json.dumps(partial)
    )

    results = assessor.assess(
        state,
        make_decision(),
        make_context(),
    )

    assert (
        results[0].integration_complexity
        == "LOW"
    )

    assert (
        results[1].integration_complexity
        == "UNKNOWN"
    )

    assert assessor.llm_call_count == 1


def test_invalid_level_normalizes_to_unknown():
    data = payload()

    data["results"][0][
        "integration_complexity"
    ] = "EASY"

    assessor, _ = make_assessor(
        json.dumps(data)
    )

    results = assessor.assess(
        make_state(),
        make_decision(),
        make_context(),
    )

    assert (
        results[0].integration_complexity
        == "UNKNOWN"
    )

    assert assessor.llm_call_count == 1


def test_hallucinated_evidence_id_is_removed():
    data = payload()

    data["results"][0][
        "evidence_ids"
    ] = [
        "evi_qdrant",
        "invented_id",
    ]

    assessor, _ = make_assessor(
        json.dumps(data)
    )

    results = assessor.assess(
        make_state(),
        make_decision(),
        make_context(),
    )

    assert results[0].evidence_ids == [
        "evi_qdrant"
    ]


def test_successful_assessments_are_cached():
    assessor, _ = make_assessor(
        json.dumps(payload())
    )

    state = make_state()
    decision = make_decision()
    context = make_context()

    first = assessor.assess(
        state,
        decision,
        context,
    )

    second = assessor.assess(
        state,
        decision,
        context,
    )

    assert assessor.llm_call_count == 1
    assert second == first


def test_context_change_invalidates_cache():
    assessor, _ = make_assessor(
        json.dumps(payload()),
        json.dumps(payload()),
    )

    state = make_state()
    decision = make_decision()

    assessor.assess(
        state,
        decision,
        make_context(),
    )

    changed = make_context()
    changed.infrastructure = [
        "Kubernetes"
    ]

    assessor.assess(
        state,
        decision,
        changed,
    )

    assert assessor.llm_call_count == 2


def test_evidence_change_invalidates_only_candidate():
    assessor, _ = make_assessor(
        json.dumps(payload()),
        json.dumps({
            "results": [
                payload()["results"][0]
            ]
        }),
    )

    state = make_state()
    decision = make_decision()
    context = make_context()

    assessor.assess(
        state,
        decision,
        context,
    )

    state.evidence_items[0].snippet = (
        "Qdrant changed deployment evidence."
    )

    assessor.assess(
        state,
        decision,
        context,
    )

    assert assessor.llm_call_count == 2


def test_failed_response_is_not_cached():
    assessor, _ = make_assessor(
        "bad json",
        "still bad",
        json.dumps(payload()),
    )

    state = make_state()
    decision = make_decision()
    context = make_context()

    first = assessor.assess(
        state,
        decision,
        context,
    )

    assert all(
        result.integration_complexity
        == "UNKNOWN"
        for result in first
    )

    assert assessor.llm_call_count == 2

    second = assessor.assess(
        state,
        decision,
        context,
    )

    assert (
        second[0].integration_complexity
        == "LOW"
    )

    assert assessor.llm_call_count == 3


def test_missing_result_retries():
    incomplete = {
        "results": [
            payload()["results"][0]
        ]
    }

    assessor, _ = make_assessor(
        json.dumps(incomplete),
        json.dumps(payload()),
    )

    results = assessor.assess(
        make_state(),
        make_decision(),
        make_context(),
    )

    assert len(results) == 2
    assert assessor.retry_count == 1
    assert assessor.llm_call_count == 2
