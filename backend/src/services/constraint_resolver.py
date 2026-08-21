"""Semantic resolution of hard decision constraints from evidence."""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

from hello_agents import ToolAwareSimpleAgent

from config import Configuration
from models import DecisionCase, SummaryState
from utils import strip_thinking_tokens

logger = logging.getLogger(__name__)


CONSTRAINT_PROMPT = """
You are a conservative technical constraint evaluator.

Determine whether the supplied evidence establishes that one candidate
satisfies or violates each supplied hard decision constraint.

Candidate:
{candidate}

Constraints:
{constraints}

Evidence:
{evidence}

Return ONLY valid JSON in this exact structure:

{{
  "results": [
    {{
      "constraint_id": "constraint id",
      "status": "satisfied",
      "strength": 0.0,
      "rationale": "brief evidence-grounded explanation"
    }}
  ]
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
7. Return one result for each supplied constraint when possible.
8. Preserve the supplied constraint_id exactly.
9. Do not invent constraint IDs.
10. Return no markdown and no text outside the JSON object.
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

        # Cumulative actual provider invocations for observability.
        # Cache hits do not increment this counter; retries do.
        self.llm_call_count = 0

        # Runtime-only cache for repeated adaptive decision passes.
        #
        # The cache intentionally lives on the resolver instance rather than
        # SummaryState persistence. It reduces duplicate LLM calls within one
        # research workflow without introducing persisted cache invalidation
        # semantics.
        self._candidate_cache: dict[
            tuple[str, str],
            tuple[str, dict[str, bool]],
        ] = {}

    def resolve(
        self,
        state: SummaryState,
        decision: DecisionCase,
    ) -> dict[str, dict[str, bool]]:
        """
        Resolve candidate × constraint results using one LLM call per
        candidate rather than one call per candidate × constraint pair.

        Unknown, missing, malformed, or failed judgments are intentionally
        omitted so the deterministic evaluator preserves them as unresolved.
        """

        results: dict[str, dict[str, bool]] = {}

        if not decision.constraints:
            return results

        constraints = [
            {
                "constraint_id": constraint.constraint_id,
                "text": constraint.text,
            }
            for constraint in decision.constraints
        ]

        for candidate in decision.candidates:
            candidate_evidence = self._candidate_evidence(
                state,
                candidate.name,
            )

            cache_key = (
                decision.decision_id,
                candidate.candidate_id,
            )

            if not candidate_evidence:
                # Never allow stale cached judgments to leak into a state
                # where the candidate no longer has relevant evidence.
                self._candidate_cache.pop(
                    cache_key,
                    None,
                )
                continue

            fingerprint = self._candidate_fingerprint(
                candidate_name=candidate.name,
                constraints=constraints,
                evidence=candidate_evidence,
            )

            cached = self._candidate_cache.get(
                cache_key
            )

            if (
                cached is not None
                and cached[0] == fingerprint
            ):
                candidate_results = dict(
                    cached[1]
                )
            else:
                resolutions = (
                    self._resolve_candidate_constraints(
                        candidate_name=candidate.name,
                        constraints=constraints,
                        evidence=candidate_evidence,
                    )
                )

                candidate_results: dict[
                    str,
                    bool,
                ] = {}

                for resolution in resolutions:
                    status = resolution["status"]

                    if status == "unknown":
                        continue

                    candidate_results[
                        resolution["constraint_id"]
                    ] = (
                        status == "satisfied"
                    )

                # Cache only a successfully parsed LLM response.
                #
                # A successful response may contain unknown judgments; those
                # are intentionally represented by omission and are safe to
                # reuse until the evidence or constraints change.
                #
                # Failed / malformed output must never be cached so a later
                # adaptive pass can retry it.
                if self.last_parse_status == "success":
                    self._candidate_cache[
                        cache_key
                    ] = (
                        fingerprint,
                        dict(candidate_results),
                    )

            if candidate_results:
                results[
                    candidate.candidate_id
                ] = candidate_results

        return results

    def _resolve_candidate_constraints(
        self,
        *,
        candidate_name: str,
        constraints: list[dict[str, str]],
        evidence: str,
    ) -> list[dict[str, Any]]:
        """Resolve all hard constraints for one candidate with one retry."""

        self.retry_count = 0
        self.last_parse_status = "unknown"

        allowed_constraint_ids = {
            item["constraint_id"]
            for item in constraints
        }

        prompt = CONSTRAINT_PROMPT.format(
            candidate=candidate_name,
            constraints=json.dumps(
                constraints,
                ensure_ascii=False,
                indent=2,
            ),
            evidence=evidence,
        )

        result = self._run_and_parse(
            prompt,
            allowed_constraint_ids=allowed_constraint_ids,
        )

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
                retry_prompt,
                allowed_constraint_ids=allowed_constraint_ids,
            )

        # Fail closed: unresolved constraints are represented by omission.
        return result or []

    def _run_and_parse(
        self,
        prompt: str,
        *,
        allowed_constraint_ids: set[str],
    ) -> list[dict[str, Any]] | None:
        self.llm_call_count += 1
        response = self._agent.run(prompt)
        self._agent.clear_history()

        logger.info(
            "Constraint resolver output (truncated): %s",
            response[:500],
        )

        return self._extract_payload(
            response,
            allowed_constraint_ids=allowed_constraint_ids,
        )

    def _extract_payload(
        self,
        raw_response: str,
        *,
        allowed_constraint_ids: set[str],
    ) -> list[dict[str, Any]] | None:
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

        validated = self._validate_payload(
            payload,
            allowed_constraint_ids=allowed_constraint_ids,
        )

        if validated is None:
            self.last_parse_status = "invalid_schema"
            return None

        self.last_parse_status = "success"
        return validated

    def _validate_payload(
        self,
        payload: Any,
        *,
        allowed_constraint_ids: set[str],
    ) -> list[dict[str, Any]] | None:
        if not isinstance(payload, dict):
            return None

        raw_results = payload.get("results")

        if not isinstance(raw_results, list):
            return None

        validated: list[dict[str, Any]] = []
        seen_ids: set[str] = set()

        for item in raw_results:
            if not isinstance(item, dict):
                return None

            constraint_id = item.get("constraint_id")
            status = item.get("status")
            strength = item.get("strength")
            rationale = item.get("rationale")

            if (
                not isinstance(constraint_id, str)
                or constraint_id not in allowed_constraint_ids
                or constraint_id in seen_ids
            ):
                return None

            if status not in self.VALID_STATUSES:
                return None

            if isinstance(strength, bool):
                return None

            if not isinstance(
                strength,
                (int, float),
            ):
                return None

            if not 0.0 <= float(strength) <= 1.0:
                return None

            if (
                rationale is not None
                and not isinstance(rationale, str)
            ):
                return None

            seen_ids.add(constraint_id)

            validated.append(
                {
                    "constraint_id": constraint_id,
                    "status": status,
                    "strength": float(strength),
                    "rationale": (
                        rationale or ""
                    ).strip(),
                }
            )

        return validated

    @staticmethod
    def _candidate_fingerprint(
        *,
        candidate_name: str,
        constraints: list[dict[str, str]],
        evidence: str,
    ) -> str:
        """
        Fingerprint exactly the semantic inputs used for one candidate.

        Any change to candidate identity, hard constraints, or the evidence
        context invalidates the cached constraint result.
        """

        payload = json.dumps(
            {
                "candidate_name": candidate_name,
                "constraints": constraints,
                "evidence": evidence,
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )

        return hashlib.sha256(
            payload.encode("utf-8")
        ).hexdigest()

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
                "Return only one syntactically valid JSON object "
                'with a "results" array.'
            )

        if failure_status == "invalid_schema":
            return (
                'Return {"results": [...]} only. Each result must use '
                "one supplied constraint_id exactly; status must be "
                "satisfied, violated, or unknown; strength must be "
                "between 0 and 1."
            )

        return (
            "Return only the required JSON object."
        )
