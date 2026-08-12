from services.decision_case_extractor import DecisionCaseExtractor


class DummyConfig:
    strip_thinking_tokens = False


class StaticAgent:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0
        self.prompts = []

    def run(self, prompt):
        self.prompts.append(prompt)
        response = self.responses[self.calls]
        self.calls += 1
        return response

    def clear_history(self):
        pass


def make_success_payload():
    return """
    {
      "is_decision": true,
      "question": "Should we choose Qdrant or Milvus?",
      "context": "Vector database selection for our system",
      "candidates": [
        {
          "name": "Qdrant",
          "description": "Vector database"
        },
        {
          "name": "Milvus",
          "description": "Vector database"
        }
      ],
      "requirements": [
        {
          "text": "The system must support vector search"
        }
      ],
      "constraints": [
        {
          "text": "Must support self-hosted deployment"
        }
      ],
      "criteria": [
        {
          "name": "Operational simplicity",
          "weight": 2.0,
          "description": "Ease of deployment and maintenance"
        },
        {
          "name": "Scalability",
          "weight": 1.0,
          "description": null
        }
      ]
    }
    """


def test_extract_successful_decision_case():
    agent = StaticAgent([
        make_success_payload(),
    ])

    extractor = DecisionCaseExtractor(
        agent,
        DummyConfig(),
    )

    decision = extractor.extract(
        "Compare Qdrant and Milvus for a self-hosted vector database."
    )

    assert decision is not None

    assert decision.question == (
        "Should we choose Qdrant or Milvus?"
    )

    assert [
        candidate.name
        for candidate in decision.candidates
    ] == [
        "Qdrant",
        "Milvus",
    ]

    assert len(decision.requirements) == 1
    assert len(decision.constraints) == 1
    assert len(decision.criteria) == 2

    assert decision.constraints[0].source == "user"
    assert decision.criteria[0].source == "user"

    assert decision.criteria[0].weight == 2.0

    assert extractor.retry_count == 0
    assert extractor.final_parse_status == "success"
    assert extractor.stats["calls"] == 1
    assert extractor.stats["final_status"] == "success"


def test_non_decision_topic_returns_none_without_retry():
    agent = StaticAgent([
        """
        {
          "is_decision": false,
          "question": "",
          "context": null,
          "candidates": [],
          "requirements": [],
          "constraints": [],
          "criteria": []
        }
        """,
    ])

    extractor = DecisionCaseExtractor(
        agent,
        DummyConfig(),
    )

    decision = extractor.extract(
        "Explain how transformer attention works."
    )

    assert decision is None

    assert agent.calls == 1
    assert extractor.retry_count == 0
    assert extractor.last_parse_status == "non_decision"
    assert extractor.final_parse_status == "non_decision"
    assert extractor.stats["final_status"] == "non_decision"


def test_invalid_json_retries_once_and_recovers():
    agent = StaticAgent([
        '{"is_decision": true,',
        make_success_payload(),
    ])

    extractor = DecisionCaseExtractor(
        agent,
        DummyConfig(),
    )

    decision = extractor.extract(
        "Compare Qdrant and Milvus."
    )

    assert decision is not None

    assert agent.calls == 2
    assert extractor.retry_count == 1
    assert extractor.retry_reason == "json_error"
    assert extractor.final_parse_status == "success"

    retry_prompt = agent.prompts[1]

    assert "repair instruction" in retry_prompt.lower()
    assert "valid json" in retry_prompt.lower()


def test_invalid_schema_retries_once_and_recovers():
    agent = StaticAgent([
        """
        {
          "is_decision": true,
          "question": "Choose database",
          "context": null,
          "candidates": "Qdrant",
          "requirements": [],
          "constraints": [],
          "criteria": []
        }
        """,
        make_success_payload(),
    ])

    extractor = DecisionCaseExtractor(
        agent,
        DummyConfig(),
    )

    decision = extractor.extract(
        "Choose between Qdrant and Milvus."
    )

    assert decision is not None

    assert agent.calls == 2
    assert extractor.retry_count == 1
    assert extractor.retry_reason == "invalid_schema"
    assert extractor.final_parse_status == "success"

    retry_prompt = agent.prompts[1]

    assert "schema" in retry_prompt.lower()
    assert "json" in retry_prompt.lower()


def test_retry_failure_returns_none_and_records_failure():
    agent = StaticAgent([
        '{"is_decision": true,',
        '{"is_decision": true,',
    ])

    extractor = DecisionCaseExtractor(
        agent,
        DummyConfig(),
    )

    decision = extractor.extract(
        "Compare Qdrant and Milvus."
    )

    assert decision is None

    assert agent.calls == 2
    assert extractor.retry_count == 1
    assert extractor.retry_reason == "json_error"

    assert extractor.final_parse_status == "retry_failed"

    assert extractor.stats["calls"] == 2
    assert extractor.stats["retry_count"] == 1
    assert extractor.stats["failures"] == 1
    assert extractor.stats["final_status"] == "retry_failed"
