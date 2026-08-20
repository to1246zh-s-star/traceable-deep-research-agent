from models import EvidenceSignal
from services.decision_input_builder import (
    LEXICAL_SIGNAL_RATIONALE,
)
from services.incremental_semantic_signals import (
    is_semantically_interpreted,
    merge_semantic_signals,
    partition_semantic_proposals,
    signal_key,
)


def make_signal(
    *,
    signal_id="sig_1",
    evidence_id="evi_1",
    candidate_id="cand_1",
    criterion_id="crit_1",
    direction="neutral",
    strength=0.5,
    source_confidence=0.8,
    applicability=0.7,
    rationale=LEXICAL_SIGNAL_RATIONALE,
):
    return EvidenceSignal(
        signal_id=signal_id,
        evidence_id=evidence_id,
        candidate_id=candidate_id,
        criterion_id=criterion_id,
        direction=direction,
        strength=strength,
        source_confidence=source_confidence,
        applicability=applicability,
        rationale=rationale,
    )


def test_signal_key_ignores_generated_signal_id():
    first = make_signal(
        signal_id="sig_old",
    )

    second = make_signal(
        signal_id="sig_new",
    )

    assert signal_key(first) == signal_key(second)


def test_lexical_fallback_is_not_semantically_interpreted():
    signal = make_signal()

    assert (
        is_semantically_interpreted(signal)
        is False
    )


def test_directional_semantic_result_is_reusable():
    signal = make_signal(
        direction="positive",
        strength=0.9,
        rationale="Deployment is explicitly simple.",
    )

    assert (
        is_semantically_interpreted(signal)
        is True
    )


def test_semantic_neutral_result_is_reusable():
    signal = make_signal(
        direction="neutral",
        strength=0.1,
        rationale="Evidence does not establish an advantage.",
    )

    assert (
        is_semantically_interpreted(signal)
        is True
    )


def test_partition_reuses_existing_semantic_result():
    previous = make_signal(
        signal_id="sig_old",
        direction="positive",
        strength=0.9,
        rationale="Semantic result.",
    )

    current = make_signal(
        signal_id="sig_new",
    )

    reusable, pending = (
        partition_semantic_proposals(
            [current],
            [previous],
        )
    )

    assert signal_key(current) in reusable
    assert pending == []


def test_partition_retries_previous_lexical_fallback():
    previous = make_signal(
        signal_id="sig_old",
    )

    current = make_signal(
        signal_id="sig_new",
    )

    reusable, pending = (
        partition_semantic_proposals(
            [current],
            [previous],
        )
    )

    assert reusable == {}
    assert pending == [current]


def test_new_evidence_remains_pending():
    previous = make_signal(
        evidence_id="evi_old",
        direction="positive",
        rationale="Semantic result.",
    )

    current = make_signal(
        evidence_id="evi_new",
    )

    reusable, pending = (
        partition_semantic_proposals(
            [current],
            [previous],
        )
    )

    assert reusable == {}
    assert pending == [current]


def test_merge_reuses_semantics_but_refreshes_deterministic_weights():
    previous = make_signal(
        signal_id="sig_old",
        direction="positive",
        strength=0.9,
        source_confidence=0.3,
        applicability=0.4,
        rationale="Semantic result.",
    )

    current = make_signal(
        signal_id="sig_new",
        source_confidence=0.95,
        applicability=0.85,
    )

    reusable, pending = (
        partition_semantic_proposals(
            [current],
            [previous],
        )
    )

    assert pending == []

    merged = merge_semantic_signals(
        [current],
        reusable,
        [],
    )

    assert len(merged) == 1

    signal = merged[0]

    assert signal.signal_id == "sig_new"
    assert signal.direction == "positive"
    assert signal.strength == 0.9
    assert signal.rationale == "Semantic result."

    # Must use freshly rebuilt deterministic values.
    assert signal.source_confidence == 0.95
    assert signal.applicability == 0.85


def test_merge_new_semantic_result_takes_priority():
    proposal = make_signal(
        signal_id="sig_current",
    )

    reusable_signal = make_signal(
        signal_id="sig_old",
        direction="negative",
        strength=0.7,
        rationale="Old semantic result.",
    )

    new_signal = make_signal(
        signal_id="sig_current",
        direction="positive",
        strength=0.8,
        rationale="New semantic result.",
    )

    reusable = {
        signal_key(reusable_signal):
            reusable_signal,
    }

    merged = merge_semantic_signals(
        [proposal],
        reusable,
        [new_signal],
    )

    assert merged[0].direction == "positive"
    assert merged[0].strength == 0.8
    assert merged[0].rationale == "New semantic result."


def test_merge_preserves_unresolved_lexical_proposal():
    proposal = make_signal()

    merged = merge_semantic_signals(
        [proposal],
        {},
        [],
    )

    assert merged == [proposal]
