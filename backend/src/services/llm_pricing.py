"""Explicit trusted pricing rules for provider-observed LLM usage."""

from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Iterable

from models import RuntimeEfficiency


@dataclass(kw_only=True, frozen=True)
class LLMPricingRule:
    """One explicit provider/model token-pricing rule."""

    provider: str
    model_id: str
    input_price_per_1m_tokens: Decimal
    output_price_per_1m_tokens: Decimal
    currency: str
    basis: str = "per_1m_tokens"
    basis_units: int = 1_000_000

    def __post_init__(self) -> None:
        """Validate explicit pricing metadata."""
        if not self.provider.strip():
            raise ValueError("pricing provider must not be empty")
        if not self.model_id.strip():
            raise ValueError("pricing model_id must not be empty")
        if not self.currency.strip():
            raise ValueError("pricing currency must not be empty")
        if not self.basis.strip():
            raise ValueError("pricing basis must not be empty")
        if self.basis_units <= 0:
            raise ValueError("pricing basis_units must be positive")
        if self.input_price_per_1m_tokens < 0:
            raise ValueError("input token price must be non-negative")
        if self.output_price_per_1m_tokens < 0:
            raise ValueError("output token price must be non-negative")


class LLMPricingRegistry:
    """Deterministic exact-match registry of trusted pricing rules."""

    def __init__(self, rules: Iterable[LLMPricingRule] = ()) -> None:
        """Index explicit rules by provider and exact model identifier."""
        self._rules: dict[tuple[str, str], LLMPricingRule] = {}
        for rule in rules:
            key = self._key(rule.provider, rule.model_id)
            if key in self._rules:
                raise ValueError(
                    "duplicate pricing rule for provider/model: "
                    f"{rule.provider}/{rule.model_id}"
                )
            self._rules[key] = rule

    @staticmethod
    def _key(provider: str, model_id: str) -> tuple[str, str]:
        return provider.strip().lower(), model_id.strip()

    def find(self, provider: str, model_id: str) -> LLMPricingRule | None:
        """Return an exact provider/model match, if explicitly configured."""
        return self._rules.get(self._key(provider, model_id))

    @classmethod
    def from_json(cls, raw: str | None) -> LLMPricingRegistry:
        """Parse explicit pricing configuration without built-in prices."""
        if raw is None or not raw.strip():
            return cls()

        payload = json.loads(raw)
        if not isinstance(payload, list):
            raise ValueError("LLM pricing configuration must be a JSON list")

        rules: list[LLMPricingRule] = []
        for item in payload:
            if not isinstance(item, dict):
                raise ValueError("each LLM pricing rule must be an object")
            rules.append(_pricing_rule_from_mapping(item))
        return cls(rules)


def _pricing_rule_from_mapping(item: dict[str, Any]) -> LLMPricingRule:
    required = (
        "provider",
        "model_id",
        "input_price_per_1m_tokens",
        "output_price_per_1m_tokens",
        "currency",
    )
    missing = [name for name in required if name not in item]
    if missing:
        raise ValueError(f"pricing rule missing fields: {', '.join(missing)}")

    return LLMPricingRule(
        provider=str(item["provider"]),
        model_id=str(item["model_id"]),
        input_price_per_1m_tokens=Decimal(
            str(item["input_price_per_1m_tokens"])
        ),
        output_price_per_1m_tokens=Decimal(
            str(item["output_price_per_1m_tokens"])
        ),
        currency=str(item["currency"]),
        basis=str(item.get("basis", "per_1m_tokens")),
        basis_units=int(item.get("basis_units", 1_000_000)),
    )


def apply_trusted_cost_estimate(
    efficiency: RuntimeEfficiency,
    *,
    provider: str | None,
    model_id: str | None,
    registry: LLMPricingRegistry,
) -> None:
    """Apply cost only for complete usage and an exact trusted price."""
    efficiency.estimated_cost = None
    efficiency.cost_currency = None
    efficiency.cost_basis = None

    if efficiency.llm_usage_complete is not True:
        return
    if not provider or not provider.strip() or not model_id or not model_id.strip():
        return
    if not isinstance(efficiency.prompt_tokens, int):
        return
    if not isinstance(efficiency.completion_tokens, int):
        return

    rule = registry.find(provider, model_id)
    if rule is None:
        return

    cost = (
        Decimal(efficiency.prompt_tokens) * rule.input_price_per_1m_tokens
        + Decimal(efficiency.completion_tokens) * rule.output_price_per_1m_tokens
    ) / Decimal(rule.basis_units)

    efficiency.estimated_cost = float(cost)
    efficiency.cost_currency = rule.currency
    efficiency.cost_basis = rule.basis
