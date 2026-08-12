"""Reliable LLM extraction of a technical DecisionCase."""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

from hello_agents import ToolAwareSimpleAgent

from config import Configuration
from models import (
    Candidate,
    Constraint,
    DecisionCase,
    DecisionCriterion,
    Requirement,
)
from utils import strip_thinking_tokens

logger = logging.getLogger(__name__)


DECISION_CASE_PROMPT = """
You are a technical decision-analysis extractor.

Your job is to inspect the user's research topic and determine whether it
contains a real technical decision that can be compared using candidates,
requirements, constraints, and criteria.

Research topic:
{research_topic}

Return ONLY valid JSON using exactly this structure:

{{
  "is_decision": true,
  "question": "The decision question",
  "context": "Optional decision context",
  "candidates": [
    {{
      "name": "Candidate name",
      "description": "Optional description"
    }}
  ],
  "requirements": [
    {{
      "text": "User requirement"
    }}
  ],
  "constraints": [
    {{
      "text": "Hard requirement that a candidate must satisfy"
    }}
  ],
  "criteria": [
    {{
      "name": "Comparison criterion",
      "weight": 1.0,
      "description": "Optional description"
    }}
  ]
}}

Rules:

1. Set "is_decision" to true only when the topic actually asks for a choice,
   recommendation, tradeoff, selection, or comparison between technical
   alternatives.

2. If the topic is informational rather than decisional, return:

   {{
     "is_decision": false,
     "question": "",
     "context": null,
     "candidates": [],
     "requirements": [],
     "constraints": [],
     "criteria": []
   }}

3. Do not invent candidates that are not stated or strongly implied by the
   research topic.

4. Do not invent hard constraints. A constraint is something a candidate must
   satisfy, not merely something the user prefers.

5. Requirements and criteria may only reflect information present in the
   research topic.

6. Criterion weights must be positive numbers. Use equal weights when the user
   expresses criteria but gives no relative importance.

7. Do not include markdown, commentary, reasoning, or text outside the JSON.
""".strip()


