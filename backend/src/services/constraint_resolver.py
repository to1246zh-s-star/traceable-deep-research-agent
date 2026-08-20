"""Semantic resolution of hard decision constraints from evidence."""

from __future__ import annotations

import json
import logging
from typing import Any

from hello_agents import ToolAwareSimpleAgent

from config import Configuration
from models import (
    DecisionCase,
    Evidence,
    SummaryState,
)
from utils import strip_thinking_tokens

logger = logging.getLogger(__name__)


CONSTRAINT_PROMPT = """
You are a conservative technical constraint evaluator.

Determine whether the supplied evidence establishes that one candidate
satisfies or violates one hard decision constraint.

Candidate:
{candidate}

Constraint:
{constraint}

Evidence:
{evidence}

Return ONLY valid JSON:

{{
  "status": "satisfied",
  "strength": 0.0,
  "rationale": "brief evidence-grounded explanation"
}}

Allowed status values:

- "satisfied":
  the evidence clearly establishes that the candidate satisfies
  the hard constraint.

- "violated":
  the evidence clearly establishes that the candidate does not satisfy
  the hard constraint.

- "unknown":
  the evidence is insufficient, ambiguous, indirect, or irrelevant.

Rules:

1. Use only the supplied evidence.
2. Never infer missing facts.
3. Absence of evidence is NOT evidence of violation.
4. If uncertain, return "unknown".
5. strength must be between 0 and 1.
6. Do not evaluate source trustworthiness.
7. Return no markdown and no text outside the JSON object.
""".strip()


class ConstraintResolver:
    """Resolve candidate hard constraints conservatively from evidence."""

    VALID_STATUSES = {
        "satisfied",
        "violated",
        "unknown",
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

    def resolve(
        self,
        state: SummaryState,
        decision: DecisionCase,
    ) -> dict[str, dict[str, bool]]:
        """
        Resolve supported candidate × constraint pairs.

        Unknown pairs are intentionally omitted so the existing decision
        evaluator preserves them as unresolved.
        """

        results: dict[str, dict[str, bool]] = {}

        if not decision.constraints:
            return results

        for candidate in decision.candidates:
            candidate_evidence = self._candidate_evidence(
                state,
                candidate.name,
            )

            if not candidate_evidence:
                continue

            for constraint in decision.constraints:
                resolution = self._resolve_pair(
                    candidate_name=candidate.name,
                    constraint_text=constraint.text,
                    evidence=candidate_evidence,
                )

                if resolution is None:
                    continue

                status = resolution["status"]

                if status == "unknown":
                    continue

                results.setdefault(
                    candidate.candidate_id,
                    {},
                )[constraint.constraint_id] = (
                    status == "satisfied"
                )

        return results

    def _resolve_pair(
        self,
        *,
        candidate_name: str,
        constraint_text: str,
        evidence: str,
    ) -> dict[str, Any] | None:
        """Resolve one candidate × constraint pair with one retry."""

        self.retry_count = 0
        self.last_parse_status = "unknown"

        prompt = CONSTRAINT_PROMPT.format(
            candidate=candidate_name,
            constraint=constraint_text,
            evidence=evidence,
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
        response = self._agent.run(prompt)
        self._agent.clear_history()

        logger.info(
            "Constraint resolver output (truncated): %s",
            response[:500],
        )

        return self._extract_payload(response)

    def _extract_payload(
        self,
        raw_response: str,
    ) -> dict[str, Any] | None:
        text = (raw_response or "").strip()

        if not text:
            self.last_parse_status = "empty_output"
            return None

        if self._config.strip_thinking_tokens:
            text = strip_thinking_tokens(text)

        start = text.find("{")
        end = text.rfind("}")

        if start == -1 or end == -1 or end <= start:
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
            "status": payload["status"],
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
        if not isinstance(payload, dict):
            return False

        status = payload.get("status")
        strength = payload.get("strength")
        rationale = payload.get("rationale")

        if status not in self.VALID_STATUSES:
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
    def _candidate_evidence(
        state: SummaryState,
        candidate_name: str,
    ) -> str:
        """
        Build conservative evidence context for one candidate.

        Only evidence explicitly mentioning the candidate is included.
        """

        candidate_key = candidate_name.casefold()
        chunks: list[str] = []

        for evidence in state.evidence_items:
            text = "\n".join(
                part.strip()
                for part in (
                    evidence.source_title,
                    evidence.snippet,
                    evidence.content,
                )
                if isinstance(part, str)
                and part.strip()
            )

            if not text:
                continue

            if candidate_key not in text.casefold():
                continue

            chunks.append(text)

        return "\n\n".join(chunks)[:12000]

    @staticmethod
    def _repair_instruction(
        failure_status: str,
    ) -> str:
        if failure_status == "json_error":
            return (
                "Return only one syntactically valid JSON object."
            )

        if failure_status == "invalid_schema":
            return (
                "status must be satisfied, violated, or unknown; "
                "strength must be between 0 and 1."
            )

        return (
            "Return only the required JSON object."
        )
