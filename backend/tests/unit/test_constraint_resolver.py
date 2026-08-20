from models import (
    Candidate,
    Constraint,
    DecisionCase,
    Evidence,
    SummaryState,
)
from services.constraint_resolver import ConstraintResolver
from services.decision_evaluator import evaluate_decision_case


class DummyConfig:
    strip_thinking_tokens = False


class StubAgent:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0
        self.prompts = []

    def run(self, prompt):
        self.prompts.append(prompt)
        response = self.responses[self.calls]
        self.calls += 1
        return response

    def clear_history(self):
        pass


def make_decision():
    return DecisionCase(
        decision_id="dec_constraints",
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
        constraints=[
            Constraint(
                constraint_id="con_self_host",
                text="Must support self-hosting",
            )
        ],
    )


def make_state():
    return SummaryState(
        research_topic="Qdrant vs Milvus",
        evidence_items=[
            Evidence(
                evidence_id="evi_qdrant",
                task_id=1,
                trace_id="trace_1",
                query="Qdrant self hosting",
                backend="web",
                source_title="Qdrant Documentation",
                snippet=(
                    "Qdrant supports self-hosted deployment."
                ),
            ),
            Evidence(
                evidence_id="evi_milvus",
                task_id=2,
                trace_id="trace_2",
                query="Milvus self hosting",
                backend="web",
                source_title="Milvus Documentation",
                snippet=(
                    "Milvus deployment documentation."
                ),
            ),
        ],
    )


def test_satisfied_constraint_maps_to_true():
    resolver = ConstraintResolver(
        StubAgent([
            """
            {
              "status": "satisfied",
              "strength": 0.9,
              "rationale": "Self-hosting is explicitly supported."
            }
            """,
            """
            {
              "status": "unknown",
              "strength": 0.2,
              "rationale": "Evidence is not explicit."
            }
            """,
        ]),
        DummyConfig(),
    )

    results = resolver.resolve(
        make_state(),
        make_decision(),
    )

    assert results == {
        "cand_qdrant": {
            "con_self_host": True,
        }
    }


def test_violated_constraint_maps_to_false():
    resolver = ConstraintResolver(
        StubAgent([
            """
            {
              "status": "violated",
              "strength": 0.9,
              "rationale": "Candidate does not support self-hosting."
            }
            """,
            """
            {
              "status": "unknown",
              "strength": 0.1,
              "rationale": "Insufficient evidence."
            }
            """,
        ]),
        DummyConfig(),
    )

    results = resolver.resolve(
        make_state(),
        make_decision(),
    )

    assert results == {
        "cand_qdrant": {
            "con_self_host": False,
        }
    }


def test_unknown_constraint_is_omitted():
    resolver = ConstraintResolver(
        StubAgent([
            """
            {
              "status": "unknown",
              "strength": 0.2,
              "rationale": "Evidence is insufficient."
            }
            """,
            """
            {
              "status": "unknown",
              "strength": 0.2,
              "rationale": "Evidence is insufficient."
            }
            """,
        ]),
        DummyConfig(),
    )

    results = resolver.resolve(
        make_state(),
        make_decision(),
    )

    assert results == {}


def test_unknown_remains_unresolved_in_evaluator():
    decision = make_decision()

    resolver = ConstraintResolver(
        StubAgent([
            """
            {
              "status": "unknown",
              "strength": 0.2,
              "rationale": "Evidence is insufficient."
            }
            """,
            """
            {
              "status": "unknown",
              "strength": 0.2,
              "rationale": "Evidence is insufficient."
            }
            """,
        ]),
        DummyConfig(),
    )

    results = resolver.resolve(
        make_state(),
        decision,
    )

    evaluation = evaluate_decision_case(
        decision,
        constraint_results=results,
    )

    assert evaluation.status == "incomplete"

    assert set(
        evaluation.unresolved_candidate_ids
    ) == {
        "cand_qdrant",
        "cand_milvus",
    }

    assert evaluation.disqualified_candidate_ids == []


def test_invalid_json_retries_once():
    agent = StubAgent([
        '{"status":',
        """
        {
          "status": "satisfied",
          "strength": 0.8,
          "rationale": "Recovered."
        }
        """,
        """
        {
          "status": "unknown",
          "strength": 0.1,
          "rationale": "Unknown."
        }
        """,
    ])

    resolver = ConstraintResolver(
        agent,
        DummyConfig(),
    )

    results = resolver.resolve(
        make_state(),
        make_decision(),
    )

    assert results["cand_qdrant"][
        "con_self_host"
    ] is True

    assert agent.calls == 3


def test_missing_candidate_evidence_skips_llm_call():
    state = SummaryState(
        research_topic="Qdrant vs Milvus",
        evidence_items=[],
    )

    agent = StubAgent([])

    resolver = ConstraintResolver(
        agent,
        DummyConfig(),
    )

    results = resolver.resolve(
        state,
        make_decision(),
    )

    assert results == {}
    assert agent.calls == 0
