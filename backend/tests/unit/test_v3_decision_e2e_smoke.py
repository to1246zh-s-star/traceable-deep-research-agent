from scripts.smoke_v3_decision_e2e import (
    HttpResult,
    _extract_llm_block,
    validate_replay,
)


def test_extract_llm_block_recognizes_quota_failure():
    result = HttpResult(
        status=503,
        payload={
            "detail": {
                "code": "llm_quota_exhausted",
                "reason": "insufficient_balance",
                "provider": "custom",
            }
        },
    )

    detail = _extract_llm_block(result)

    assert detail is not None
    assert detail["code"] == "llm_quota_exhausted"
    assert detail["reason"] == "insufficient_balance"


def test_non_llm_503_is_not_classified_as_blocked():
    result = HttpResult(
        status=503,
        payload={
            "detail": {
                "code": "database_unavailable",
            }
        },
    )

    assert _extract_llm_block(result) is None


def test_validate_replay_accepts_persisted_decision_usage():
    payload = {
        "research_id": "research_123",
        "decision": {
            "case": {
                "candidates": [
                    {
                        "candidate_id": "cand_qdrant",
                        "name": "Qdrant",
                    },
                    {
                        "candidate_id": "cand_milvus",
                        "name": "Milvus",
                    },
                ]
            },
            "readiness": {
                "status": "TENTATIVE",
            },
            "stopping_decision": {
                "reason": "budget_exhausted",
            },
            "research_usage": {
                "iterations": 2,
                "tasks": 4,
                "semantic_llm_calls": 3,
                "constraint_llm_calls": 2,
            },
        },
    }

    summary = validate_replay(payload)

    assert summary["research_id"] == "research_123"
    assert summary["candidate_count"] == 2
    assert summary["iterations"] == 2
    assert summary["tasks"] == 4
    assert summary["semantic_llm_calls"] == 3
    assert summary["constraint_llm_calls"] == 2
    assert summary["readiness_status"] == "TENTATIVE"


def test_validate_replay_rejects_missing_decision():
    payload = {
        "research_id": "research_123",
        "decision": None,
    }

    try:
        validate_replay(payload)
    except AssertionError as exc:
        assert "replay.decision" in str(exc)
    else:
        raise AssertionError(
            "missing decision should fail validation"
        )
