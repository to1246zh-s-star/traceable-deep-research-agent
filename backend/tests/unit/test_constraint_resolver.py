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
            ),
            Constraint(
                constraint_id="con_linux",
                text="Must support Linux deployment",
            ),
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
                query="Qdrant deployment",
                backend="web",
                source_title="Qdrant Documentation",
                snippet=(
                    "Qdrant supports self-hosted Linux deployment."
                ),
            ),
            Evidence(
                evidence_id="evi_milvus",
                task_id=2,
                trace_id="trace_2",
                query="Milvus deployment",
                backend="web",
                source_title="Milvus Documentation",
                snippet=(
                    "Milvus provides deployment documentation."
                ),
            ),
        ],
    )


def test_batch_resolves_all_constraints_for_candidate():
    agent = StubAgent([
        """
        {
          "results": [
            {
              "constraint_id": "con_self_host",
              "status": "satisfied",
              "strength": 0.95,
              "rationale": "Explicit self-hosting support."
            },
            {
              "constraint_id": "con_linux",
              "status": "satisfied",
              "strength": 0.9,
              "rationale": "Linux deployment is explicit."
            }
          ]
        }
        """,
        """
        {
          "results": [
            {
              "constraint_id": "con_self_host",
              "status": "unknown",
              "strength": 0.2,
              "rationale": "Not explicit."
            },
            {
              "constraint_id": "con_linux",
              "status": "unknown",
              "strength": 0.2,
              "rationale": "Not explicit."
            }
          ]
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

    assert results == {
        "cand_qdrant": {
            "con_self_host": True,
            "con_linux": True,
        }
    }

    # Two candidates with evidence -> only two LLM calls,
    # despite two constraints per candidate.
    assert agent.calls == 2


def test_batch_maps_violated_to_false_and_unknown_to_omission():
    resolver = ConstraintResolver(
        StubAgent([
            """
            {
              "results": [
                {
                  "constraint_id": "con_self_host",
                  "status": "violated",
                  "strength": 0.9,
                  "rationale": "Not supported."
                },
                {
                  "constraint_id": "con_linux",
                  "status": "unknown",
                  "strength": 0.2,
                  "rationale": "Insufficient evidence."
                }
              ]
            }
            """,
            """
            {
              "results": [
                {
                  "constraint_id": "con_self_host",
                  "status": "unknown",
                  "strength": 0.1,
                  "rationale": "Unknown."
                },
                {
                  "constraint_id": "con_linux",
                  "status": "unknown",
                  "strength": 0.1,
                  "rationale": "Unknown."
                }
              ]
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


def test_missing_constraint_result_remains_unresolved():
    decision = make_decision()

    resolver = ConstraintResolver(
        StubAgent([
            """
            {
              "results": [
                {
                  "constraint_id": "con_self_host",
                  "status": "satisfied",
                  "strength": 0.9,
                  "rationale": "Explicit."
                }
              ]
            }
            """,
            """
            {
              "results": []
            }
            """,
        ]),
        DummyConfig(),
    )

    results = resolver.resolve(
        make_state(),
        decision,
    )

    assert results == {
        "cand_qdrant": {
            "con_self_host": True,
        }
    }

    evaluation = evaluate_decision_case(
        decision,
        constraint_results=results,
    )

    # Qdrant is still unresolved because con_linux was omitted.
    assert "cand_qdrant" in evaluation.unresolved_candidate_ids

    # Milvus has no resolved constraints at all.
    assert "cand_milvus" in evaluation.unresolved_candidate_ids

    assert evaluation.disqualified_candidate_ids == []


def test_unknown_constraints_remain_unresolved():
    decision = make_decision()

    resolver = ConstraintResolver(
        StubAgent([
            """
            {
              "results": [
                {
                  "constraint_id": "con_self_host",
                  "status": "unknown",
                  "strength": 0.1,
                  "rationale": "Unknown."
                },
                {
                  "constraint_id": "con_linux",
                  "status": "unknown",
                  "strength": 0.1,
                  "rationale": "Unknown."
                }
              ]
            }
            """,
            """
            {
              "results": [
                {
                  "constraint_id": "con_self_host",
                  "status": "unknown",
                  "strength": 0.1,
                  "rationale": "Unknown."
                },
                {
                  "constraint_id": "con_linux",
                  "status": "unknown",
                  "strength": 0.1,
                  "rationale": "Unknown."
                }
              ]
            }
            """,
        ]),
        DummyConfig(),
    )

    results = resolver.resolve(
        make_state(),
        decision,
    )

    assert results == {}

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


def test_invalid_json_retries_once_per_candidate():
    agent = StubAgent([
        '{"results":',
        """
        {
          "results": [
            {
              "constraint_id": "con_self_host",
              "status": "satisfied",
              "strength": 0.9,
              "rationale": "Recovered."
            },
            {
              "constraint_id": "con_linux",
              "status": "satisfied",
              "strength": 0.8,
              "rationale": "Recovered."
            }
          ]
        }
        """,
        """
        {
          "results": [
            {
              "constraint_id": "con_self_host",
              "status": "unknown",
              "strength": 0.1,
              "rationale": "Unknown."
            },
            {
              "constraint_id": "con_linux",
              "status": "unknown",
              "strength": 0.1,
              "rationale": "Unknown."
            }
          ]
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

    assert results["cand_qdrant"] == {
        "con_self_host": True,
        "con_linux": True,
    }

    # Qdrant: failed call + retry
    # Milvus: one successful call
    assert agent.calls == 3


def test_unknown_constraint_id_causes_fail_closed_retry():
    agent = StubAgent([
        """
        {
          "results": [
            {
              "constraint_id": "invented_constraint",
              "status": "satisfied",
              "strength": 1.0,
              "rationale": "Invented."
            }
          ]
        }
        """,
        """
        {
          "results": []
        }
        """,
        """
        {
          "results": []
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

    assert results == {}

    # First candidate retries because the model invented an ID.
    # Second candidate succeeds with an empty result set.
    assert agent.calls == 3


def test_duplicate_constraint_ids_are_rejected():
    agent = StubAgent([
        """
        {
          "results": [
            {
              "constraint_id": "con_self_host",
              "status": "satisfied",
              "strength": 0.9,
              "rationale": "First."
            },
            {
              "constraint_id": "con_self_host",
              "status": "violated",
              "strength": 0.9,
              "rationale": "Contradictory duplicate."
            }
          ]
        }
        """,
        """
        {
          "results": []
        }
        """,
        """
        {
          "results": []
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

    assert results == {}
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


def test_identical_second_pass_reuses_candidate_cache():
    agent = StubAgent([
        """
        {
          "results": [
            {
              "constraint_id": "con_self_host",
              "status": "satisfied",
              "strength": 0.9,
              "rationale": "Supported."
            },
            {
              "constraint_id": "con_linux",
              "status": "satisfied",
              "strength": 0.9,
              "rationale": "Supported."
            }
          ]
        }
        """,
        """
        {
          "results": [
            {
              "constraint_id": "con_self_host",
              "status": "unknown",
              "strength": 0.1,
              "rationale": "Insufficient."
            },
            {
              "constraint_id": "con_linux",
              "status": "unknown",
              "strength": 0.1,
              "rationale": "Insufficient."
            }
          ]
        }
        """,
    ])

    resolver = ConstraintResolver(
        agent,
        DummyConfig(),
    )

    state = make_state()
    decision = make_decision()

    first = resolver.resolve(
        state,
        decision,
    )

    assert agent.calls == 2

    second = resolver.resolve(
        state,
        decision,
    )

    # No evidence or constraint changed.
    assert agent.calls == 2
    assert second == first


def test_only_candidate_with_changed_evidence_is_recomputed():
    agent = StubAgent([
        # First pass: Qdrant
        """
        {
          "results": [
            {
              "constraint_id": "con_self_host",
              "status": "satisfied",
              "strength": 0.9,
              "rationale": "Qdrant supports self-hosting."
            },
            {
              "constraint_id": "con_linux",
              "status": "satisfied",
              "strength": 0.9,
              "rationale": "Qdrant supports Linux."
            }
          ]
        }
        """,

        # First pass: Milvus
        """
        {
          "results": [
            {
              "constraint_id": "con_self_host",
              "status": "satisfied",
              "strength": 0.8,
              "rationale": "Milvus supports self-hosting."
            },
            {
              "constraint_id": "con_linux",
              "status": "satisfied",
              "strength": 0.8,
              "rationale": "Milvus supports Linux."
            }
          ]
        }
        """,

        # Second pass: only Qdrant should be recomputed.
        """
        {
          "results": [
            {
              "constraint_id": "con_self_host",
              "status": "satisfied",
              "strength": 0.95,
              "rationale": "Additional Qdrant evidence."
            },
            {
              "constraint_id": "con_linux",
              "status": "satisfied",
              "strength": 0.95,
              "rationale": "Additional Qdrant evidence."
            }
          ]
        }
        """,
    ])

    resolver = ConstraintResolver(
        agent,
        DummyConfig(),
    )

    state = make_state()
    decision = make_decision()

    resolver.resolve(
        state,
        decision,
    )

    assert agent.calls == 2

    state.evidence_items.append(
        Evidence(
            evidence_id="evi_qdrant_new",
            task_id=3,
            trace_id="trace_3",
            query="More Qdrant deployment evidence",
            backend="web",
            source_title="Additional Qdrant documentation",
            snippet=(
                "Qdrant provides another documented "
                "self-hosted Linux deployment path."
            ),
        )
    )

    second = resolver.resolve(
        state,
        decision,
    )

    # Qdrant fingerprint changed.
    # Milvus fingerprint stayed unchanged.
    assert agent.calls == 3

    assert second["cand_qdrant"] == {
        "con_self_host": True,
        "con_linux": True,
    }

    assert second["cand_milvus"] == {
        "con_self_host": True,
        "con_linux": True,
    }


def test_constraint_change_invalidates_candidate_cache():
    agent = StubAgent([
        """
        {
          "results": [
            {
              "constraint_id": "con_self_host",
              "status": "satisfied",
              "strength": 0.9,
              "rationale": "Supported."
            },
            {
              "constraint_id": "con_linux",
              "status": "satisfied",
              "strength": 0.9,
              "rationale": "Supported."
            }
          ]
        }
        """,
        """
        {
          "results": [
            {
              "constraint_id": "con_self_host",
              "status": "unknown",
              "strength": 0.1,
              "rationale": "Unknown."
            },
            {
              "constraint_id": "con_linux",
              "status": "unknown",
              "strength": 0.1,
              "rationale": "Unknown."
            }
          ]
        }
        """,
        """
        {
          "results": [
            {
              "constraint_id": "con_self_host",
              "status": "satisfied",
              "strength": 0.9,
              "rationale": "Re-evaluated."
            },
            {
              "constraint_id": "con_linux",
              "status": "satisfied",
              "strength": 0.9,
              "rationale": "Re-evaluated."
            }
          ]
        }
        """,
        """
        {
          "results": [
            {
              "constraint_id": "con_self_host",
              "status": "unknown",
              "strength": 0.1,
              "rationale": "Re-evaluated."
            },
            {
              "constraint_id": "con_linux",
              "status": "unknown",
              "strength": 0.1,
              "rationale": "Re-evaluated."
            }
          ]
        }
        """,
    ])

    resolver = ConstraintResolver(
        agent,
        DummyConfig(),
    )

    state = make_state()
    decision = make_decision()

    resolver.resolve(
        state,
        decision,
    )

    assert agent.calls == 2

    decision.constraints[0].text = (
        "Must support fully self-managed hosting"
    )

    resolver.resolve(
        state,
        decision,
    )

    # Constraint input changed for both candidates.
    assert agent.calls == 4


def test_failed_resolution_is_not_cached():
    decision = make_decision()

    # Keep only Qdrant so call counting is unambiguous.
    decision.candidates = [
        decision.candidates[0]
    ]

    agent = StubAgent([
        # First resolve: initial failure + retry failure.
        '{"results":',
        '{"results":',

        # Second resolve should call LLM again.
        """
        {
          "results": [
            {
              "constraint_id": "con_self_host",
              "status": "satisfied",
              "strength": 0.9,
              "rationale": "Recovered later."
            },
            {
              "constraint_id": "con_linux",
              "status": "satisfied",
              "strength": 0.9,
              "rationale": "Recovered later."
            }
          ]
        }
        """,
    ])

    resolver = ConstraintResolver(
        agent,
        DummyConfig(),
    )

    state = make_state()

    first = resolver.resolve(
        state,
        decision,
    )

    assert first == {}
    assert agent.calls == 2

    second = resolver.resolve(
        state,
        decision,
    )

    # Failed first pass was not cached.
    assert agent.calls == 3

    assert second == {
        "cand_qdrant": {
            "con_self_host": True,
            "con_linux": True,
        }
    }
