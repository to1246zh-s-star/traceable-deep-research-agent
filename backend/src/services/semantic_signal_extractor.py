"""Semantic interpretation of evidence signals using batched JSON output."""

from __future__ import annotations

import json
import logging
from collections import defaultdict
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

You are given ONE retrieved evidence item and multiple decision targets.

For each target, determine ONLY how this evidence affects the specified
candidate with respect to the specified criterion.

Evidence:
{evidence}

Targets:
{targets}

Return ONLY valid JSON in this exact structure:

{{
  "results": [
    {{
      "signal_id": "supplied signal id",
      "direction": "positive",
      "strength": 0.0,
      "rationale": "brief evidence-grounded explanation"
    }}
  ]
}}

Allowed direction values:

- "positive":
  evidence supports the candidate on this criterion.

- "negative":
  evidence indicates a disadvantage for the candidate on this criterion.

- "neutral":
  evidence is relevant but does not establish either direction.

Rules:

1. Use only the supplied evidence.
2. Never infer missing facts.
3. If evidence is ambiguous, descriptive, incomplete, or does not
   establish an advantage/disadvantage, use "neutral".
4. strength must be between 0 and 1.
5. Neutral evidence should normally have low strength.
6. Do not evaluate source trustworthiness.
7. Do not evaluate applicability.
8. Preserve every supplied signal_id exactly.
9. Do not invent signal IDs.
10. Return one result for every target when possible.
11. Return no markdown or text outside the JSON object.
""".strip()

MULTI_EVIDENCE_SIGNAL_PROMPT = """
You are a conservative technical evidence interpreter.

You are given MULTIPLE independent retrieved evidence items.
Each evidence item contains its own decision targets.

For every target, determine ONLY how the evidence in the SAME
evidence item affects the specified candidate with respect to
the specified criterion.

Evidence groups:
{evidence_groups}

Return ONLY valid JSON in this exact structure:

{{
  "results": [
    {{
      "signal_id": "supplied signal id",
      "direction": "positive",
      "strength": 0.0,
      "rationale": "brief evidence-grounded explanation"
    }}
  ]
}}

Allowed direction values:

- "positive": evidence supports the candidate on this criterion.
- "negative": evidence indicates a disadvantage for the candidate.
- "neutral": evidence is relevant but does not establish either direction.

Rules:

