from types import SimpleNamespace

from models import (
    Candidate,
    Constraint,
    DecisionArtifact,
    DecisionCase,
    DecisionComparison,
    DecisionCriterion,
    DecisionReadiness,
    SummaryState,
)
from services.decision_artifact import (
    build_decision_artifact,
    render_decision_artifact_markdown,
)


def make_state(
    *,
    readiness_status="READY",
    recommendation=None,
):
    decision = DecisionCase(
        decision_id="dec_adr",
        question="Choose Qdrant or Milvus",
        context="Production RAG platform",
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
        criteria=[
            DecisionCriterion(
                criterion_id="crit_ops",
                name="Operations",
                weight=0.6,
            ),
            DecisionCriterion(
                criterion_id="crit_scale",
                name="Scalability",
                weight=0.4,
            ),
        ],
        constraints=[
            Constraint(
                constraint_id="con_self_host",
                text="Must support self-hosting",
            )
        ],
        recommendation=recommendation,
    )

    return SummaryState(
        research_topic="Qdrant vs Milvus",
        decision_case=decision,
        decision_comparison=DecisionComparison(
            decision_id="dec_adr",
            status="complete",
            ranked_candidate_ids=[
                "cand_qdrant",
                "cand_milvus",
            ],
        ),
        decision_readiness=DecisionReadiness(
            decision_id="dec_adr",
            overall_score=0.9,
            status=readiness_status,
            criterion_coverage=0.9,
            evidence_quality=0.9,
            applicability=0.9,
            agreement_score=0.9,
            decision_margin=0.2,
            blocking_reasons=[],
        ),
    )


def test_non_decision_returns_none():
    state = SummaryState(
        research_topic="Explain transformers"
    )

    assert (
        build_decision_artifact(state)
        is None
    )


def test_ready_with_recommendation_is_accepted():
    state = make_state(
        recommendation="Choose Qdrant."
    )

    artifact = build_decision_artifact(
        state
    )

    assert artifact is not None
    assert artifact.status == "ACCEPTED"
    assert artifact.recommendation == (
        "Choose Qdrant."
    )


def test_ready_without_recommendation_is_provisional():
    state = make_state(
        recommendation=None
    )

    artifact = build_decision_artifact(
        state
    )

    assert artifact is not None
    assert artifact.status == (
        "PROVISIONAL"
    )

    assert (
        "No structured recommendation recorded."
        in artifact.markdown
    )


def test_ranking_does_not_become_recommendation():
    state = make_state(
        recommendation=None
    )

    artifact = build_decision_artifact(
        state
    )

    assert artifact is not None
    assert artifact.recommendation is None

    assert (
        "Current deterministic ranking: "
        "Qdrant > Milvus"
        in artifact.markdown
    )

    assert (
        "## Decision\n\nQdrant"
        not in artifact.markdown
    )


def test_non_ready_with_recommendation_remains_provisional():
    state = make_state(
        readiness_status="CONFLICTED",
        recommendation="Choose Qdrant.",
    )

    artifact = build_decision_artifact(
        state
    )

    assert artifact is not None
    assert artifact.status == (
        "PROVISIONAL"
    )


def test_constraints_are_not_assumptions():
    state = make_state()

    state.decision_assumptions = [
        SimpleNamespace(
            assumption_id="asm_ops",
            description=(
                "Operations team remains small"
            ),
        )
    ]

    artifact = build_decision_artifact(
        state
    )

    assert artifact is not None

    assert (
        "Must support self-hosting"
        in artifact.constraint_lines
    )

    assert (
        "Must support self-hosting"
        not in artifact.assumption_lines
    )

    assert (
        "Operations team remains small"
        in artifact.assumption_lines
    )


def test_open_research_gaps_are_exported_as_risks():
    state = make_state()

    state.research_analysis = SimpleNamespace(
        research_gaps=[
            SimpleNamespace(
                gap_id="gap_scaling",
                status="open",
                description=(
                    "Need independent scaling benchmark"
                ),
            ),
            SimpleNamespace(
                gap_id="gap_closed",
                status="resolved",
                description="Already resolved",
            ),
        ]
    )

    artifact = build_decision_artifact(
        state
    )

    assert artifact is not None

    assert any(
        "Need independent scaling benchmark"
        in line
        for line in artifact.risk_lines
    )

    assert not any(
        "Already resolved" in line
        for line in artifact.risk_lines
    )


def test_reevaluation_triggers_are_projected_only():
    state = make_state()

    state.decision_reevaluation_triggers = [
        SimpleNamespace(
            trigger_id="trigger_scale",
            description=(
                "Re-evaluate if corpus exceeds 100M vectors"
            ),
        )
    ]

    artifact = build_decision_artifact(
        state
    )

    assert artifact is not None

    assert artifact.reevaluation_lines == [
        "Re-evaluate if corpus exceeds 100M vectors"
    ]


def test_markdown_is_deterministic():
    state = make_state(
        recommendation="Choose Qdrant."
    )

    first = build_decision_artifact(
        state
    )
    second = build_decision_artifact(
        state
    )

    assert first is not None
    assert second is not None

    assert first.markdown == second.markdown


def test_renderer_does_not_mutate_artifact():
    artifact = DecisionArtifact(
        decision_id="dec_test",
        title="ADR — Test",
        status="PROVISIONAL",
        decision_question="Test?",
        recommendation=None,
    )

    before = artifact.recommendation

    markdown = (
        render_decision_artifact_markdown(
            artifact
        )
    )

    assert artifact.recommendation == before
    assert (
        "No structured recommendation recorded."
        in markdown
    )
