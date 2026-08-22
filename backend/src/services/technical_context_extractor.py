"""Reliable LLM extraction of architecture-aware technical context."""

from __future__ import annotations

import json
import logging
from typing import Any

from hello_agents import ToolAwareSimpleAgent

from config import Configuration
from models import DecisionCase, TechnicalContext
from utils import strip_thinking_tokens

logger = logging.getLogger(__name__)


TECHNICAL_CONTEXT_PROMPT = """
You are a conservative technical-context extractor.

Extract only technical environment, architecture, operational, team,
migration, security, compliance, scale, performance, reliability, and
budget information that is explicitly stated or strongly implied by the
user's research topic and structured decision case.

Do NOT evaluate candidates.
Do NOT recommend an option.
Do NOT invent missing infrastructure or requirements.

Research topic:
{research_topic}

Decision question:
{decision_question}

Decision context:
{decision_context}

Requirements:
{requirements}

Constraints:
{constraints}

Return ONLY valid JSON using exactly this structure:

{{
  "existing_stack": [],
  "deployment_environment": [],
  "infrastructure": [],
  "team_capabilities": [],
  "scale_requirements": [],
  "performance_requirements": [],
  "reliability_requirements": [],
  "integration_requirements": [],
  "operational_constraints": [],
  "security_constraints": [],
  "compliance_constraints": [],
  "migration_constraints": [],
  "budget_constraints": []
}}

Rules:

1. Every field must be an array of strings.
2. Use an empty array when the information is unknown.
3. Do not infer an implementation stack merely because a candidate uses it.
4. Do not convert candidate characteristics into user context.
5. Do not invent numeric scale, latency, reliability, or budget targets.
6. Hard decision constraints may be reflected in the appropriate context field.
7. Preserve the meaning of the user's wording.
8. Return no markdown, commentary, reasoning, or text outside the JSON object.
""".strip()


CONTEXT_FIELDS = (
    "existing_stack",
    "deployment_environment",
    "infrastructure",
    "team_capabilities",
    "scale_requirements",
    "performance_requirements",
    "reliability_requirements",
    "integration_requirements",
    "operational_constraints",
    "security_constraints",
    "compliance_constraints",
    "migration_constraints",
    "budget_constraints",
)


class TechnicalContextExtractor:
    """Extract structured TechnicalContext with conservative JSON semantics."""

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

        # Cumulative actual provider calls.
        # Retries count; reuse/no-op does not.
        self.llm_call_count = 0

    def extract(
        self,
        research_topic: str,
        decision: DecisionCase,
    ) -> TechnicalContext | None:
        """Extract context once; malformed or failed output returns None."""

        self.retry_count = 0
        self.last_parse_status = "unknown"

        prompt = TECHNICAL_CONTEXT_PROMPT.format(
            research_topic=research_topic,
            decision_question=decision.question,
            decision_context=decision.context or "",
            requirements=json.dumps(
                [
                    requirement.text
                    for requirement in decision.requirements
                ],
                ensure_ascii=False,
            ),
            constraints=json.dumps(
                [
                    constraint.text
                    for constraint in decision.constraints
                ],
                ensure_ascii=False,
            ),
        )

        payload = self._run_and_parse(prompt)

        if (
            payload is None
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

            payload = self._run_and_parse(
                retry_prompt
            )

        if payload is None:
            return None

        return TechnicalContext(
            **payload
        )

    def _run_and_parse(
        self,
        prompt: str,
    ) -> dict[str, list[str]] | None:
        self.llm_call_count += 1

        response = self._agent.run(prompt)
        self._agent.clear_history()

        logger.info(
            "Technical context extractor output "
            "(truncated): %s",
            response[:500],
        )

        return self._extract_payload(response)

    def _extract_payload(
        self,
        raw_response: str,
    ) -> dict[str, list[str]] | None:
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
            payload
        )

        if validated is None:
            self.last_parse_status = (
                "invalid_schema"
            )
            return None

        self.last_parse_status = "success"
        return validated

    @staticmethod
    def _validate_payload(
        payload: Any,
    ) -> dict[str, list[str]] | None:
        if not isinstance(payload, dict):
            return None

        if set(payload) != set(
            CONTEXT_FIELDS
        ):
            return None

        validated: dict[
            str,
            list[str],
        ] = {}

        for field_name in CONTEXT_FIELDS:
            raw_values = payload.get(
                field_name
            )

            if not isinstance(
                raw_values,
                list,
            ):
                return None

            normalized: list[str] = []
            seen: set[str] = set()

            for item in raw_values:
                if not isinstance(
                    item,
                    str,
                ):
                    return None

                value = item.strip()

                if not value:
                    continue

                key = value.casefold()

                if key in seen:
                    continue

                seen.add(key)
                normalized.append(value)

            validated[field_name] = (
                normalized
            )

        return validated

    @staticmethod
    def _repair_instruction(
        failure_status: str,
    ) -> str:
        if failure_status == "json_error":
            return (
                "Return only one syntactically "
                "valid JSON object."
            )

        if (
            failure_status
            == "invalid_schema"
        ):
            return (
                "Return exactly the required "
                "13 keys. Every value must be "
                "an array of strings. Use [] "
                "when information is unknown."
            )

        return (
            "Return only the required "
            "JSON object."
        )
