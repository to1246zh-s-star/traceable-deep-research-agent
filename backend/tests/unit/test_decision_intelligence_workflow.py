from agent import DeepResearchAgent
from models import (
    Constraint,
    Candidate,
    DecisionCase,
    DecisionCriterion,
    Evidence,
    EvidenceSignal,
    SummaryState,

    TechnicalContext,)


class StubSemanticExtractor:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.calls = []

    def extract(
        self,
        state,
        decision,
        proposals,
    ):
        self.calls.append(
            (state, decision, proposals)
        )

        if self.error is not None:
            raise self.error

        return (
            self.result
            if self.result is not None
            else proposals
        )


def make_decision():
    return DecisionCase(
        decision_id="dec_full_workflow",
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
        criteria=[
            DecisionCriterion(
                criterion_id="crit_ops",
                name="Operational simplicity",
                weight=1.0,
            )
        ],
    )


def make_state():
    return SummaryState(
        research_topic="Qdrant vs Milvus",
        decision_case=make_decision(),
        evidence_items=[
            Evidence(
                evidence_id="evi_qdrant",
                task_id=1,
                trace_id="trace_1",
                query="Qdrant operational simplicity",
                backend="web",
                source_title="Qdrant documentation",
                snippet=(
                    "Qdrant operational simplicity "
                    "and deployment."
                ),
                source_rank=1,
            ),
            Evidence(
                evidence_id="evi_milvus",
                task_id=2,
                trace_id="trace_2",
                query="Milvus operational simplicity",
                backend="web",
                source_title="Milvus documentation",
                snippet=(
                    "Milvus operational simplicity "
                    "and deployment."
                ),
                source_rank=1,
            ),
        ],
    )


def make_agent(extractor):
    agent = object.__new__(
        DeepResearchAgent
    )
    agent.semantic_signal_extractor = extractor
    return agent


def test_no_decision_case_is_noop():
    state = SummaryState(
        research_topic="Explain attention"
    )

    extractor = StubSemanticExtractor()
    agent = make_agent(extractor)

    result = agent.execute_decision_intelligence(
        state
    )

    assert result is state
    assert extractor.calls == []
    assert state.decision_evaluation is None


def test_full_workflow_uses_semantic_signals():
    state = make_state()

    semantic_signals = [
        EvidenceSignal(
            evidence_id="evi_qdrant",
            candidate_id="cand_qdrant",
            criterion_id="crit_ops",
            direction="positive",
            strength=0.8,
            source_confidence=0.9,
            applicability=0.9,
        ),
        EvidenceSignal(
            evidence_id="evi_milvus",
            candidate_id="cand_milvus",
            criterion_id="crit_ops",
            direction="positive",
            strength=0.4,
            source_confidence=0.9,
            applicability=0.9,
        ),
    ]

    extractor = StubSemanticExtractor(
        result=semantic_signals
    )
    agent = make_agent(extractor)

    result = agent.execute_decision_intelligence(
        state
    )

    assert result is state

    assert len(
        state.evidence_assessments
    ) == 2

    assert len(state.evidence_signals) == 2

    assert (
        state.evidence_signals[0].direction
        == semantic_signals[0].direction
    )
    assert (
        state.evidence_signals[0].strength
        == semantic_signals[0].strength
    )

    assert (
        state.evidence_signals[1].direction
        == semantic_signals[1].direction
    )
    assert (
        state.evidence_signals[1].strength
        == semantic_signals[1].strength
    )

    # Deterministic evidence weights come from the freshly rebuilt
    # proposals rather than the semantic extractor output.
    assert (
        state.evidence_signals[0].source_confidence
        != semantic_signals[0].source_confidence
        or state.evidence_signals[0].applicability
        != semantic_signals[0].applicability
    )

    assert state.decision_evaluation is not None
    assert state.decision_comparison is not None

    assert (
        state.decision_comparison.status
        == "complete"
    )

    assert (
        state.decision_comparison
        .ranked_candidate_ids
        == [
            "cand_qdrant",
            "cand_milvus",
        ]
    )

    assert state.research_analysis is not None
    assert state.decision_readiness is not None
    assert state.stopping_decision is not None


