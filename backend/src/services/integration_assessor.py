"""Architecture-aware semantic integration assessment for decision candidates."""

from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
import logging
from typing import Any

from hello_agents import ToolAwareSimpleAgent

from config import Configuration
from models import (
    DecisionCase,
    IntegrationAssessment,
    SummaryState,
    TechnicalContext,
)
from utils import strip_thinking_tokens

logger = logging.getLogger(__name__)


VALID_LEVELS = {
    "LOW",
    "MEDIUM",
    "HIGH",
    "UNKNOWN",
}


INTEGRATION_ASSESSMENT_PROMPT = """
You are a conservative software-architecture integration assessor.

Evaluate how each supplied candidate fits the user's CURRENT technical
environment.

Use ONLY:
1. the supplied TechnicalContext;
2. the supplied candidate information;
3. the supplied evidence for that candidate.

Do not recommend a winner.
Do not produce numeric scores.
Do not evaluate general product quality.
Do not infer missing infrastructure, skills, dependencies, or migration work.

TechnicalContext:
{technical_context}

Candidates and evidence:
{candidate_inputs}

Return ONLY valid JSON using exactly this structure:

{{
  "results": [
    {{
      "candidate_id": "candidate id",
      "integration_complexity": "LOW",
      "migration_complexity": "MEDIUM",
      "operational_change": "HIGH",
      "infrastructure_change": "UNKNOWN",
      "required_new_dependencies": [],
      "affected_components": [],
      "team_skill_gaps": [],
      "evidence_ids": [],
      "rationale": "brief evidence-grounded explanation"
    }}
  ]
}}

Allowed complexity/change values:
- LOW
- MEDIUM
- HIGH
- UNKNOWN

Rules:

1. Return exactly one result for each supplied candidate.
2. Preserve candidate_id exactly.
3. UNKNOWN means evidence/context is insufficient to make the judgment.
4. Absence of evidence must NEVER become LOW.
5. Do not invent dependencies, affected components, or team skills.
6. evidence_ids may contain only supplied evidence IDs for that candidate.
7. If a dimension cannot be established, return UNKNOWN.
8. A candidate being powerful or popular does not imply architecture fit.
9. Do not output candidate scores or rankings.
10. Return no markdown or text outside the JSON object.
""".strip()


