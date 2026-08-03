"""Execution trace query and serialization service."""

from __future__ import annotations

from threading import Lock
from typing import Any

from models import SummaryState


class ExecutionTraceService:
    """Query and serialize execution traces and related events."""

    def __init__(self, *, lock: Lock) -> None:
        self._lock = lock

    def get_trace(
        self,
        state: SummaryState,
        trace_id: str,
    ) -> dict[str, Any]:
        """Return one trace and all events associated with it."""

        with self._lock:
            trace = next(
                (
                    item
                    for item in state.execution_traces
                    if item.trace_id == trace_id
                ),
                None,
            )

            events = [
                event
                for event in state.execution_event_history
                if event.trace_id == trace_id
            ]

        return {
            "trace": trace,
            "events": events,
        }

    def serialize_trace(
        self,
        state: SummaryState,
        trace_id: str,
    ) -> dict[str, Any]:
        """Return one trace and its events as JSON-compatible data."""

        result = self.get_trace(
            state,
            trace_id,
        )

        trace = result["trace"]
        events = result["events"]

        return {
            "trace": {
                "trace_id": trace.trace_id if trace else None,
                "task_id": trace.task_id if trace else None,
                "status": trace.status if trace else None,
                "started_at": trace.started_at if trace else None,
                "finished_at": trace.finished_at if trace else None,
                "duration_ms": trace.duration_ms if trace else None,
                "current_stage": trace.current_stage if trace else None,
                "retry_count": trace.retry_count if trace else None,
                "error_type": trace.error_type if trace else None,
                "error_message": trace.error_message if trace else None,
            },
            "events": [
                {
                    "schema_version": event.schema_version,
                    "event_id": event.event_id,
                    "trace_id": event.trace_id,
                    "timestamp": event.timestamp,
                    "task_id": event.task_id,
                    "event_type": event.event_type,
                    "stage": event.stage,
                    "metadata": event.metadata,
                }
                for event in events
            ],
        }
