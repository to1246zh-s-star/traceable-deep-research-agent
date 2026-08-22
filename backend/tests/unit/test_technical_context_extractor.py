import json

from models import (
    Constraint,
    DecisionCase,
    Requirement,
    TechnicalContext,
)
from services.technical_context_extractor import (
    CONTEXT_FIELDS,
    TechnicalContextExtractor,
)


class StubAgent:
    def __init__(self, responses):
        self.responses = list(responses)
        self.prompts = []
        self.clear_count = 0

    def run(self, prompt):
        self.prompts.append(prompt)
        return self.responses.pop(0)

    def clear_history(self):
        self.clear_count += 1


class StubConfig:
    strip_thinking_tokens = False


def valid_payload(**overrides):
    payload = {
        field_name: []
        for field_name in CONTEXT_FIELDS
    }
    payload.update(overrides)
    return payload


def make_decision():
    return DecisionCase(
        decision_id="dec_context",
        question="Qdrant or Milvus?",
        context=(
            "Existing Python service "
            "deployed with Docker."
        ),
        requirements=[
            Requirement(
                text="Keep operations simple"
            )
        ],
        constraints=[
            Constraint(
                text="Must support self-hosting"
            )
        ],
    )


def make_extractor(*responses):
    agent = StubAgent(responses)

    extractor = TechnicalContextExtractor(
        agent,
        StubConfig(),
    )

    return extractor, agent


def test_extracts_technical_context():
    payload = valid_payload(
        existing_stack=[
            "Python",
            "FastAPI",
        ],
        deployment_environment=[
            "Docker-only",
        ],
        team_capabilities=[
            "limited DevOps capacity",
        ],
    )

    extractor, agent = make_extractor(
        json.dumps(payload)
    )

    result = extractor.extract(
        "Choose Qdrant or Milvus",
        make_decision(),
    )

    assert isinstance(
        result,
        TechnicalContext,
    )

    assert result.existing_stack == [
        "Python",
        "FastAPI",
    ]

    assert (
        result.deployment_environment
        == ["Docker-only"]
    )

    assert (
        result.team_capabilities
        == ["limited DevOps capacity"]
    )

    assert extractor.llm_call_count == 1
    assert agent.clear_count == 1


def test_unknown_information_remains_empty():
    extractor, _ = make_extractor(
        json.dumps(valid_payload())
    )

    result = extractor.extract(
        "Choose Qdrant or Milvus",
        make_decision(),
    )

    assert result is not None
    assert result.infrastructure == []
    assert result.budget_constraints == []


def test_rejects_missing_schema_field():
    payload = valid_payload()
    payload.pop("infrastructure")

    extractor, _ = make_extractor(
        json.dumps(payload),
        json.dumps(payload),
    )

    result = extractor.extract(
        "Choose A or B",
        make_decision(),
    )

    assert result is None
    assert (
        extractor.last_parse_status
        == "invalid_schema"
    )
    assert extractor.llm_call_count == 2


def test_rejects_non_string_values():
    payload = valid_payload(
        existing_stack=[
            "Python",
            123,
        ]
    )

    extractor, _ = make_extractor(
        json.dumps(payload),
        json.dumps(payload),
    )

    result = extractor.extract(
        "Choose A or B",
        make_decision(),
    )

    assert result is None
    assert extractor.llm_call_count == 2


def test_retries_malformed_json_once():
    payload = valid_payload(
        existing_stack=["Python"]
    )

    extractor, _ = make_extractor(
        "not-json",
        json.dumps(payload),
    )

    result = extractor.extract(
        "Choose A or B",
        make_decision(),
    )

    assert result is not None
    assert result.existing_stack == [
        "Python"
    ]

    assert extractor.retry_count == 1
    assert extractor.llm_call_count == 2
    assert (
        extractor.last_parse_status
        == "success"
    )


def test_empty_output_fails_conservatively():
    extractor, _ = make_extractor(
        "",
        "",
    )

    result = extractor.extract(
        "Choose A or B",
        make_decision(),
    )

    assert result is None
    assert extractor.llm_call_count == 2


def test_normalizes_whitespace_and_duplicates():
    payload = valid_payload(
        existing_stack=[
            " Python ",
            "python",
            "",
            "FastAPI",
        ]
    )

    extractor, _ = make_extractor(
        json.dumps(payload)
    )

    result = extractor.extract(
        "Choose A or B",
        make_decision(),
    )

    assert result is not None
    assert result.existing_stack == [
        "Python",
        "FastAPI",
    ]