class IntegrationAssessor:
    """Assess candidate × architecture fit with bounded semantic inference."""

    def __init__(
        self,
        extraction_agent: ToolAwareSimpleAgent,
        config: Configuration,
    ) -> None:
        self._agent = extraction_agent
        self._config = config

        self.max_retries = 1
        self.retry_count = 0
        self.last_parse_status = "unknown"

        # Actual provider invocations. Retries count; cache hits do not.
        self.llm_call_count = 0

        # Runtime-only candidate cache:
        # (decision_id, candidate_id) -> (fingerprint, assessment)
        self._candidate_cache: dict[
            tuple[str, str],
            tuple[str, IntegrationAssessment],
        ] = {}

    def assess(
        self,
        state: SummaryState,
        decision: DecisionCase,
        technical_context: TechnicalContext | None,
    ) -> list[IntegrationAssessment]:
        """
        Assess all candidates.

        Cached candidate results are reused only while candidate identity,
        TechnicalContext, and candidate-specific evidence remain unchanged.
        """

        if (
            technical_context is None
            or not self._context_has_information(
                technical_context
            )
        ):
            return [
                self._unknown_assessment(
                    decision.decision_id,
                    candidate.candidate_id,
                )
                for candidate in decision.candidates
            ]

        resolved: dict[
            str,
            IntegrationAssessment,
        ] = {}

        pending_inputs: list[
            dict[str, Any]
        ] = []

        pending_fingerprints: dict[
            str,
            str,
        ] = {}

        allowed_evidence_ids: dict[
            str,
            set[str],
        ] = {}

        for candidate in decision.candidates:
            evidence = self._candidate_evidence(
                state,
                candidate.name,
            )

            cache_key = (
                decision.decision_id,
                candidate.candidate_id,
            )

            if not evidence:
                # Never let an old grounded assessment survive after
                # candidate-specific evidence disappears.
                self._candidate_cache.pop(
                    cache_key,
                    None,
                )

                resolved[
                    candidate.candidate_id
                ] = self._unknown_assessment(
                    decision.decision_id,
                    candidate.candidate_id,
                )
                continue

            candidate_input = {
                "candidate_id":
                    candidate.candidate_id,
                "name":
                    candidate.name,
                "description":
                    candidate.description,
                "evidence":
                    evidence,
            }

            fingerprint = (
                self._candidate_fingerprint(
                    candidate_input=
                        candidate_input,
                    technical_context=
                        technical_context,
                )
            )

            cached = self._candidate_cache.get(
                cache_key
            )

            if (
                cached is not None
                and cached[0] == fingerprint
            ):
                resolved[
                    candidate.candidate_id
                ] = cached[1]
                continue

            pending_inputs.append(
                candidate_input
            )

            pending_fingerprints[
                candidate.candidate_id
            ] = fingerprint

            allowed_evidence_ids[
                candidate.candidate_id
            ] = {
                item["evidence_id"]
                for item in evidence
            }

        if pending_inputs:
            assessed = self._assess_batch(
                technical_context=
                    technical_context,
                candidate_inputs=pending_inputs,
                allowed_evidence_ids=
                    allowed_evidence_ids,
            )

            if assessed is not None:
                for assessment in assessed:
                    assessment.decision_id = (
                        decision.decision_id
                    )

                    candidate_id = (
                        assessment.candidate_id
                    )

                    resolved[
                        candidate_id
                    ] = assessment

                    self._candidate_cache[
                        (
                            decision.decision_id,
                            candidate_id,
                        )
                    ] = (
                        pending_fingerprints[
                            candidate_id
                        ],
                        assessment,
                    )
            else:
                # Failed semantic inference is represented conservatively.
                # Do not cache this fallback: a later adaptive pass must retry.
                for item in pending_inputs:
                    candidate_id = (
                        item["candidate_id"]
                    )

                    resolved[
                        candidate_id
                    ] = (
                        self._unknown_assessment(
                            decision.decision_id,
                            candidate_id,
                        )
                    )

        return [
            resolved.get(
                candidate.candidate_id,
                self._unknown_assessment(
                    decision.decision_id,
                    candidate.candidate_id,
                ),
            )
            for candidate in decision.candidates
        ]

    def _assess_batch(
        self,
        *,
        technical_context: TechnicalContext,
        candidate_inputs: list[
            dict[str, Any]
        ],
        allowed_evidence_ids: dict[
            str,
            set[str],
        ],
    ) -> list[
        IntegrationAssessment
    ] | None:
        """Assess all currently uncached candidates in one semantic call."""

        self.retry_count = 0
        self.last_parse_status = "unknown"

        allowed_candidate_ids = {
            item["candidate_id"]
            for item in candidate_inputs
        }

        prompt = (
            INTEGRATION_ASSESSMENT_PROMPT.format(
                technical_context=json.dumps(
                    asdict(
                        technical_context
                    ),
                    ensure_ascii=False,
                    indent=2,
                ),
                candidate_inputs=json.dumps(
                    candidate_inputs,
                    ensure_ascii=False,
                    indent=2,
                ),
            )
        )

        result = self._run_and_parse(
            prompt,
            allowed_candidate_ids=
                allowed_candidate_ids,
            allowed_evidence_ids=
                allowed_evidence_ids,
        )

        if (
            result is None
            and self.last_parse_status
            in {
                "empty_output",
                "json_error",
                "invalid_schema",
            }
            and self.retry_count
            < self.max_retries
        ):
            failure_status = (
                self.last_parse_status
            )
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
                allowed_candidate_ids=
                    allowed_candidate_ids,
                allowed_evidence_ids=
                    allowed_evidence_ids,
            )

        return result

    def _run_and_parse(
        self,
        prompt: str,
        *,
        allowed_candidate_ids: set[str],
        allowed_evidence_ids: dict[
            str,
            set[str],
        ],
    ) -> list[
        IntegrationAssessment
    ] | None:
        self.llm_call_count += 1

        response = self._agent.run(prompt)
        self._agent.clear_history()

        logger.info(
            "Integration assessor output "
            "(truncated): %s",
            response[:500],
        )

        return self._extract_payload(
            response,
            allowed_candidate_ids=
                allowed_candidate_ids,
            allowed_evidence_ids=
                allowed_evidence_ids,
        )

    def _extract_payload(
        self,
        raw_response: str,
        *,
        allowed_candidate_ids: set[str],
        allowed_evidence_ids: dict[
            str,
            set[str],
        ],
    ) -> list[
        IntegrationAssessment
    ] | None:
        text = (raw_response or "").strip()

        if not text:
            self.last_parse_status = (
                "empty_output"
            )
            return None

        if self._config.strip_thinking_tokens:
            text = strip_thinking_tokens(
                text
            )

        start = text.find("{")
        end = text.rfind("}")

        if (
            start == -1
            or end == -1
            or end <= start
        ):
            self.last_parse_status = (
                "json_error"
            )
            return None

        try:
            payload = json.loads(
                text[start : end + 1]
            )
        except json.JSONDecodeError:
            self.last_parse_status = (
                "json_error"
            )
            return None

        validated = self._validate_payload(
            payload,
            allowed_candidate_ids=
                allowed_candidate_ids,
            allowed_evidence_ids=
                allowed_evidence_ids,
        )

        if validated is None:
            self.last_parse_status = (
                "invalid_schema"
            )
            return None

        self.last_parse_status = "success"
        return validated

    @classmethod
    def _validate_payload(
        cls,
        payload: Any,
        *,
        allowed_candidate_ids: set[str],
        allowed_evidence_ids: dict[
            str,
            set[str],
        ],
    ) -> list[
        IntegrationAssessment
    ] | None:
        if not isinstance(payload, dict):
            return None

        raw_results = payload.get("results")

        if not isinstance(
            raw_results,
            list,
        ):
            return None

        if len(raw_results) != len(
            allowed_candidate_ids
        ):
            return None

        validated: list[
            IntegrationAssessment
        ] = []

        seen_candidate_ids: set[str] = set()

        for item in raw_results:
            if not isinstance(item, dict):
                return None

            required_keys = {
                "candidate_id",
                "integration_complexity",
                "migration_complexity",
                "operational_change",
                "infrastructure_change",
                "required_new_dependencies",
                "affected_components",
                "team_skill_gaps",
                "evidence_ids",
                "rationale",
            }

            if not required_keys.issubset(
                item
            ):
                return None

            candidate_id = item.get(
                "candidate_id"
            )

            if (
                not isinstance(
                    candidate_id,
                    str,
                )
                or candidate_id
                not in allowed_candidate_ids
                or candidate_id
                in seen_candidate_ids
            ):
                return None

            dependencies = cls._string_list(
                item.get(
                    "required_new_dependencies"
                )
            )

            components = cls._string_list(
                item.get(
                    "affected_components"
                )
            )

            skill_gaps = cls._string_list(
                item.get(
                    "team_skill_gaps"
                )
            )

            raw_ids = item.get(
                "evidence_ids"
            )

            if (
                dependencies is None
                or components is None
                or skill_gaps is None
                or not isinstance(
                    raw_ids,
                    list,
                )
            ):
                return None

            # Drop hallucinated evidence IDs rather than allowing them
            # to create false grounding.
            valid_ids = (
                allowed_evidence_ids.get(
                    candidate_id,
                    set(),
                )
            )

            evidence_ids: list[str] = []
            seen_ids: set[str] = set()

            for evidence_id in raw_ids:
                if not isinstance(
                    evidence_id,
                    str,
                ):
                    return None

                if evidence_id not in valid_ids:
                    continue

                if evidence_id in seen_ids:
                    continue

                seen_ids.add(evidence_id)
                evidence_ids.append(
                    evidence_id
                )

            rationale = item.get(
                "rationale"
            )

            if (
                rationale is not None
                and not isinstance(
                    rationale,
                    str,
                )
            ):
                return None

            validated.append(
                IntegrationAssessment(
                    decision_id="",
                    candidate_id=candidate_id,
                    integration_complexity=
                        cls._normalize_level(
                            item.get(
                                "integration_complexity"
                            )
                        ),
                    migration_complexity=
                        cls._normalize_level(
                            item.get(
                                "migration_complexity"
                            )
                        ),
                    operational_change=
                        cls._normalize_level(
                            item.get(
                                "operational_change"
                            )
                        ),
                    infrastructure_change=
                        cls._normalize_level(
                            item.get(
                                "infrastructure_change"
                            )
                        ),
                    required_new_dependencies=
                        dependencies,
                    affected_components=
                        components,
                    team_skill_gaps=
                        skill_gaps,
                    evidence_ids=evidence_ids,
                    rationale=(
                        rationale.strip()
                        if isinstance(
                            rationale,
                            str,
                        )
                        and rationale.strip()
                        else None
                    ),
                )
            )

            seen_candidate_ids.add(
                candidate_id
            )

        if (
            seen_candidate_ids
            != allowed_candidate_ids
        ):
            return None

        return validated

    @staticmethod
    def _normalize_level(
        value: Any,
    ) -> str:
        if not isinstance(value, str):
            return "UNKNOWN"

        normalized = value.strip().upper()

        if normalized not in VALID_LEVELS:
            return "UNKNOWN"

        return normalized

    @staticmethod
    def _string_list(
        value: Any,
    ) -> list[str] | None:
        if not isinstance(value, list):
            return None

        result: list[str] = []
        seen: set[str] = set()

        for item in value:
            if not isinstance(item, str):
                return None

            normalized = item.strip()

            if not normalized:
                continue

            key = normalized.casefold()

            if key in seen:
                continue

            seen.add(key)
            result.append(normalized)

        return result

    @staticmethod
    def _context_has_information(
        context: TechnicalContext,
    ) -> bool:
        payload = asdict(context)

        return any(
            bool(value)
            for value in payload.values()
        )

    @staticmethod
    def _candidate_evidence(
        state: SummaryState,
        candidate_name: str,
    ) -> list[dict[str, str]]:
        """
        Return only evidence explicitly mentioning the candidate.

        This preserves conservative grounding and avoids contaminating one
        candidate with another candidate's evidence.
        """

        candidate_key = (
            candidate_name.casefold()
        )

        results: list[
            dict[str, str]
        ] = []

        for evidence in state.evidence_items:
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

            if not text:
                continue

            if (
                candidate_key
                not in text.casefold()
            ):
                continue

            results.append(
                {
                    "evidence_id":
                        evidence.evidence_id,
                    "source_title":
                        evidence.source_title
                        or "",
                    "content":
                        text[:6000],
                }
            )

        return results

    @staticmethod
    def _candidate_fingerprint(
        *,
        candidate_input: dict[
            str,
            Any,
        ],
        technical_context: TechnicalContext,
    ) -> str:
        payload = json.dumps(
            {
                "candidate":
                    candidate_input,
                "technical_context":
                    asdict(
                        technical_context
                    ),
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )

        return hashlib.sha256(
            payload.encode("utf-8")
        ).hexdigest()

    @staticmethod
    def _unknown_assessment(
        decision_id: str,
        candidate_id: str,
    ) -> IntegrationAssessment:
        return IntegrationAssessment(
            decision_id=decision_id,
            candidate_id=candidate_id,
        )

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
                'Return {"results": [...]} only. Return exactly one '
                "result per supplied candidate_id. Complexity/change "
                "values must be LOW, MEDIUM, HIGH, or UNKNOWN."
            )

        return (
            "Return only the required JSON object."
        )
