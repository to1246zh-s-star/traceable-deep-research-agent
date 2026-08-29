from decimal import Decimal

import pytest

from models import RuntimeEfficiency
from services.llm_pricing import (
    LLMPricingRegistry,
    LLMPricingRule,
    apply_trusted_cost_estimate,
)


def _rule(
    *,
    provider="trusted-provider",
    model_id="trusted-model",
):
    return LLMPricingRule(
        provider=provider,
        model_id=model_id,
        input_price_per_1m_tokens=Decimal("2.00"),
        output_price_per_1m_tokens=Decimal("4.00"),
        currency="USD",
        basis="per_1m_tokens",
    )


def _complete_efficiency(prompt=1000, completion=500):
    return RuntimeEfficiency(
        prompt_tokens=prompt,
        completion_tokens=completion,
        total_tokens=prompt + completion,
        llm_usage_complete=True,
    )


def test_complete_usage_and_matching_price_calculates_cost():
    efficiency = _complete_efficiency()

    apply_trusted_cost_estimate(
        efficiency,
        provider="trusted-provider",
        model_id="trusted-model",
        registry=LLMPricingRegistry([_rule()]),
    )

    assert efficiency.estimated_cost == pytest.approx(0.004)
    assert efficiency.cost_currency == "USD"
    assert efficiency.cost_basis == "per_1m_tokens"


def test_prompt_and_completion_prices_are_applied_separately():
    efficiency = _complete_efficiency(prompt=1_000_000, completion=2_000_000)

    apply_trusted_cost_estimate(
        efficiency,
        provider="trusted-provider",
        model_id="trusted-model",
        registry=LLMPricingRegistry([_rule()]),
    )

    assert efficiency.estimated_cost == pytest.approx(10.0)


@pytest.mark.parametrize(
    ("complete", "provider", "model_id", "registry"),
    [
        (False, "trusted-provider", "trusted-model", LLMPricingRegistry([_rule()])),
        (True, "trusted-provider", None, LLMPricingRegistry([_rule()])),
        (True, "trusted-provider", "unknown-model", LLMPricingRegistry([_rule()])),
        (True, "trusted-provider", "trusted-model", LLMPricingRegistry()),
        (True, "other-provider", "trusted-model", LLMPricingRegistry([_rule()])),
    ],
)
def test_missing_trusted_cost_input_remains_unknown(
    complete,
    provider,
    model_id,
    registry,
):
    efficiency = _complete_efficiency()
    efficiency.llm_usage_complete = complete

    apply_trusted_cost_estimate(
        efficiency,
        provider=provider,
        model_id=model_id,
        registry=registry,
    )

    assert efficiency.estimated_cost is None
    assert efficiency.cost_currency is None
    assert efficiency.cost_basis is None


def test_zero_complete_usage_has_zero_cost():
    efficiency = _complete_efficiency(prompt=0, completion=0)

    apply_trusted_cost_estimate(
        efficiency,
        provider="trusted-provider",
        model_id="trusted-model",
        registry=LLMPricingRegistry([_rule()]),
    )

    assert efficiency.estimated_cost == 0.0
    assert efficiency.cost_currency == "USD"


def test_registry_parses_explicit_json_configuration():
    registry = LLMPricingRegistry.from_json(
        """[
          {
            "provider": "custom",
            "model_id": "model-a",
            "input_price_per_1m_tokens": "1.25",
            "output_price_per_1m_tokens": "3.50",
            "currency": "EUR",
            "basis": "per_1m_tokens"
          }
        ]"""
    )

    rule = registry.find("custom", "model-a")
    assert rule is not None
    assert rule.input_price_per_1m_tokens == Decimal("1.25")
    assert rule.output_price_per_1m_tokens == Decimal("3.50")
    assert rule.currency == "EUR"
    assert registry.find("custom", "MODEL-A") is None