1. Use only the evidence belonging to the target's evidence group.
2. Never combine facts across different evidence groups.
3. Never infer missing facts.
4. If evidence is ambiguous or incomplete, use "neutral".
5. strength must be between 0 and 1.
6. Neutral evidence should normally have low strength.
7. Do not evaluate source trustworthiness.
8. Do not evaluate applicability.
9. Preserve every supplied signal_id exactly.
10. Do not invent signal IDs.
11. Return one result for every target when possible.
12. Return no markdown or text outside the JSON object.
""".strip()



class SemanticSignalExtractor:
    """
    Convert conservative neutral signal proposals into semantic directions.

    Candidate/criterion relevance is determined upstream.

    Proposals sharing one evidence item are interpreted in one batched
    LLM call to reduce inference requests while preserving the original
    deterministic proposal identities and weights.
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
        *,
        max_evidence_per_batch: int = 4,
    ) -> None:
        if max_evidence_per_batch < 1:
            raise ValueError(
                "max_evidence_per_batch must be at least 1"
            )

        self._agent = extraction_agent
        self._config = config
        self.max_evidence_per_batch = max_evidence_per_batch

        self.max_retries = 1
        self.last_parse_status = "unknown"
        self.retry_count = 0

        # Cumulative actual provider invocations for observability.
        # Retries count because they consume real LLM quota.
        self.llm_call_count = 0

    def extract(
        self,
        state: SummaryState,
        decision: DecisionCase,
        proposals: list[EvidenceSignal],
    ) -> list[EvidenceSignal]:
        """
        Semantically interpret candidate × criterion proposals.

        One LLM call is made per unique evidence_id rather than per
        individual proposal.
        """

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

        grouped: dict[str, list[EvidenceSignal]] = defaultdict(list)

        for proposal in proposals:
            if (
                proposal.evidence_id not in evidence_by_id
                or proposal.candidate_id not in candidate_by_id
                or proposal.criterion_id not in criterion_by_id
            ):
                continue

            grouped[proposal.evidence_id].append(proposal)

        interpreted_by_signal_id: dict[str, EvidenceSignal] = {}

        evidence_groups: list[
            tuple[
                Evidence,
                list[EvidenceSignal],
                list[dict[str, str]],
            ]
        ] = []

        for evidence_id, evidence_proposals in grouped.items():
            evidence = evidence_by_id[evidence_id]

            targets: list[dict[str, str]] = []

            for proposal in evidence_proposals:
                candidate = candidate_by_id[
                    proposal.candidate_id
                ]
                criterion = criterion_by_id[
                    proposal.criterion_id
                ]

                targets.append(
                    {
                        "signal_id": proposal.signal_id,
                        "candidate_id": proposal.candidate_id,
                        "candidate_name": candidate.name,
                        "criterion_id": proposal.criterion_id,
                        "criterion_name": criterion.name,
                    }
                )

            evidence_groups.append(
                (
                    evidence,
                    evidence_proposals,
                    targets,
                )
            )

        for start_index in range(
            0,
            len(evidence_groups),
            self.max_evidence_per_batch,
        ):
            batch_groups = evidence_groups[
                start_index:
                start_index + self.max_evidence_per_batch
            ]

            results = self._classify_multi_evidence_batch(
                groups=[
                    (
                        evidence,
                        targets,
                    )
                    for (
                        evidence,
                        _,
                        targets,
                    ) in batch_groups
                ]
            )

            result_by_signal_id = {
                result["signal_id"]: result
                for result in (results or [])
            }

            for (
                _,
                evidence_proposals,
                _,
            ) in batch_groups:
                for proposal in evidence_proposals:
                    result = result_by_signal_id.get(
                        proposal.signal_id
                    )

                    if result is None:
                        interpreted_by_signal_id[
                            proposal.signal_id
                        ] = proposal
                        continue

                    interpreted_by_signal_id[
                        proposal.signal_id
                    ] = EvidenceSignal(
                        signal_id=proposal.signal_id,
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

        # Preserve ordering only for proposals whose references were valid.
        # Invalid evidence/candidate/criterion references keep the historical
        # contract: they are skipped rather than silently reintroduced.
        valid_signal_ids = {
            proposal.signal_id
            for evidence_proposals in grouped.values()
            for proposal in evidence_proposals
        }

        return [
            interpreted_by_signal_id.get(
                proposal.signal_id,
                proposal,
            )
            for proposal in proposals
            if proposal.signal_id in valid_signal_ids
        ]

    def _classify_batch(
        self,
        *,
        evidence: Evidence,
        targets: list[dict[str, str]],
    ) -> list[dict[str, Any]] | None:
        """Backward-compatible single-evidence classification wrapper."""

        return self._classify_multi_evidence_batch(
            groups=[
                (
                    evidence,
                    targets,
                )
            ]
        )

    def _classify_multi_evidence_batch(
        self,
        *,
        groups: list[
            tuple[
                Evidence,
                list[dict[str, str]],
            ]
        ],
    ) -> list[dict[str, Any]] | None:
        """
        Interpret a bounded group of evidence items in one provider call.

        Each target remains scoped to its own evidence item. Results are
        mapped back exclusively through the supplied signal_id values.
        """

        self.retry_count = 0
        self.last_parse_status = "unknown"

        evidence_groups: list[dict[str, Any]] = []
        allowed_signal_ids: set[str] = set()

        for evidence, targets in groups:
            evidence_text = self._evidence_text(
                evidence
            )

            if not evidence_text:
                continue

            valid_targets = [
                target
                for target in targets
                if target.get("signal_id")
            ]

            if not valid_targets:
                continue

            evidence_groups.append(
                {
                    "evidence_id": evidence.evidence_id,
                    "evidence": evidence_text,
                    "targets": valid_targets,
                }
            )

            allowed_signal_ids.update(
                target["signal_id"]
                for target in valid_targets
            )

        if not evidence_groups:
            self.last_parse_status = "empty_evidence"
            return None

        prompt = MULTI_EVIDENCE_SIGNAL_PROMPT.format(
            evidence_groups=json.dumps(
                evidence_groups,
                ensure_ascii=False,
                indent=2,
            )
        )

        result = self._run_and_parse(
            prompt,
            allowed_signal_ids=allowed_signal_ids,
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
                allowed_signal_ids=allowed_signal_ids,
            )

        return result

    def _run_and_parse(
        self,
        prompt: str,
        *,
        allowed_signal_ids: set[str],
    ) -> list[dict[str, Any]] | None:
        """Invoke semantic agent and validate one batched JSON response."""

        self.llm_call_count += 1
        response = self._agent.run(prompt)
        self._agent.clear_history()

        logger.info(
            "Semantic signal batch output (truncated): %s",
            response[:500],
        )

        return self._extract_payload(
            response,
            allowed_signal_ids=allowed_signal_ids,
        )

    def _extract_payload(
        self,
        raw_response: str,
        *,
        allowed_signal_ids: set[str],
    ) -> list[dict[str, Any]] | None:
        """Parse one batched semantic signal result."""

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

        validated = self._validate_payload(
            payload,
            allowed_signal_ids=allowed_signal_ids,
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
        allowed_signal_ids: set[str],
    ) -> list[dict[str, Any]] | None:
        if not isinstance(payload, dict):
            return None

        raw_results = payload.get("results")

        if not isinstance(raw_results, list):
            return None

        validated: list[dict[str, Any]] = []
        seen_signal_ids: set[str] = set()

        for item in raw_results:
            if not isinstance(item, dict):
                return None

            signal_id = item.get("signal_id")
            direction = item.get("direction")
            strength = item.get("strength")
            rationale = item.get("rationale")

            if (
                not isinstance(signal_id, str)
                or signal_id not in allowed_signal_ids
                or signal_id in seen_signal_ids
            ):
                return None

            if direction not in self.VALID_DIRECTIONS:
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

            seen_signal_ids.add(signal_id)

            validated.append(
                {
                    "signal_id": signal_id,
                    "direction": direction,
                    "strength": float(strength),
                    "rationale": (
                        rationale or ""
                    ).strip(),
                }
            )

        return validated

    @staticmethod
    def _evidence_text(
        evidence: Evidence,
    ) -> str:
        parts = [
            evidence.source_title,
            evidence.snippet,
            evidence.content,
        ]

        text = "\n\n".join(
            part.strip()
            for part in parts
            if isinstance(part, str)
            and part.strip()
        )

        return text[:6000]

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
                'Return {"results": [...]} only. Preserve supplied '
                "signal_id values exactly. direction must be positive, "
                "negative, or neutral; strength must be between 0 and 1."
            )

        return (
            "Return only the required JSON object."
        )
