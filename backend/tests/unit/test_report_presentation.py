from models import (
    Candidate,
    CandidateDecisionResult,
    Constraint,
    DecisionCase,
    DecisionComparison,
    DecisionCriterion,
    DecisionEvaluation,
    DecisionReadiness,
    DecisionReevaluationTrigger,
    SummaryState,
    TodoItem,
)
from services.report_presentation import (
    TECHNICAL_DECISION_SECTIONS,
    build_fallback_user_report,
    validate_user_report,
)
from services.reporter import ReportingService


class Config:
    strip_thinking_tokens = False


class LeakingAgent:
    def run(self, prompt):
        del prompt
        return technical_report(
            "candidate_id=cand_postgresql"
        )

    def clear_history(self):
        pass


def decision_state(*, constraint_status="UNKNOWN"):
    candidates = [
        Candidate(
            candidate_id="cand_postgresql",
            name="PostgreSQL",
        ),
        Candidate(
            candidate_id="cand_mongodb",
            name="MongoDB",
        ),
    ]
    constraint = Constraint(
        constraint_id="con_transactions",
        text="强事务一致性要求",
    )
    missing = (
        [constraint.constraint_id]
        if constraint_status == "UNKNOWN"
        else []
    )
    violated = (
        [constraint.constraint_id]
        if constraint_status == "UNSATISFIED"
        else []
    )

    return SummaryState(
        research_topic="PostgreSQL vs MongoDB",
        decision_case=DecisionCase(
            decision_id="dec_database",
            question="PostgreSQL or MongoDB?",
            candidates=candidates,
            constraints=[constraint],
        ),
        decision_evaluation=DecisionEvaluation(
            decision_id="dec_database",
            status="incomplete",
            candidate_results=[
                CandidateDecisionResult(
                    candidate_id=candidate.candidate_id,
                    status="unresolved",
                    missing_constraint_ids=missing,
                    violated_constraint_ids=violated,
                )
                for candidate in candidates
            ],
        ),
        decision_comparison=DecisionComparison(
            decision_id="dec_database",
            status="incomplete",
            ranked_candidate_ids=[
                "cand_postgresql",
                "cand_mongodb",
            ],
        ),
        decision_readiness=DecisionReadiness(
            decision_id="dec_database",
            overall_score=0.6,
            status="NOT_READY",
            criterion_coverage=0.5,
            evidence_quality=0.5,
            applicability=0.5,
            agreement_score=0.5,
            decision_margin=0.1,
        ),
        todo_items=[
            TodoItem(
                id=987,
                title="Transactions",
                intent="Compare transactions",
                query="database transactions",
                status="completed",
                summary="Transaction summary",
                sources_summary="Source summary",
            )
        ],
    )


def technical_report(body="用户可读内容"):
    return "\n\n".join(
        [
            TECHNICAL_DECISION_SECTIONS[0] + "\n\n" + body,
            *TECHNICAL_DECISION_SECTIONS[1:],
        ]
    )


def test_user_report_accepts_required_sections():
    assert validate_user_report(
        technical_report(),
        decision_state(),
    )


def test_user_report_rejects_candidate_id():
    assert not validate_user_report(
        technical_report("candidate_id=cand_postgresql"),
        decision_state(),
    )


def test_user_report_rejects_raw_internal_json():
    report = '# 研究结果\n\n```json\n{"status": "internal"}\n```'

    assert not validate_user_report(
        report,
        SummaryState(research_topic="JSON research"),
    )


def test_user_report_rejects_structured_state_header():
    assert not validate_user_report(
        technical_report(
            "AUTHORITATIVE STRUCTURED DECISION STATE"
        ),
        decision_state(),
    )


def test_user_report_rejects_debug_presentation_phrases():
    for phrase in (
        "has insufficient confidence",
        "has insufficient coverage",
        "No evidence signals exist",
        "candidate eligibility remains unresolved",
    ):
        assert not validate_user_report(
            technical_report(phrase),
            decision_state(),
        )


