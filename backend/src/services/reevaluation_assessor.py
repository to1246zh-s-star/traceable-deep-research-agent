"""Deterministic assessment of existing decision re-evaluation triggers."""

from __future__ import annotations

from models import (
    DecisionReevaluationTrigger,
    ReevaluationAssessment,
    ReevaluationRequest,
)


VALID_STATUSES = {
    "REQUIRED",
    "RECOMMENDED",
    "NOT_REQUIRED",
    "UNKNOWN",
}


def assess_reevaluation_need(
    request: ReevaluationRequest,
    triggers: list[DecisionReevaluationTrigger],
) -> ReevaluationAssessment:
    """
    Match structured external observations against persisted re-evaluation
    triggers.

    This service never:
    - interprets free-text observed facts;
    - calls an LLM;
    - retrieves evidence;
    - changes candidate scores;
    - predicts a winner;
    - mutates existing trigger state.
    """

    relevant_triggers = [
        trigger
        for trigger in triggers
        if trigger.decision_id == request.decision_id
    ]

    has_structured_observation = bool(
        request.observed_trigger_ids
        or _has_changed_source_fields(
            request.changed_source_fields
        )
    )

    if not has_structured_observation:
        return ReevaluationAssessment(
            decision_id=request.decision_id,
            status="UNKNOWN",
            observed_facts=list(
                request.observed_facts
            ),
            reasons=[
                (
                    "No structured trigger observation was supplied; "
                    "re-evaluation need cannot be determined "
                    "deterministically."
                )
            ],
        )

    matched = _match_triggers(
        request,
        relevant_triggers,
    )

    if not matched:
        return ReevaluationAssessment(
            decision_id=request.decision_id,
            status="NOT_REQUIRED",
            observed_facts=list(
                request.observed_facts
            ),
            reasons=[
                (
                    "Structured changes were supplied, but none matched "
                    "the persisted re-evaluation triggers."
                )
            ],
        )

    required = any(
        bool(trigger.reevaluation_required)
        for trigger in matched
    )

    status = (
        "REQUIRED"
        if required
        else "RECOMMENDED"
    )

    return ReevaluationAssessment(
        decision_id=request.decision_id,
        status=status,
        matched_trigger_ids=_dedupe(
            trigger.trigger_id
            for trigger in matched
        ),
        invalidated_modules=_dedupe(
            module
            for trigger in matched
            for module in (
                trigger.invalidated_modules
                or []
            )
        ),
        affected_candidate_ids=_dedupe(
            candidate_id
            for trigger in matched
            for candidate_id in (
                trigger.affected_candidate_ids
                or []
            )
        ),
        affected_criterion_ids=_dedupe(
            criterion_id
            for trigger in matched
            for criterion_id in (
                trigger.affected_criterion_ids
                or []
            )
        ),
        affected_scenario_ids=_dedupe(
            scenario_id
            for trigger in matched
            for scenario_id in (
                trigger.affected_scenario_ids
                or []
            )
        ),
        reasons=_build_reasons(
            matched,
            status,
        ),
        observed_facts=list(
            request.observed_facts
        ),
    )


def _match_triggers(
    request: ReevaluationRequest,
    triggers: list[DecisionReevaluationTrigger],
) -> list[DecisionReevaluationTrigger]:
    observed_trigger_ids = set(
        request.observed_trigger_ids
    )

    changed_fields = {
        str(source_type): {
            str(field_name)
            for field_name in fields
            if str(field_name)
        }
        for source_type, fields
        in request.changed_source_fields.items()
        if source_type
    }

    matched: list[
        DecisionReevaluationTrigger
    ] = []

    seen_ids: set[str] = set()

    for trigger in triggers:
        matched_by_id = (
            trigger.trigger_id
            in observed_trigger_ids
        )

        source_fields = changed_fields.get(
            trigger.source_type,
            set(),
        )

        matched_by_source = (
            bool(trigger.source_field)
            and trigger.source_field
            in source_fields
        )

        if not (
            matched_by_id
            or matched_by_source
        ):
            continue

        if trigger.trigger_id in seen_ids:
            continue

        matched.append(trigger)
        seen_ids.add(
            trigger.trigger_id
        )

    # Existing trigger derivation is deterministic, therefore preserving
    # trigger_id ordering gives stable assessment output.
    matched.sort(
        key=lambda item: item.trigger_id
    )

    return matched


def _build_reasons(
    triggers: list[DecisionReevaluationTrigger],
    status: str,
) -> list[str]:
    reasons: list[str] = []

    for trigger in triggers:
        rationale = list(
            trigger.rationale
            or []
        )

        if rationale:
            reasons.extend(rationale)
            continue

        reasons.append(
            (
                f"Matched re-evaluation trigger "
                f"{trigger.trigger_id} "
                f"({trigger.trigger_type})."
            )
        )

    if status == "REQUIRED":
        reasons.append(
            (
                "At least one matched persisted trigger explicitly "
                "requires re-evaluation."
            )
        )
    else:
        reasons.append(
            (
                "Relevant persisted trigger state changed, but no "
                "matched trigger explicitly requires re-evaluation."
            )
        )

    return _dedupe(reasons)


def _has_changed_source_fields(
    values: dict[str, list[str]],
) -> bool:
    return any(
        bool(fields)
        for fields in values.values()
    )


def _dedupe(
    values,
) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()

    for value in values:
        if not value:
            continue

        value = str(value)

        if value in seen:
            continue

        seen.add(value)
        result.append(value)

    return result
