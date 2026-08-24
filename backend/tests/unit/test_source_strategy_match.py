from models import (
    EvidenceApplicability,
    EvidenceAssessment,
    EvidenceQuality,
    EvidenceSignal,
    ResearchGap,
    SourceQuality,
)
from services.source_strategy_match import (
    evaluate_source_strategy_matches,
)


def gap(
    *,
    preferred=None,
):
    return ResearchGap(
        gap_id="gap_test",
        candidate_id="cand_a",
        criterion_id="crit_scale",
        gap_type="low_coverage",
        severity=0.8,
        description="Need evidence",
        suggested_query="candidate scalability",
        search_strategy="PERFORMANCE_SCALE",
        preferred_source_types=(
            preferred
            if preferred is not None
            else [
                "official_documentation",
                "benchmark",
                "academic_paper",
            ]
        ),
    )


def signal(
    evidence_id,
):
    return EvidenceSignal(
        evidence_id=evidence_id,
        candidate_id="cand_a",
        criterion_id="crit_scale",
        direction="neutral",
        strength=0.5,
        source_confidence=0.8,
        applicability=0.8,
    )


def assessment(
    evidence_id,
    authority_type,
):
    return EvidenceAssessment(
        evidence_id=evidence_id,
        decision_id="dec_test",
        source_quality=SourceQuality(
            evidence_id=evidence_id,
            source_type="web",
            confidence=0.8,
            authority_type=authority_type,
            authority_level="HIGH",
        ),
        evidence_quality=EvidenceQuality(
            evidence_id=evidence_id,
            quality_score=0.8,
            completeness=0.8,
        ),
        applicability=EvidenceApplicability(
            evidence_id=evidence_id,
            decision_id="dec_test",
            applicability_score=0.8,
        ),
        overall_score=0.8,
    )


def test_full_strategy_match():
    item = gap()

    evaluate_source_strategy_matches(
        [item],
        [
            signal("evi_docs"),
            signal("evi_bench"),
            signal("evi_paper"),
        ],
        [
            assessment(
                "evi_docs",
                "OFFICIAL_DOCUMENTATION",
            ),
            assessment(
                "evi_bench",
                "INDEPENDENT_BENCHMARK",
            ),
            assessment(
                "evi_paper",
                "ACADEMIC",
            ),
        ],
    )

    assert (
        item.strategy_match_status
        == "FULL"
    )

    assert item.missing_source_types == []

    assert item.matched_source_types == [
        "official_documentation",
        "benchmark",
        "academic_paper",
    ]


def test_partial_strategy_match():
    item = gap()

    evaluate_source_strategy_matches(
        [item],
        [
            signal("evi_docs"),
        ],
        [
            assessment(
                "evi_docs",
                "OFFICIAL_DOCUMENTATION",
            ),
        ],
    )

    assert (
        item.strategy_match_status
        == "PARTIAL"
    )

    assert item.matched_source_types == [
        "official_documentation",
    ]

    assert item.missing_source_types == [
        "benchmark",
        "academic_paper",
    ]


def test_none_when_recognized_sources_do_not_match():
    item = gap(
        preferred=[
            "benchmark",
        ]
    )

    evaluate_source_strategy_matches(
        [item],
        [
            signal("evi_community"),
        ],
        [
            assessment(
                "evi_community",
                "COMMUNITY",
            ),
        ],
    )

    assert (
        item.strategy_match_status
        == "NONE"
    )

    assert item.matched_source_types == []

    assert item.missing_source_types == [
        "benchmark",
    ]

    assert (
        item.observed_authority_types
        == ["COMMUNITY"]
    )


def test_unknown_when_evidence_authority_is_unknown():
    item = gap()

    evaluate_source_strategy_matches(
        [item],
        [
            signal("evi_unknown"),
        ],
        [
            assessment(
                "evi_unknown",
                "UNKNOWN",
            ),
        ],
    )

    assert (
        item.strategy_match_status
        == "UNKNOWN"
    )


def test_no_signal_for_pair_is_none():
    item = gap()

    evaluate_source_strategy_matches(
        [item],
        [],
        [],
    )

    assert (
        item.strategy_match_status
        == "NONE"
    )

    assert (
        item.missing_source_types
        == item.preferred_source_types
    )


def test_no_strategy_is_unknown():
    item = gap(
        preferred=[],
    )

    evaluate_source_strategy_matches(
        [item],
        [],
        [],
    )

    assert (
        item.strategy_match_status
        == "UNKNOWN"
    )

    assert item.missing_source_types == []