def test_semantic_failure_falls_back_to_neutral():
    state = make_state()

    extractor = StubSemanticExtractor(
        error=RuntimeError(
            "semantic model unavailable"
        )
    )
    agent = make_agent(extractor)

    result = agent.execute_decision_intelligence(
        state
    )

    assert result is state

    assert state.evidence_signals
    assert all(
        signal.direction == "neutral"
        for signal in state.evidence_signals
    )

    assert state.decision_comparison is not None
    assert (
        state.decision_comparison.status
        == "incomplete"
    )


def test_constraints_remain_unresolved_without_results():
    state = make_state()

    from models import Constraint

    state.decision_case.constraints = [
        Constraint(
            constraint_id="con_self_hosted",
            text="Must support self-hosting",
        )
    ]

    extractor = StubSemanticExtractor()
    agent = make_agent(extractor)

    result = agent.execute_decision_intelligence(
        state
    )

    assert result is state

    assert state.decision_evaluation is not None
    assert (
        state.decision_evaluation.status
        == "incomplete"
    )

    assert set(
        state.decision_evaluation
        .unresolved_candidate_ids
    ) == {
        "cand_qdrant",
        "cand_milvus",
    }

    assert (
        state.decision_comparison.status
        == "incomplete"
    )


def test_decision_intelligence_auto_resolves_constraints(monkeypatch):
    agent = object.__new__(DeepResearchAgent)

    decision = DecisionCase(
        decision_id="dec_constraint_auto",
        question="Choose A or B",
        candidates=[
            Candidate(
                candidate_id="cand_a",
                name="A",
            ),
            Candidate(
                candidate_id="cand_b",
                name="B",
            ),
        ],
        constraints=[
            Constraint(
                constraint_id="con_required",
                text="Must satisfy requirement",
            ),
        ],
    )

    state = SummaryState(
        research_topic="Choose A or B",
        decision_case=decision,
    )

    agent.constraint_resolver = type(
        "Resolver",
        (),
        {
            "resolve": lambda self, state, decision: {
                "cand_a": {
                    "con_required": True,
                },
                "cand_b": {
                    "con_required": False,
                },
            }
        },
    )()

    monkeypatch.setattr(
        "agent.build_evidence_assessments",
        lambda state, decision: [],
    )

    monkeypatch.setattr(
        "agent.build_evidence_signals",
        lambda state, decision: [],
    )

    agent.extract_semantic_signals = (
        lambda state, decision, proposals: proposals
    )

    captured = {}

    def fake_pipeline(
        state,
        decision,
        *,
        constraint_results=None,
        technical_context=None,
        integration_assessments=None,
        evidence_signals=None,
        evidence_assessments=None,
        research_budget=None,
        research_usage=None,
    ):
        captured["constraint_results"] = constraint_results
        return state

    agent.execute_decision_pipeline = fake_pipeline

    result = agent.execute_decision_intelligence(state)

    assert result is state
    assert captured["constraint_results"] == {
        "cand_a": {
            "con_required": True,
        },
        "cand_b": {
            "con_required": False,
        },
    }


