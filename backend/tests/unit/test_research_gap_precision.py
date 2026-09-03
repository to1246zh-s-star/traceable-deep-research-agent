from models import (
    AdaptiveResearchState,
    Candidate,
    DecisionCase,
    DecisionComparison,
    DecisionCriterion,
    DecisionEvaluation,
    EvidenceApplicability,
    EvidenceAssessment,
    EvidenceQuality,
    EvidenceSignal,
    ResearchAnalysis,
    ResearchGap,
    SourceQuality,
    TechnicalContext,
)
from services.adaptive_research import select_research_gaps
from services.decision_impact_gaps import (
    enrich_research_gaps_with_decision_impact,
)
from services.search_strategy import assign_search_strategies
from services.source_strategy_match import evaluate_source_strategy_matches


def make_gap(criterion_id, description="Missing evidence"):
    return ResearchGap(
        gap_id=f"gap_{criterion_id}",
        candidate_id="cand_db",
        criterion_id=criterion_id,
        gap_type="missing_evidence",
        severity=1.0,
        description=description,
        suggested_query=f"PostgreSQL {description}",
    )


def make_decision(criterion_name):
    return DecisionCase(
        decision_id="dec_precision",
        question="Choose a database",
        candidates=[Candidate(candidate_id="cand_db", name="PostgreSQL")],
        criteria=[
            DecisionCriterion(
                criterion_id="crit_target",
                name=criterion_name,
                weight=1.0,
            )
        ],
    )


def apply_context_policy(criterion_name, context=None, description="Missing evidence"):
    decision = make_decision(criterion_name)
    gap = make_gap("crit_target", description)
    analysis = ResearchAnalysis(
        decision_id=decision.decision_id,
        research_gaps=[gap],
    )
    enrich_research_gaps_with_decision_impact(
        decision,
        analysis,
        DecisionComparison(decision_id=decision.decision_id, status="incomplete"),
        DecisionEvaluation(decision_id=decision.decision_id, status="incomplete"),
        [],
        None,
        context,
        [],
    )
    assign_search_strategies(decision, analysis.research_gaps)
    return analysis, gap


def test_team_familiarity_does_not_create_web_followup():
    analysis, gap = apply_context_policy(
        "Team familiarity and maintenance cost",
        TechnicalContext(team_capabilities=["team knows PostgreSQL"]),
    )

    assert gap.status == "not_externally_researchable"
    assert gap.decision_impact == "UNKNOWN"
    assert select_research_gaps(
        analysis,
        AdaptiveResearchState(decision_id=analysis.decision_id),
    ) == []


def test_deployment_context_does_not_create_web_followup():
    analysis, gap = apply_context_policy(
        "Deployment environment",
        TechnicalContext(deployment_environment=["no Kubernetes"]),
    )

    assert gap.status == "not_externally_researchable"
    assert gap.suggested_query is None
    assert select_research_gaps(
        analysis,
        AdaptiveResearchState(decision_id=analysis.decision_id),
    ) == []


def test_missing_product_capability_allows_official_docs_followup():
    decision = make_decision("Multi-document transaction support")
    gap = make_gap("crit_target", "MongoDB transaction semantics are unclear")

    assign_search_strategies(decision, [gap])

    assert gap.preferred_source_types == ["official_documentation"]
    assert select_research_gaps(
        ResearchAnalysis(decision_id=decision.decision_id, research_gaps=[gap]),
        AdaptiveResearchState(decision_id=decision.decision_id),
    ) == [gap]


def assessment(authority_type):
    return EvidenceAssessment(
        evidence_id="evi_docs",
        decision_id="dec_precision",
        source_quality=SourceQuality(
            evidence_id="evi_docs",
            source_type="official_docs",
            confidence=0.9,
            authority_type=authority_type,
            authority_level="HIGH",
        ),
        evidence_quality=EvidenceQuality(
            evidence_id="evi_docs", quality_score=1.0, completeness=1.0
        ),
        applicability=EvidenceApplicability(
            evidence_id="evi_docs",
            decision_id="dec_precision",
            applicability_score=1.0,
        ),
        overall_score=0.9,
    )


def matching_signal():
    return EvidenceSignal(
        evidence_id="evi_docs",
        candidate_id="cand_db",
        criterion_id="crit_target",
        direction="positive",
        strength=1.0,
        source_confidence=0.9,
        applicability=1.0,
    )


def test_official_docs_close_product_capability_and_hard_constraint():
    for criterion in (
        "Multi-document transaction support",
        "Must support ACID hard constraint",
    ):
        decision = make_decision(criterion)
        gap = make_gap("crit_target")
        assign_search_strategies(decision, [gap])
        evaluate_source_strategy_matches(
            [gap], [matching_signal()], [assessment("OFFICIAL_DOCUMENTATION")]
        )
        assert gap.strategy_match_status == "FULL"


def test_vendor_comparison_does_not_close_comparative_performance():
    decision = make_decision("PostgreSQL vs MongoDB performance comparison")
    gap = make_gap("crit_target")
    assign_search_strategies(decision, [gap])
    evaluate_source_strategy_matches(
        [gap], [matching_signal()], [assessment("VENDOR")]
    )

    assert gap.preferred_source_types == ["benchmark"]
    assert gap.strategy_match_status == "NONE"


def test_equivalent_pair_gaps_create_only_one_followup():
    first = make_gap("crit_target", "transaction consistency evidence")
    second = make_gap("crit_target", "ACID official source")
    second.gap_id = "gap_equivalent"

    selected = select_research_gaps(
        ResearchAnalysis(
            decision_id="dec_precision",
            research_gaps=[first, second],
        ),
        AdaptiveResearchState(decision_id="dec_precision"),
    )

    assert len(selected) == 1
