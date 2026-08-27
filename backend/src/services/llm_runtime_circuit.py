"""Per-run circuit breaker for terminal LLM provider failures."""

from __future__ import annotations

from typing import Any

from models import SummaryState
from services.execution_errors import classify_execution_error
from services.runtime_notices import record_runtime_notice


TERMINAL_LLM_ERROR_TYPES = {
    "quota_exceeded",
    "authentication",
}


def is_terminal_llm_error(error: Exception) -> bool:
    """Return whether an error should stop later LLM calls in this run."""
    return (
        classify_execution_error(error)
        in TERMINAL_LLM_ERROR_TYPES
    )


def is_llm_circuit_open(
    state: SummaryState,
) -> bool:
    """Return whether this research run has opened its LLM circuit."""
    circuit = getattr(
        state,
        "llm_runtime_circuit",
        None,
    )

    return bool(
        circuit
        and circuit.get("status") == "open"
    )


def get_llm_circuit(
    state: SummaryState,
) -> dict[str, Any]:
    """Return a copy of the current circuit state."""
    circuit = getattr(
        state,
        "llm_runtime_circuit",
        None,
    )

    if not circuit:
        return {
            "status": "closed",
            "error_type": None,
            "trigger_stage": None,
        }

    return dict(circuit)


def open_llm_circuit(
    state: SummaryState,
    *,
    error: Exception,
    trigger_stage: str,
) -> bool:
    """
    Open the per-run circuit on a terminal provider error.

    Returns True only when this call transitions CLOSED -> OPEN.
    """
    error_type = classify_execution_error(
        error
    )

    if (
        error_type
        not in TERMINAL_LLM_ERROR_TYPES
    ):
        return False

    if is_llm_circuit_open(state):
        return False

    state.llm_runtime_circuit = {
        "status": "open",
        "error_type": error_type,
        "trigger_stage": trigger_stage,
    }

    record_runtime_notice(
        state,
        stage="llm_runtime_circuit",
        error=error,
        degraded=True,
        metadata={
            "status": "open",
            "trigger_stage": trigger_stage,
        },
    )

    return True


def open_llm_circuit_from_error(
    state: SummaryState,
    *,
    error: Exception,
    trigger_stage: str,
) -> None:
    """Best-effort convenience wrapper for orchestration boundaries."""
    open_llm_circuit(
        state,
        error=error,
        trigger_stage=trigger_stage,
    )


def record_circuit_skip(
    state: SummaryState,
    *,
    stage: str,
) -> None:
    """
    Record that an optional LLM stage was skipped because the circuit is open.

    Duplicate notices for the same stage are suppressed.
    """
    circuit = get_llm_circuit(state)

    for notice in state.runtime_notices:
        if (
            notice.get("stage") == stage
            and notice.get("error_type")
            == "llm_circuit_open"
        ):
            return

    state.runtime_notices.append(
        {
            "stage": stage,
            "error_type": "llm_circuit_open",
            "message": (
                "Optional LLM call skipped because the "
                "per-run LLM circuit is open."
            ),
            "degraded": True,
            "metadata": {
                "trigger_error_type": (
                    circuit.get("error_type")
                ),
                "trigger_stage": (
                    circuit.get("trigger_stage")
                ),
            },
        }
    )