def test_decision_intelligence_constraint_resolution_failure_is_safe(
    monkeypatch,
):
    agent = object.__new__(DeepResearchAgent)

    decision = DecisionCase(
        decision_id="dec_constraint_fail",
        question="Choose A or B",
        candidates=[
            Candidate(
                candidate_id="cand_a",
                name="A",
            ),
            Candidate(
                candidate_id="cand_b",
                name="B",
            ),
        ],
        constraints=[
            Constraint(
                constraint_id="con_required",
                text="Must satisfy requirement",
            ),
        ],
    )

    state = SummaryState(
        research_topic="Choose A or B",
        decision_case=decision,
    )

    class FailingResolver:
        def resolve(self, state, decision):
            raise RuntimeError("resolver failure")

    agent.constraint_resolver = FailingResolver()

    monkeypatch.setattr(
        "agent.build_evidence_assessments",
        lambda state, decision: [],
    )

    monkeypatch.setattr(
        "agent.build_evidence_signals",
        lambda state, decision: [],
    )

    agent.extract_semantic_signals = (
        lambda state, decision, proposals: proposals
    )

    captured = {}

    def fake_pipeline(
        state,
        decision,
        *,
        constraint_results=None,
        technical_context=None,
        integration_assessments=None,
        evidence_signals=None,
        evidence_assessments=None,
        research_budget=None,
        research_usage=None,
    ):
        captured["constraint_results"] = constraint_results
        return state

    agent.execute_decision_pipeline = fake_pipeline

    result = agent.execute_decision_intelligence(state)

    assert result is state
    assert captured["constraint_results"] == {}


def test_explicit_constraint_results_skip_resolver(monkeypatch):
    agent = object.__new__(DeepResearchAgent)

    decision = DecisionCase(
        decision_id="dec_constraint_explicit",
        question="Choose A or B",
        candidates=[
            Candidate(
                candidate_id="cand_a",
                name="A",
            ),
            Candidate(
                candidate_id="cand_b",
                name="B",
            ),
        ],
        constraints=[
            Constraint(
                constraint_id="con_required",
                text="Must satisfy requirement",
            ),
        ],
    )

    state = SummaryState(
        research_topic="Choose A or B",
        decision_case=decision,
    )

    class ResolverMustNotRun:
        def resolve(self, state, decision):
            raise AssertionError(
                "constraint resolver should not be called"
            )

    agent.constraint_resolver = ResolverMustNotRun()

    monkeypatch.setattr(
        "agent.build_evidence_assessments",
        lambda state, decision: [],
    )

    monkeypatch.setattr(
        "agent.build_evidence_signals",
        lambda state, decision: [],
    )

    agent.extract_semantic_signals = (
        lambda state, decision, proposals: proposals
    )

    explicit_results = {
        "cand_a": {
            "con_required": True,
        },
        "cand_b": {
            "con_required": True,
        },
    }

    captured = {}

    def fake_pipeline(
        state,
        decision,
        *,
        constraint_results=None,
        technical_context=None,
        integration_assessments=None,
        evidence_signals=None,
        evidence_assessments=None,
        research_budget=None,
        research_usage=None,
    ):
        captured["constraint_results"] = constraint_results
        return state

    agent.execute_decision_pipeline = fake_pipeline

    result = agent.execute_decision_intelligence(
        state,
        constraint_results=explicit_results,
    )

    assert result is state
    assert captured["constraint_results"] == explicit_results


def test_decision_intelligence_reuses_existing_semantic_signals():
    from models import EvidenceSignal
    from services.decision_input_builder import (
        LEXICAL_SIGNAL_RATIONALE,
    )

    agent = make_agent(
        StubSemanticExtractor(result=[])
    )

    state = make_state()
    decision = state.decision_case

    assert decision is not None

    existing = EvidenceSignal(
        signal_id="sig_old",
        evidence_id=state.evidence_items[0].evidence_id,
        candidate_id=decision.candidates[0].candidate_id,
        criterion_id=decision.criteria[0].criterion_id,
        direction="positive",
        strength=0.8,
        source_confidence=0.9,
        applicability=0.8,
        rationale="Previously interpreted semantic result.",
    )

    state.evidence_signals = [existing]

    calls = []

    def fake_extract(
        state_arg,
        decision_arg,
        proposals,
    ):
        calls.append(list(proposals))
        return proposals

    agent.extract_semantic_signals = fake_extract

    agent.execute_decision_intelligence(state)

    # The already interpreted stable key should not be sent back to LLM.
    assert all(
        not (
            proposal.evidence_id == existing.evidence_id
            and proposal.candidate_id == existing.candidate_id
            and proposal.criterion_id == existing.criterion_id
        )
        for batch in calls
        for proposal in batch
    )


