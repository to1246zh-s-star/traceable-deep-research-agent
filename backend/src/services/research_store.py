"""In-memory storage for completed or active research states."""

from __future__ import annotations

import uuid
from threading import Lock

from models import SummaryState


class InMemoryResearchStore:
    """Thread-safe in-memory store for research states."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._states: dict[str, SummaryState] = {}

    def save(self, state: SummaryState) -> str:
        """Store a research state and return its generated research id."""

        research_id = f"research_{uuid.uuid4().hex[:12]}"

        with self._lock:
            self._states[research_id] = state

        return research_id

    def get(self, research_id: str) -> SummaryState | None:
        """Return the stored state for a research id, if present."""

        with self._lock:
            return self._states.get(research_id)

    def list(self) -> list[tuple[str, SummaryState]]:
        """Return stored research states in insertion order."""

        with self._lock:
            return list(self._states.items())
