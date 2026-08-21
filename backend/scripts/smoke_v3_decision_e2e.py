#!/usr/bin/env python3
"""Smoke-test the persisted V3 technical-decision workflow.

Flow:
    GET  /healthz
    POST /research
    GET  /research/{research_id}/replay

Exit codes:
    0 = PASS
    1 = FAIL
    2 = BLOCKED by external LLM availability
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


PASS = 0
FAIL = 1
BLOCKED = 2

BLOCKING_LLM_CODES = {
    "llm_quota_exhausted",
    "llm_rate_limited",
    "llm_authentication_failed",
    "llm_timeout",
    "llm_unavailable",
}


@dataclass(frozen=True)
class HttpResult:
    status: int
    payload: Any


def _request_json(
    method: str,
    url: str,
    *,
    payload: dict[str, Any] | None = None,
    timeout: float = 300.0,
) -> HttpResult:
    body = None
    headers = {
        "Accept": "application/json",
    }

    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = urllib.request.Request(
        url,
        data=body,
        headers=headers,
        method=method,
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=timeout,
        ) as response:
            raw = response.read().decode("utf-8")
            parsed = json.loads(raw) if raw else None

            return HttpResult(
                status=response.status,
                payload=parsed,
            )

    except urllib.error.HTTPError as exc:
        raw = exc.read().decode(
            "utf-8",
            errors="replace",
        )

        try:
            parsed = json.loads(raw) if raw else None
        except json.JSONDecodeError:
            parsed = {
                "raw": raw,
            }

        return HttpResult(
            status=exc.code,
            payload=parsed,
        )


def _extract_llm_block(
    result: HttpResult,
) -> dict[str, Any] | None:
    """Return safe LLM-unavailable detail when HTTP response represents it."""

    if result.status != 503:
        return None

    payload = result.payload

    if not isinstance(payload, dict):
        return None

    detail = payload.get("detail")

    if not isinstance(detail, dict):
        return None

    code = detail.get("code")

    if code not in BLOCKING_LLM_CODES:
        return None

    return detail


def _extract_research_id(
    payload: Any,
) -> str | None:
    if not isinstance(payload, dict):
        return None

    research_id = payload.get("research_id")

    if isinstance(research_id, str):
        research_id = research_id.strip()

        if research_id:
            return research_id

    return None


def _require_mapping(
    value: Any,
    *,
    name: str,
) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise AssertionError(
            f"{name} must be an object"
        )

    return value


def validate_replay(
    replay: Any,
) -> dict[str, Any]:
    """Validate the minimum persisted V3 decision-intelligence contract."""

    replay_payload = _require_mapping(
        replay,
        name="replay",
    )

    research_id = replay_payload.get(
        "research_id"
    )

    if not isinstance(research_id, str) or not research_id:
        raise AssertionError(
            "replay.research_id is missing"
        )

    decision = _require_mapping(
        replay_payload.get("decision"),
        name="replay.decision",
    )

    case = _require_mapping(
        decision.get("case"),
        name="replay.decision.case",
    )

    candidates = case.get("candidates")

    if not isinstance(candidates, list) or not candidates:
        raise AssertionError(
            "decision case has no candidates"
        )

    usage = _require_mapping(
        decision.get("research_usage"),
        name="replay.decision.research_usage",
    )

    for field_name in (
        "iterations",
        "tasks",
        "semantic_llm_calls",
        "constraint_llm_calls",
    ):
        value = usage.get(field_name)

        if not isinstance(value, int):
            raise AssertionError(
                "research_usage."
                f"{field_name} must be an integer"
            )

        if value < 0:
            raise AssertionError(
                "research_usage."
                f"{field_name} must be non-negative"
            )

    return {
        "research_id": research_id,
        "candidate_count": len(candidates),
        "iterations": usage["iterations"],
        "tasks": usage["tasks"],
        "semantic_llm_calls": (
            usage["semantic_llm_calls"]
        ),
        "constraint_llm_calls": (
            usage["constraint_llm_calls"]
        ),
        "readiness_status": (
            decision.get("readiness") or {}
        ).get("status"),
        "stopping_reason": (
            decision.get("stopping_decision") or {}
        ).get("reason"),
    }


def run_smoke(
    *,
    base_url: str,
    topic: str,
    timeout: float,
) -> int:
    base_url = base_url.rstrip("/")

    print("=== V3 Decision E2E Smoke ===")
    print(f"Base URL: {base_url}")
    print(f"Topic: {topic}")
    print()

    # --------------------------------------------------
    # 1. Health
    # --------------------------------------------------

    print("[1/3] Checking /healthz ...")

    try:
        health = _request_json(
            "GET",
            f"{base_url}/healthz",
            timeout=10.0,
        )
    except Exception as exc:
        print(
            "FAIL: backend is unreachable:",
            str(exc),
        )
        return FAIL

    if health.status != 200:
        print(
            "FAIL: /healthz returned",
            health.status,
            health.payload,
        )
        return FAIL

    print("PASS: backend healthy")

    # --------------------------------------------------
    # 2. Research
    # --------------------------------------------------

    print("[2/3] Running /research ...")

    try:
        research = _request_json(
            "POST",
            f"{base_url}/research",
            payload={
                "topic": topic,
            },
            timeout=timeout,
        )
    except Exception as exc:
        print(
            "FAIL: /research request failed:",
            str(exc),
        )
        return FAIL

    llm_block = _extract_llm_block(
        research
    )

    if llm_block is not None:
        print("BLOCKED: external LLM unavailable")
        print(
            "  code:",
            llm_block.get("code"),
        )
        print(
            "  reason:",
            llm_block.get("reason"),
        )
        print(
            "  provider:",
            llm_block.get("provider"),
        )
        return BLOCKED

    if research.status != 200:
        print(
            "FAIL: /research returned",
            research.status,
        )
        print(
            json.dumps(
                research.payload,
                indent=2,
                ensure_ascii=False,
            )
        )
        return FAIL

    research_id = _extract_research_id(
        research.payload
    )

    if research_id is None:
        print(
            "FAIL: /research succeeded but "
            "research_id is missing"
        )
        print(
            json.dumps(
                research.payload,
                indent=2,
                ensure_ascii=False,
            )
        )
        return FAIL

    print(
        f"PASS: research completed ({research_id})"
    )

    # --------------------------------------------------
    # 3. Replay
    # --------------------------------------------------

    print("[3/3] Validating persisted replay ...")

    try:
        replay = _request_json(
            "GET",
            (
                f"{base_url}/research/"
                f"{research_id}/replay"
            ),
            timeout=30.0,
        )
    except Exception as exc:
        print(
            "FAIL: replay request failed:",
            str(exc),
        )
        return FAIL

    if replay.status != 200:
        print(
            "FAIL: replay returned",
            replay.status,
        )
        print(
            json.dumps(
                replay.payload,
                indent=2,
                ensure_ascii=False,
            )
        )
        return FAIL

    try:
        summary = validate_replay(
            replay.payload
        )
    except AssertionError as exc:
        print(
            "FAIL: persisted V3 replay contract invalid:"
        )
        print(
            f"  {exc}"
        )
        return FAIL

    print("PASS: persisted V3 replay valid")
    print()
    print("=== Decision Intelligence Summary ===")
    print(
        "Research ID:",
        summary["research_id"],
    )
    print(
        "Candidates:",
        summary["candidate_count"],
    )
    print(
        "Adaptive iterations:",
        summary["iterations"],
    )
    print(
        "Adaptive tasks:",
        summary["tasks"],
    )
    print(
        "Semantic LLM calls:",
        summary["semantic_llm_calls"],
    )
    print(
        "Constraint LLM calls:",
        summary["constraint_llm_calls"],
    )
    print(
        "Readiness:",
        summary["readiness_status"],
    )
    print(
        "Stopping reason:",
        summary["stopping_reason"],
    )

    print()
    print("RESULT: PASS")

    return PASS


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run the persisted V3 technical-decision "
            "E2E smoke test."
        )
    )

    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:8000",
        help="Backend base URL.",
    )

    parser.add_argument(
        "--topic",
        default=(
            "Compare Qdrant and Milvus for a "
            "production RAG system. Recommend one "
            "based on operational simplicity, "
            "scalability, and self-hosting support."
        ),
        help="Technical-decision research topic.",
    )

    parser.add_argument(
        "--timeout",
        type=float,
        default=600.0,
        help="Research request timeout in seconds.",
    )

    return parser.parse_args()


def main() -> int:
    args = parse_args()

    return run_smoke(
        base_url=args.base_url,
        topic=args.topic,
        timeout=args.timeout,
    )


if __name__ == "__main__":
    sys.exit(main())