def test_failed_lexical_fallback_is_retried_next_pass():
    from models import EvidenceSignal
    from services.decision_input_builder import (
        LEXICAL_SIGNAL_RATIONALE,
    )

    agent = make_agent(
        StubSemanticExtractor(result=[])
    )

    state = make_state()
    decision = state.decision_case

    assert decision is not None

    fallback = EvidenceSignal(
        signal_id="sig_old",
        evidence_id=state.evidence_items[0].evidence_id,
        candidate_id=decision.candidates[0].candidate_id,
        criterion_id=decision.criteria[0].criterion_id,
        direction="neutral",
        strength=0.5,
        source_confidence=0.9,
        applicability=0.8,
        rationale=LEXICAL_SIGNAL_RATIONALE,
    )

    state.evidence_signals = [fallback]

    calls = []

    def fake_extract(
        state_arg,
        decision_arg,
        proposals,
    ):
        calls.extend(proposals)
        return proposals

    agent.extract_semantic_signals = fake_extract

    agent.execute_decision_intelligence(state)

    assert any(
        proposal.evidence_id == fallback.evidence_id
        and proposal.candidate_id == fallback.candidate_id
        and proposal.criterion_id == fallback.criterion_id
        for proposal in calls
    )



class UsageCounter:
    def __init__(self, llm_call_count=0):
        self.llm_call_count = llm_call_count


def test_decision_intelligence_records_semantic_llm_usage():
    agent = make_agent(
        StubSemanticExtractor(result=[])
    )

    state = make_state()

    # Replace with an explicitly observable semantic service.
    agent.semantic_signal_extractor.llm_call_count = 4

    # Constraint counting is irrelevant in this test.
    agent.constraint_resolver = UsageCounter()

    def fake_extract(
        state_arg,
        decision_arg,
        proposals,
    ):
        agent.semantic_signal_extractor.llm_call_count += 2
        return proposals

    agent.extract_semantic_signals = fake_extract

    agent.execute_decision_intelligence(state)

    assert state.research_usage is not None
    assert state.research_usage.semantic_llm_calls == 2
    assert state.research_usage.constraint_llm_calls == 0


def test_decision_intelligence_records_constraint_llm_usage():
    agent = make_agent(
        StubSemanticExtractor(result=[])
    )

    state = make_state()

    from models import Constraint

    state.decision_case.constraints = [
        Constraint(
            constraint_id="con_required",
            text="Must satisfy requirement",
        )
    ]

    class CountingResolver:
        def __init__(self):
            self.llm_call_count = 3

        def resolve(
            self,
            state_arg,
            decision_arg,
        ):
            self.llm_call_count += 1
            return {}

    agent.constraint_resolver = CountingResolver()

    agent.execute_decision_intelligence(state)

    assert state.research_usage is not None
    assert state.research_usage.constraint_llm_calls == 1


def test_decision_usage_accumulates_across_passes():
    agent = make_agent(
        StubSemanticExtractor(result=[])
    )

    state = make_state()

    from models import Constraint

    state.decision_case.constraints = [
        Constraint(
            constraint_id="con_required",
            text="Must satisfy requirement",
        )
    ]

    semantic_deltas = [2, 0]
    constraint_deltas = [2, 0]

    agent.semantic_signal_extractor.llm_call_count = 0

    class CountingResolver:
        def __init__(self):
            self.llm_call_count = 0

        def resolve(
            self,
            state_arg,
            decision_arg,
        ):
            delta = constraint_deltas.pop(0)
            self.llm_call_count += delta
            return {}

    agent.constraint_resolver = CountingResolver()

    def fake_extract(
        state_arg,
        decision_arg,
        proposals,
    ):
        delta = semantic_deltas.pop(0)
        agent.semantic_signal_extractor.llm_call_count += delta
        return proposals

    agent.extract_semantic_signals = fake_extract

    agent.execute_decision_intelligence(state)
    agent.execute_decision_intelligence(state)

    assert state.research_usage is not None

    assert (
        state.research_usage.semantic_llm_calls
        == 2
    )
    assert (
        state.research_usage.constraint_llm_calls
        == 2
    )