def test_signal_from_other_candidate_does_not_match():
    item = gap(
        preferred=[
            "benchmark",
        ]
    )

    other_signal = EvidenceSignal(
        evidence_id="evi_other",
        candidate_id="cand_b",
        criterion_id="crit_scale",
        direction="neutral",
        strength=0.5,
        source_confidence=0.8,
        applicability=0.8,
    )

    evaluate_source_strategy_matches(
        [item],
        [other_signal],
        [
            assessment(
                "evi_other",
                "INDEPENDENT_BENCHMARK",
            ),
        ],
    )

    assert (
        item.strategy_match_status
        == "NONE"
    )


def test_signal_from_other_criterion_does_not_match():
    item = gap(
        preferred=[
            "benchmark",
        ]
    )

    other_signal = EvidenceSignal(
        evidence_id="evi_other",
        candidate_id="cand_a",
        criterion_id="crit_security",
        direction="neutral",
        strength=0.5,
        source_confidence=0.8,
        applicability=0.8,
    )

    evaluate_source_strategy_matches(
        [item],
        [other_signal],
        [
            assessment(
                "evi_other",
                "INDEPENDENT_BENCHMARK",
            ),
        ],
    )

    assert (
        item.strategy_match_status
        == "NONE"
    )


def test_security_authority_satisfies_security_preference():
    item = gap(
        preferred=[
            "official_security_documentation",
        ]
    )

    evaluate_source_strategy_matches(
        [item],
        [
            signal("evi_security"),
        ],
        [
            assessment(
                "evi_security",
                "OFFICIAL_SECURITY",
            ),
        ],
    )

    assert (
        item.strategy_match_status
        == "FULL"
    )


def test_pricing_authority_satisfies_pricing_preference():
    item = gap(
        preferred=[
            "official_pricing_documentation",
        ]
    )

    evaluate_source_strategy_matches(
        [item],
        [
            signal("evi_pricing"),
        ],
        [
            assessment(
                "evi_pricing",
                "OFFICIAL_PRICING",
            ),
        ],
    )

    assert (
        item.strategy_match_status
        == "FULL"
    )


def test_independent_technical_satisfies_engineering_review():
    item = gap(
        preferred=[
            "independent_engineering_review",
        ]
    )

    evaluate_source_strategy_matches(
        [item],
        [
            signal("evi_review"),
        ],
        [
            assessment(
                "evi_review",
                "INDEPENDENT_TECHNICAL",
            ),
        ],
    )

    assert (
        item.strategy_match_status
        == "FULL"
    )


def test_matched_evidence_ids_only_include_useful_sources():
    item = gap(
        preferred=[
            "benchmark",
        ]
    )

    evaluate_source_strategy_matches(
        [item],
        [
            signal("evi_benchmark"),
            signal("evi_community"),
        ],
        [
            assessment(
                "evi_benchmark",
                "INDEPENDENT_BENCHMARK",
            ),
            assessment(
                "evi_community",
                "COMMUNITY",
            ),
        ],
    )

    assert (
        item.strategy_matched_evidence_ids
        == ["evi_benchmark"]
    )


def test_duplicate_signals_do_not_duplicate_output():
    item = gap(
        preferred=[
            "benchmark",
        ]
    )

    evaluate_source_strategy_matches(
        [item],
        [
            signal("evi_benchmark"),
            signal("evi_benchmark"),
        ],
        [
            assessment(
                "evi_benchmark",
                "INDEPENDENT_BENCHMARK",
            ),
        ],
    )

    assert (
        item.strategy_matched_evidence_ids
        == ["evi_benchmark"]
    )

    assert (
        item.observed_authority_types
        == ["INDEPENDENT_BENCHMARK"]
    )


def test_assignment_is_deterministic():
    first = gap()
    second = gap()

    signals = [
        signal("evi_docs"),
    ]

    assessments = [
        assessment(
            "evi_docs",
            "OFFICIAL_DOCUMENTATION",
        ),
    ]

    evaluate_source_strategy_matches(
        [first],
        signals,
        assessments,
    )

    evaluate_source_strategy_matches(
        [second],
        signals,
        assessments,
    )

    assert (
        first.strategy_match_status
        == second.strategy_match_status
    )

    assert (
        first.matched_source_types
        == second.matched_source_types
    )

    assert (
        first.missing_source_types
        == second.missing_source_types
    )
