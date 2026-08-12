"""Semantic interpretation of evidence signals using reliable JSON output."""

from __future__ import annotations

import json
import logging
from typing import Any

from hello_agents import ToolAwareSimpleAgent

from config import Configuration
from models import (
    DecisionCase,
    Evidence,
    EvidenceSignal,
    SummaryState,
)
from utils import strip_thinking_tokens

logger = logging.getLogger(__name__)


SIGNAL_PROMPT = """
You are a conservative technical evidence interpreter.

You are given:
- one technical decision candidate,
- one decision criterion,
- one retrieved evidence item.

Your task is ONLY to determine how this evidence affects that candidate
with respect to that criterion.

Candidate:
{name}

Criterion:
{criterion}

Evidence:
{evidence}

Return ONLY valid JSON:

{{
  "direction": "positive",
  "strength": 0.0,
  "rationale": "brief evidence-grounded explanation"
}}

Allowed direction values:
- "positive": evidence supports the candidate on this criterion
- "negative": evidence indicates a disadvantage on this criterion
- "neutral": evidence is relevant but does not establish either direction

Rules:
1. Use only the supplied evidence.
2. Never infer missing facts.
3. If the evidence is ambiguous, descriptive, incomplete, or does not
   establish an advantage/disadvantage, use "neutral".
4. strength must be between 0 and 1.
5. Neutral evidence should normally have low strength.
6. Do not evaluate source trustworthiness. Source confidence and
   applicability are handled separately by deterministic services.
7. Return no markdown and no text outside the JSON object.
""".strip()