def test_user_report_requires_section_order():
    sections = list(TECHNICAL_DECISION_SECTIONS)
    sections[2], sections[3] = sections[3], sections[2]

    assert not validate_user_report(
        "\n\n".join(sections),
        decision_state(),
    )


def test_reporting_service_falls_back_when_report_leaks_internal_state():
    state = decision_state()

    report = ReportingService(
        LeakingAgent(),
        Config(),
    ).generate_report(state)

    assert report.startswith("# 技术选型结论")
    assert "candidate_id" not in report
    assert any(
        notice["stage"] == "report_presentation_validation"
        and notice["degraded"] is True
        for notice in state.runtime_notices
    )


def test_fallback_report_does_not_expose_task_ids():
    state = SummaryState(
        research_topic="Explain transformers",
        todo_items=[
            TodoItem(
                id=987,
                title="Attention",
                intent="Explain attention",
                query="attention",
                summary="Attention summary",
            )
        ],
    )

    report = build_fallback_user_report(state)

    assert "任务 987" not in report
    assert "Task 987" not in report
    assert "task_id" not in report


def test_fallback_report_does_not_expose_internal_ids():
    report = build_fallback_user_report(decision_state())

    for marker in (
        "cand_postgresql",
        "cand_mongodb",
        "con_transactions",
        "dec_database",
        "candidate_id",
        "constraint_id",
        "decision_id",
    ):
        assert marker not in report


def test_fallback_report_preserves_unknown():
    report = build_fallback_user_report(
        decision_state(constraint_status="UNKNOWN")
    )

    constraint_line = next(
        line
        for line in report.splitlines()
        if "强事务一致性要求" in line
    )
    assert "未知" in constraint_line
    assert "当前证据不足" in constraint_line
    assert "不满足" not in constraint_line


def test_comparison_absence_is_distinct_from_satisfied_constraint():
    state = decision_state(constraint_status="SATISFIED")
    state.decision_case.criteria = [
        DecisionCriterion(
            criterion_id="crit_transactions",
            name="事务一致性能力",
            weight=1.0,
        )
    ]

    report = build_fallback_user_report(state)
    comparison = report.split(
        TECHNICAL_DECISION_SECTIONS[1], 1
    )[1].split(TECHNICAL_DECISION_SECTIONS[2], 1)[0]
    constraints = report.split(
        TECHNICAL_DECISION_SECTIONS[2], 1
    )[1].split(TECHNICAL_DECISION_SECTIONS[3], 1)[0]

    assert "独立候选比较状态" in comparison
    assert "— 暂无独立比较结论" in comparison
    assert "未验证" not in comparison
    assert "硬约束是否满足" in comparison
    assert "| 满足 |" in constraints


def test_fallback_report_does_not_invent_recommendation():
    report = build_fallback_user_report(decision_state())

    assert "推荐：暂不形成确定推荐" in report
    assert "综合表现靠前" not in report
    assert "正式建议：" not in report


def test_fallback_report_does_not_expose_reevaluation_debug_rationale():
    state = decision_state()
    state.decision_reevaluation_triggers = [
        DecisionReevaluationTrigger(
            trigger_id="trigger_context",
            decision_id="dec_database",
            trigger_type="TECHNICAL_CONTEXT_CHANGE",
            source_type="technical_context",
            source_field="team_capabilities",
            source_value="团队主要熟悉 PostgreSQL",
            rationale=[
                "Recompute affected modules: integration_assessment.",
                "1 counterfactual dependency path is linked.",
            ],
        )
    ]

    report = build_fallback_user_report(state)

    assert "团队主要熟悉 PostgreSQL" in report
    assert "发生变化" in report
    assert "应重新评估" in report
    assert "Recompute affected modules" not in report
    assert "counterfactual dependency path" not in report


def test_generic_research_report_does_not_require_decision_sections():
    report = "# 研究结论\n\n注意力机制让模型聚合上下文信息。"

    assert validate_user_report(
        report,
        SummaryState(
            research_topic="Explain transformers"
        ),
    )
