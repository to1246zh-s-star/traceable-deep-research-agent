from models import (
    AdaptiveResearchIteration,
    Claim,
    EvidenceSignal,
)
from services.claim_information_gain import (
    ClaimInformationSnapshot,
    assess_iteration_information_gain,
    candidate_criterion_key,
    capture_claim_information_snapshot,
    claim_signature,
    enrich_retrieval_yield_with_information_gain,
)


def iteration(
    *,
    status="completed",
):
    return AdaptiveResearchIteration(
        decision_id="dec_test",
        iteration_number=1,
        status=status,
    )


def snapshot(
    *,
    claims=None,
    signals=None,
    pairs=None,
):
    return ClaimInformationSnapshot(
        claim_signatures=set(
            claims or []
        ),
        directional_signal_keys=set(
            signals or []
        ),
        covered_pairs=set(
            pairs or []
        ),
    )


def make_claim(
    text,
):
    return Claim(
        claim_id=f"claim_{abs(hash(text))}",
        task_id=1,
        trace_id="trace_test",
        text=text,
    )


def test_identical_claim_text_has_same_signature():
    first = make_claim(
        "Qdrant supports distributed deployment."
    )

    second = make_claim(
        "Qdrant supports distributed deployment!"
    )

    assert (
        claim_signature(first)
        == claim_signature(second)
    )


def test_no_new_claim_or_signal_is_no_information_gain():
    item = iteration()

    status = assess_iteration_information_gain(
        item,
        snapshot(
            claims={"claim a"},
        ),
        snapshot(
            claims={"claim a"},
        ),
        before_claim_count=1,
        after_claim_count=1,
    )

    assert status == "NO_INFORMATION_GAIN"


def test_duplicate_new_claim_is_low_information_gain():
    item = iteration()

    status = assess_iteration_information_gain(
        item,
        snapshot(
            claims={"same claim"},
        ),
        snapshot(
            claims={"same claim"},
        ),
        before_claim_count=1,
        after_claim_count=2,
    )

    assert status == "LOW_INFORMATION_GAIN"
    assert item.new_claim_count == 1
    assert item.novel_claim_count == 0
    assert item.duplicate_claim_count == 1


def test_novel_claims_are_moderate_information_gain():
    item = iteration()

    status = assess_iteration_information_gain(
        item,
        snapshot(
            claims={"existing claim"},
        ),
        snapshot(
            claims={
                "existing claim",
                "novel claim one",
                "novel claim two",
            },
        ),
        before_claim_count=1,
        after_claim_count=3,
    )

    assert (
        status
        == "MODERATE_INFORMATION_GAIN"
    )

    assert item.novel_claim_count == 2
    assert item.claim_novelty_ratio == 1.0


def test_new_directional_signal_is_moderate():
    item = iteration()

    status = assess_iteration_information_gain(
        item,
        snapshot(),
        snapshot(
            signals={
                "e1|cand|crit|POSITIVE"
            },
            pairs={
                "cand|crit"
            },
        ),
        before_claim_count=0,
        after_claim_count=0,
    )

    assert status == "HIGH_INFORMATION_GAIN"


def test_new_candidate_criterion_pair_is_high_gain():
    item = iteration()

    status = assess_iteration_information_gain(
        item,
        snapshot(
            signals={
                "e1|cand|crit1|POSITIVE"
            },
            pairs={
                "cand|crit1"
            },
        ),
        snapshot(
            signals={
                "e1|cand|crit1|POSITIVE",
                "e2|cand|crit2|NEGATIVE",
            },
            pairs={
                "cand|crit1",
                "cand|crit2",
            },
        ),
        before_claim_count=1,
        after_claim_count=2,
    )

    assert status == "HIGH_INFORMATION_GAIN"

    assert (
        item.new_candidate_criterion_pairs
        == ["cand|crit2"]
    )


def test_new_signal_on_existing_pair_is_moderate():
    item = iteration()

    status = assess_iteration_information_gain(
        item,
        snapshot(
            signals={
                "e1|cand|crit|POSITIVE"
            },
            pairs={
                "cand|crit"
            },
        ),
        snapshot(
            signals={
                "e1|cand|crit|POSITIVE",
                "e2|cand|crit|NEGATIVE",
            },
            pairs={
                "cand|crit"
            },
        ),
        before_claim_count=1,
        after_claim_count=1,
    )

    assert (
        status
        == "MODERATE_INFORMATION_GAIN"
    )

    assert (
        item.new_directional_signal_count
        == 1
    )

    assert (
        item.new_candidate_criterion_pairs
        == []
    )


def test_failed_iteration_is_unknown():
    item = iteration(
        status="failed",
    )

    status = assess_iteration_information_gain(
        item,
        snapshot(),
        snapshot(),
        before_claim_count=0,
        after_claim_count=0,
    )

    assert status == "UNKNOWN"


def test_information_gain_enriches_yield_without_changing_it():
    item = iteration()

    item.retrieval_yield_status = (
        "LOW_YIELD"
    )
    item.retrieval_yield_reasons = []
    item.information_gain_status = (
        "HIGH_INFORMATION_GAIN"
    )

    enrich_retrieval_yield_with_information_gain(
        item
    )

    assert (
        item.retrieval_yield_status
        == "LOW_YIELD"
    )

    assert (
        "decision information gain: high_information_gain"
        in item.retrieval_yield_reasons
    )


def test_candidate_criterion_key_is_deterministic():
    assert (
        candidate_criterion_key(
            "cand_a",
            "crit_scale",
        )
        == "cand_a|crit_scale"
    )