class SemanticSignalExtractor:
    """
    Convert conservative neutral signal proposals into semantic directions.

    Candidate/criterion relevance is determined upstream. This service only
    interprets direction and strength from the associated evidence text.
    """

    VALID_DIRECTIONS = {
        "positive",
        "negative",
        "neutral",
    }

    def __init__(
        self,
        extraction_agent: ToolAwareSimpleAgent,
        config: Configuration,
    ) -> None:
        self._agent = extraction_agent
        self._config = config

        self.max_retries = 1
        self.last_parse_status = "unknown"
        self.retry_count = 0

    def extract(
        self,
        state: SummaryState,
        decision: DecisionCase,
        proposals: list[EvidenceSignal],
    ) -> list[EvidenceSignal]:
        """Semantically interpret existing candidate × criterion proposals."""

        evidence_by_id = {
            evidence.evidence_id: evidence
            for evidence in state.evidence_items
        }

        candidate_by_id = {
            candidate.candidate_id: candidate
            for candidate in decision.candidates
        }

        criterion_by_id = {
            criterion.criterion_id: criterion
            for criterion in decision.criteria
        }

        interpreted: list[EvidenceSignal] = []

        for proposal in proposals:
            evidence = evidence_by_id.get(
                proposal.evidence_id
            )
            candidate = candidate_by_id.get(
                proposal.candidate_id
            )
            criterion = criterion_by_id.get(
                proposal.criterion_id
            )

            if (
                evidence is None
                or candidate is None
                or criterion is None
            ):
                continue

            result = self._classify(
                evidence=evidence,
                candidate_name=candidate.name,
                criterion_name=criterion.name,
            )

            if result is None:
                # Parsing/LLM failure must not invent direction.
                interpreted.append(proposal)
                continue

            interpreted.append(
                EvidenceSignal(
                    evidence_id=proposal.evidence_id,
                    candidate_id=proposal.candidate_id,
                    criterion_id=proposal.criterion_id,
                    direction=result["direction"],
                    strength=result["strength"],
                    source_confidence=proposal.source_confidence,
                    applicability=proposal.applicability,
                    atomic_claim_id=proposal.atomic_claim_id,
                    rationale=result["rationale"],
                )
            )

        return interpreted

    def _classify(
        self,
        *,
        evidence: Evidence,
        candidate_name: str,
        criterion_name: str,
    ) -> dict[str, Any] | None:
        """Run one conservative semantic classification with one retry."""

        self.retry_count = 0
        self.last_parse_status = "unknown"

        evidence_text = self._evidence_text(evidence)

        if not evidence_text:
            self.last_parse_status = "empty_evidence"
            return None

        prompt = SIGNAL_PROMPT.format(
            name=candidate_name,
            criterion=criterion_name,
            evidence=evidence_text,
        )

        result = self._run_and_parse(prompt)

        if (
            result is None
            and self.last_parse_status
            in {
                "empty_output",
                "json_error",
                "invalid_schema",
            }
            and self.retry_count < self.max_retries
        ):
            failure_status = self.last_parse_status
            self.retry_count += 1

            retry_prompt = (
                prompt
                + "\n\nREPAIR INSTRUCTION:\n"
                + self._repair_instruction(
                    failure_status
                )
            )

            result = self._run_and_parse(
                retry_prompt
            )

        return result

    def _run_and_parse(
        self,
        prompt: str,
    ) -> dict[str, Any] | None:
        """Invoke semantic agent and validate its JSON response."""

        response = self._agent.run(prompt)
        self._agent.clear_history()

        logger.info(
            "Semantic signal output (truncated): %s",
            response[:500],
        )

        return self._extract_payload(response)

    def _extract_payload(
        self,
        raw_response: str,
    ) -> dict[str, Any] | None:
        """Parse one semantic signal result."""

        text = (raw_response or "").strip()

        if not text:
            self.last_parse_status = "empty_output"
            return None

        if self._config.strip_thinking_tokens:
            text = strip_thinking_tokens(text)

        start = text.find("{")
        end = text.rfind("}")

        if (
            start == -1
            or end == -1
            or end <= start
        ):
            self.last_parse_status = "json_error"
            return None

        try:
            payload = json.loads(
                text[start : end + 1]
            )
        except json.JSONDecodeError:
            self.last_parse_status = "json_error"
            return None

        if not self._is_valid_payload(payload):
            self.last_parse_status = "invalid_schema"
            return None

        self.last_parse_status = "success"

        return {
            "direction": payload["direction"],
            "strength": float(
                payload["strength"]
            ),
            "rationale": (
                payload.get("rationale")
                or ""
            ).strip(),
        }

    def _is_valid_payload(
        self,
        payload: Any,
    ) -> bool:
        """Validate semantic signal JSON schema."""

        if not isinstance(payload, dict):
            return False

        direction = payload.get("direction")
        strength = payload.get("strength")
        rationale = payload.get("rationale")

        if direction not in self.VALID_DIRECTIONS:
            return False

        if isinstance(strength, bool):
            return False

        if not isinstance(
            strength,
            (int, float),
        ):
            return False

        if not 0.0 <= float(strength) <= 1.0:
            return False

        if (
            rationale is not None
            and not isinstance(rationale, str)
        ):
            return False

        return True

    @staticmethod
    def _repair_instruction(
        failure_status: str,
    ) -> str:
        """Return targeted JSON repair instruction."""

        if failure_status == "json_error":
            return (
                "Your previous response was invalid JSON. "
                "Return only one valid JSON object."
            )

        if failure_status == "invalid_schema":
            return (
                "Your previous response violated the schema. "
                "direction must be positive, negative, or neutral; "
                "strength must be a number between 0 and 1."
            )

        return (
            "Your previous response was empty. "
            "Return only the required JSON object."
        )

    @staticmethod
    def _evidence_text(
        evidence: Evidence,
    ) -> str:
        """Build bounded semantic evidence context."""

        parts = [
            part.strip()
            for part in (
                evidence.source_title,
                evidence.snippet,
                evidence.content,
            )
            if isinstance(part, str)
            and part.strip()
        ]

        text = "\n".join(parts)

        # Prevent unexpectedly huge pages from becoming a semantic prompt.
        return text[:6000]
