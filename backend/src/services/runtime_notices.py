"""Structured observability for graceful runtime degradation."""

from __future__ import annotations

from typing import Any

from models import SummaryState
from services.execution_errors import classify_execution_error


MAX_NOTICE_MESSAGE_LENGTH = 500


def record_runtime_notice(
    state: SummaryState,
    *,
    stage: str,
    error: Exception,
    degraded: bool = True,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Record one structured runtime degradation notice.

    Runtime notices are observability only. They must never drive scoring,
    readiness, constraint resolution, or stopping behavior.
    """

    message = str(error).strip()

    if len(message) > MAX_NOTICE_MESSAGE_LENGTH:
        message = (
            message[:MAX_NOTICE_MESSAGE_LENGTH]
            + "..."
        )

    notice: dict[str, Any] = {
        "stage": stage,
        "error_type": classify_execution_error(error),
        "message": message,
        "degraded": bool(degraded),
    }

    if metadata:
        notice["metadata"] = dict(metadata)

    state.runtime_notices.append(notice)

    return notice