class DecisionCaseExtractor:
    """Extract a DecisionCase using Planner-style JSON reliability rules."""

    def __init__(
        self,
        extraction_agent: ToolAwareSimpleAgent,
        config: Configuration,
    ) -> None:
        self._agent = extraction_agent
        self._config = config

        self.last_parse_status = "unknown"
        self.retry_count = 0
        self.max_retries = 1
        self.retry_reason: str | None = None
        self.final_parse_status = "unknown"

        self.stats = {
            "calls": 0,
            "retry_count": 0,
            "failures": 0,
            "retry_reason": None,
            "final_status": "unknown",
        }

    def extract(self, research_topic: str) -> Optional[DecisionCase]:
        """Extract one DecisionCase, or None for a non-decision topic."""

        self._reset_call_state()

        prompt = DECISION_CASE_PROMPT.format(
            research_topic=research_topic,
        )

        payload = self._run_and_parse(prompt)

        if self._should_retry():
            self.retry_count += 1
            self.stats["retry_count"] += 1
            self.retry_reason = self.last_parse_status
            self.stats["retry_reason"] = self.retry_reason

            retry_prompt = self._build_retry_prompt(
                prompt,
                self.last_parse_status,
            )

            payload = self._run_and_parse(retry_prompt)

        if payload is None:
            if self.last_parse_status == "non_decision":
                self.final_parse_status = "non_decision"
                self.stats["final_status"] = "non_decision"
                return None

            self.final_parse_status = (
                "retry_failed"
                if self.retry_count > 0
                else self.last_parse_status
            )
            self.stats["final_status"] = self.final_parse_status

            if self.final_parse_status == "retry_failed":
                self.stats["failures"] += 1

            return None

        decision = self._build_decision_case(payload)

        if decision is None:
            self.final_parse_status = (
                "retry_failed"
                if self.retry_count > 0
                else self.last_parse_status
            )
            self.stats["final_status"] = self.final_parse_status

            if self.final_parse_status == "retry_failed":
                self.stats["failures"] += 1

            return None

        self.final_parse_status = "success"
        self.stats["final_status"] = "success"

        return decision

    def _reset_call_state(self) -> None:
        """Reset per-extraction reliability state."""

        self.last_parse_status = "unknown"
        self.retry_count = 0
        self.retry_reason = None
        self.final_parse_status = "unknown"

        self.stats = {
            "calls": 0,
            "retry_count": 0,
            "failures": 0,
            "retry_reason": None,
            "final_status": "unknown",
        }

    def _run_and_parse(
        self,
        prompt: str,
    ) -> Optional[dict[str, Any]]:
        """Run the extraction agent once and parse its JSON response."""

        self.stats["calls"] += 1

        response = self._agent.run(prompt)
        self._agent.clear_history()

        logger.info(
            "Decision extractor raw output (truncated): %s",
            response[:500],
        )

        return self._extract_payload(response)

    def _should_retry(self) -> bool:
        """Return whether the current parse failure is retryable."""

        return (
            self.last_parse_status
            in {
                "empty_output",
                "json_error",
                "invalid_schema",
            }
            and self.retry_count < self.max_retries
        )

    @staticmethod
    def _build_retry_prompt(
        prompt: str,
        failure_status: str,
    ) -> str:
        """Build a targeted Planner-style JSON repair prompt."""

        if failure_status == "json_error":
            repair = (
                "Your previous response was not valid JSON. "
                "Return only syntactically valid JSON. "
                "Do not include markdown or explanations."
            )
        elif failure_status == "invalid_schema":
            repair = (
                "Your previous response violated the required schema. "
                "Preserve the exact required JSON keys and value types. "
                "Do not invent missing decision information."
            )
        else:
            repair = (
                "Your previous response was empty. "
                "Return only the required JSON object."
            )

        return f"{prompt}\n\nREPAIR INSTRUCTION:\n{repair}"

    def _extract_payload(
        self,
        raw_response: str,
    ) -> Optional[dict[str, Any]]:
        """Parse and validate the extractor JSON envelope."""

        self.last_parse_status = "unknown"

        text = (raw_response or "").strip()

        if not text:
            self.last_parse_status = "empty_output"
            return None

        if self._config.strip_thinking_tokens:
            text = strip_thinking_tokens(text)

        payload = self._extract_json_object(text)

        if payload is None:
            if self.last_parse_status == "unknown":
                self.last_parse_status = "json_error"
            return None

        if not self._is_valid_payload(payload):
            self.last_parse_status = "invalid_schema"
            return None

        if payload["is_decision"] is False:
            self.last_parse_status = "non_decision"
            return None

        self.last_parse_status = "success"
        return payload

    def _extract_json_object(
        self,
        text: str,
    ) -> Optional[dict[str, Any]]:
        """Locate and decode the outermost JSON object."""

        start = text.find("{")
        end = text.rfind("}")

        if start == -1 or end == -1 or end <= start:
            self.last_parse_status = "json_error"
            return None

        candidate = text[start : end + 1]

        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError:
            self.last_parse_status = "json_error"
            return None

        if not isinstance(payload, dict):
            self.last_parse_status = "invalid_schema"
            return None

        return payload

    def _is_valid_payload(
        self,
        payload: dict[str, Any],
    ) -> bool:
        """Validate the complete decision-extraction schema."""

        required_keys = {
            "is_decision",
            "question",
            "context",
            "candidates",
            "requirements",
            "constraints",
            "criteria",
        }

        if not required_keys.issubset(payload):
            return False

        is_decision = payload.get("is_decision")

        if not isinstance(is_decision, bool):
            return False

        question = payload.get("question")
        context = payload.get("context")
        candidates = payload.get("candidates")
        requirements = payload.get("requirements")
        constraints = payload.get("constraints")
        criteria = payload.get("criteria")

        if not isinstance(question, str):
            return False

        if context is not None and not isinstance(context, str):
            return False

        if not isinstance(candidates, list):
            return False

        if not isinstance(requirements, list):
            return False

        if not isinstance(constraints, list):
            return False

        if not isinstance(criteria, list):
            return False

        if not is_decision:
            return True

        if not question.strip():
            return False

        if len(candidates) < 2:
            return False

        candidate_names: set[str] = set()

        for candidate in candidates:
            if not isinstance(candidate, dict):
                return False

            name = candidate.get("name")
            description = candidate.get("description")

            if not isinstance(name, str) or not name.strip():
                return False

            if (
                description is not None
                and not isinstance(description, str)
            ):
                return False

            normalized_name = name.strip().casefold()

            if normalized_name in candidate_names:
                return False

            candidate_names.add(normalized_name)

        for requirement in requirements:
            if not self._is_valid_text_item(requirement):
                return False

        for constraint in constraints:
            if not self._is_valid_text_item(constraint):
                return False

        criterion_names: set[str] = set()

        for criterion in criteria:
            if not isinstance(criterion, dict):
                return False

            name = criterion.get("name")
            weight = criterion.get("weight")
            description = criterion.get("description")

            if not isinstance(name, str) or not name.strip():
                return False

            if isinstance(weight, bool):
                return False

            if not isinstance(weight, (int, float)):
                return False

            if float(weight) <= 0:
                return False

            if (
                description is not None
                and not isinstance(description, str)
            ):
                return False

            normalized_name = name.strip().casefold()

            if normalized_name in criterion_names:
                return False

            criterion_names.add(normalized_name)

        return True

    @staticmethod
    def _is_valid_text_item(
        item: Any,
    ) -> bool:
        """Validate an object containing one non-empty text field."""

        if not isinstance(item, dict):
            return False

        text = item.get("text")

        return isinstance(text, str) and bool(text.strip())

    def _build_decision_case(
        self,
        payload: dict[str, Any],
    ) -> Optional[DecisionCase]:
        """Convert validated JSON into V3 decision dataclasses."""

        if payload.get("is_decision") is not True:
            self.last_parse_status = "non_decision"
            return None

        candidates = [
            Candidate(
                name=item["name"].strip(),
                description=self._optional_text(
                    item.get("description")
                ),
            )
            for item in payload["candidates"]
        ]

        requirements = [
            Requirement(
                text=item["text"].strip(),
            )
            for item in payload["requirements"]
        ]

        constraints = [
            Constraint(
                text=item["text"].strip(),
                source="user",
            )
            for item in payload["constraints"]
        ]

        criteria = [
            DecisionCriterion(
                name=item["name"].strip(),
                weight=float(item["weight"]),
                source="user",
                description=self._optional_text(
                    item.get("description")
                ),
            )
            for item in payload["criteria"]
        ]

        return DecisionCase(
            question=payload["question"].strip(),
            context=self._optional_text(
                payload.get("context")
            ),
            candidates=candidates,
            requirements=requirements,
            constraints=constraints,
            criteria=criteria,
            status="draft",
        )

    @staticmethod
    def _optional_text(value: Any) -> str | None:
        """Normalize optional user-visible text."""

        if not isinstance(value, str):
            return None

        value = value.strip()

        return value or None