def test_decision_intelligence_extracts_technical_context():
    state = make_state()

    agent = make_agent(
        StubSemanticExtractor(result=[])
    )

    context = TechnicalContext(
        existing_stack=[
            "Python",
            "FastAPI",
        ],
        deployment_environment=[
            "Docker-only",
        ],
    )

    class ContextExtractor:
        def __init__(self):
            self.calls = []
            self.llm_call_count = 0

        def extract(
            self,
            topic,
            decision,
        ):
            self.calls.append(
                (topic, decision)
            )
            self.llm_call_count += 1
            return context

    extractor = ContextExtractor()

    agent.technical_context_extractor = (
        extractor
    )

    result = (
        agent.execute_decision_intelligence(
            state
        )
    )

    assert result is state
    assert state.technical_context is context
    assert len(extractor.calls) == 1

    assert state.research_usage is not None
    assert (
        state.research_usage.semantic_llm_calls
        >= 1
    )


def test_decision_intelligence_reuses_existing_technical_context():
    state = make_state()

    existing = TechnicalContext(
        existing_stack=["Python"]
    )
    state.technical_context = existing

    agent = make_agent(
        StubSemanticExtractor(result=[])
    )

    class MustNotRun:
        llm_call_count = 0

        def extract(
            self,
            topic,
            decision,
        ):
            raise AssertionError(
                "existing TechnicalContext "
                "must be reused"
            )

    agent.technical_context_extractor = (
        MustNotRun()
    )

    agent.execute_decision_intelligence(
        state
    )

    assert state.technical_context is existing


def test_decision_intelligence_populates_integration_assessments():
    state = make_state()

    context = TechnicalContext(
        existing_stack=["Python"],
        deployment_environment=[
            "Docker-only"
        ],
    )

    state.technical_context = context

    agent = make_agent(
        StubSemanticExtractor(result=[])
    )

    class StubIntegrationAssessor:
        def __init__(self):
            self.llm_call_count = 0
            self.calls = []

        def assess(
            self,
            state_arg,
            decision_arg,
            context_arg,
        ):
            from models import (
                IntegrationAssessment,
            )

            self.calls.append(
                (
                    state_arg,
                    decision_arg,
                    context_arg,
                )
            )

            self.llm_call_count += 1

            return [
                IntegrationAssessment(
                    decision_id=
                        decision_arg.decision_id,
                    candidate_id=
                        candidate.candidate_id,
                    integration_complexity="LOW",
                )
                for candidate
                in decision_arg.candidates
            ]

    assessor = StubIntegrationAssessor()

    agent.integration_assessor = assessor

    result = (
        agent.execute_decision_intelligence(
            state
        )
    )

    assert result is state

    assert len(
        state.integration_assessments
    ) == len(
        state.decision_case.candidates
    )

    assert all(
        assessment.integration_complexity
        == "LOW"
        for assessment
        in state.integration_assessments
    )

    assert assessor.calls
    assert state.research_usage is not None

    assert (
        state.research_usage
        .semantic_llm_calls
        >= 1
    )


def test_missing_integration_assessor_does_not_break_workflow():
    state = make_state()

    state.technical_context = (
        TechnicalContext(
            existing_stack=["Python"]
        )
    )

    agent = make_agent(
        StubSemanticExtractor(result=[])
    )

    # object.__new__ style test agents may not have the new service.
    assert not hasattr(
        agent,
        "integration_assessor",
    )

    result = (
        agent.execute_decision_intelligence(
            state
        )
    )

    assert result is state
    assert (
        state.integration_assessments
        == []
    )
    assert (
        state.decision_evaluation
        is not None
    )
