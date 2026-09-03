"""Deterministic source-strategy planning for decision research gaps."""

from __future__ import annotations

from models import DecisionCase, ResearchGap


STRATEGY_SOURCE_TYPES = {
    "PERFORMANCE_SCALE": [
        "official_documentation",
        "benchmark",
        "academic_paper",
    ],
    "SECURITY_GOVERNANCE": [
        "official_security_documentation",
        "security_advisory",
        "cve",
    ],
    "MIGRATION_INTEGRATION": [
        "official_documentation",
        "migration_guide",
        "issue_tracker",
    ],
    "OPERATIONS_RELIABILITY": [
        "official_documentation",
        "issue_tracker",
        "independent_engineering_review",
    ],
    "COST_ECONOMICS": [
        "official_pricing_documentation",
        "cost_comparison",
    ],
    "GENERAL_TECHNICAL": [
        "official_documentation",
        "independent_engineering_review",
    ],
    "GENERAL": [
        "official_documentation",
        "independent_source",
    ],
}


STRATEGY_QUALIFIERS = {
    "PERFORMANCE_SCALE": [
        "official documentation",
        "benchmark",
        "performance",
    ],
    "SECURITY_GOVERNANCE": [
        "official security documentation",
        "security advisory",
        "CVE",
    ],
    "MIGRATION_INTEGRATION": [
        "official documentation",
        "migration guide",
        "issue tracker",
    ],
    "OPERATIONS_RELIABILITY": [
        "official documentation",
        "production reliability",
        "issue tracker",
    ],
    "COST_ECONOMICS": [
        "official pricing",
        "cost",
    ],
    "GENERAL_TECHNICAL": [
        "official documentation",
        "independent technical review",
    ],
    "GENERAL": [
        "official documentation",
        "independent verification",
    ],
}


PERFORMANCE_TERMS = {
    "performance",
    "latency",
    "throughput",
    "scalability",
    "scale",
    "speed",
    "benchmark",
    "capacity",
    "memory",
    "cpu",
    "gpu",
}

SECURITY_TERMS = {
    "security",
    "secure",
    "compliance",
    "privacy",
    "authentication",
    "authorization",
    "encryption",
    "vulnerability",
    "cve",
}

MIGRATION_TERMS = {
    "migration",
    "integration",
    "compatibility",
    "interoperability",
    "dependency",
    "dependencies",
    "upgrade",
    "adoption",
    "implementation",
}

OPERATIONS_TERMS = {
    "operations",
    "operational",
    "reliability",
    "availability",
    "maintenance",
    "maintainability",
    "observability",
    "deployment",
    "devops",
    "complexity",
    "support",
}

COST_TERMS = {
    "cost",
    "pricing",
    "price",
    "budget",
    "economics",
    "economic",
    "license",
    "licensing",
    "tco",
}

COMPARATIVE_TERMS = {
    "benchmark", "compare", "comparison", "faster", "slower",
    "better", "worse", "versus", " vs ", "性能对比", "更快", "优于",
}

CAPABILITY_TERMS = {
    "support", "supports", "capability", "feature", "transaction", "acid",
    "replication", "distributed", "scalability", "horizontal scaling",
    "支持", "事务", "复制", "水平扩展",
}

USER_CONTEXT_TERMS = {
    "team familiarity", "team capability", "team skills", "team experience",
    "deployment environment", "current environment", "existing stack",
    "budget constraint", "团队熟悉", "团队能力", "团队经验", "部署环境",
    "no kubernetes", "docker environment", "self-hosted",
    "现有技术栈", "预算有限", "没有 kubernetes", "当前环境", "自托管",
}

ARCHITECTURE_FIT_TERMS = {
    "architecture", "integration", "migration", "operational fit",
    "operational complexity", "deployment fit", "maintenance cost",
    "learning curve", "new operational skills",
    "架构", "集成", "迁移", "运维适配", "维护成本", "学习成本",
    "运维复杂度", "部署适配",
}

HARD_CONSTRAINT_TERMS = {
    "hard constraint", "must support", "required feature", "必须支持", "硬约束",
}


def classify_gap_claim_type(
    *,
    criterion_name: str,
    description: str,
) -> str:
    """Classify what kind of uncertainty a research gap represents."""
    text = f" {criterion_name} {description} ".casefold()

    if any(term in text for term in USER_CONTEXT_TERMS):
        return "USER_CONTEXT"
    if any(term in text for term in HARD_CONSTRAINT_TERMS):
        return "HARD_CONSTRAINT"
    if any(term in text for term in COMPARATIVE_TERMS):
        return "COMPARATIVE_PERFORMANCE"
    if any(term in text for term in ARCHITECTURE_FIT_TERMS):
        return "ARCHITECTURE_INTEGRATION_FIT"
    if any(term in text for term in CAPABILITY_TERMS):
        return "PRODUCT_CAPABILITY"
    return "GENERAL_EVIDENCE"


def preferred_sources_for_claim_type(
    claim_type: str,
    default_source_types: list[str],
) -> list[str]:
    """Return sufficient, claim-aware evidence expectations."""
    if claim_type in {"PRODUCT_CAPABILITY", "HARD_CONSTRAINT"}:
        return ["official_documentation"]
    if claim_type == "COMPARATIVE_PERFORMANCE":
        return ["benchmark"]
    if claim_type == "ARCHITECTURE_INTEGRATION_FIT":
        return [
            "official_documentation",
            "migration_guide",
        ]
    if claim_type == "USER_CONTEXT":
        return []
    return list(default_source_types)


def assign_search_strategies(
    decision: DecisionCase,
    gaps: list[ResearchGap],
) -> list[ResearchGap]:
    """
    Attach deterministic retrieval strategies to existing ResearchGap objects.

    This enriches retrieval intent only. It does not change gap priority,
    evidence quality, candidate scores, or recommendation semantics.
    """

    criterion_names = {
        criterion.criterion_id: criterion.name
        for criterion in decision.criteria
    }

    candidate_names = {
        candidate.candidate_id: candidate.name
        for candidate in decision.candidates
    }

    for gap in gaps:
        if gap.status != "open":
            gap.preferred_source_types = []
            gap.query_qualifiers = []
            gap.suggested_query = None
            continue

        criterion_name = criterion_names.get(
            gap.criterion_id,
            "",
        )

        strategy = classify_search_strategy(
            criterion_name=criterion_name,
            gap_type=gap.gap_type,
            description=gap.description,
            context_dimensions=getattr(
                gap,
                "context_dimensions",
                [],
            ),
        )

        gap.search_strategy = strategy

        claim_type = (
            "GENERAL_EVIDENCE"
            if gap.gap_type == "reevaluation"
            else classify_gap_claim_type(
                criterion_name=criterion_name,
                description=gap.description,
            )
        )

        gap.preferred_source_types = preferred_sources_for_claim_type(
            claim_type,
            STRATEGY_SOURCE_TYPES[strategy],
        )

        gap.query_qualifiers = list(
            STRATEGY_QUALIFIERS[strategy]
        )

        gap.suggested_query = build_strategy_query(
            gap,
            candidate_name=candidate_names.get(
                gap.candidate_id,
                "",
            ),
            criterion_name=criterion_name,
        )

    return gaps


def classify_search_strategy(
    *,
    criterion_name: str,
    gap_type: str,
    description: str,
    context_dimensions: list[str] | None = None,
) -> str:
    """Classify one gap into a deterministic retrieval strategy."""

    text = " ".join(
        [
            criterion_name,
            gap_type,
            description,
            *(
                context_dimensions
                or []
            ),
        ]
    ).casefold()

    tokens = set(
        text
        .replace("-", " ")
        .replace("_", " ")
        .split()
    )

    scores = {
        "PERFORMANCE_SCALE": len(
            tokens & PERFORMANCE_TERMS
        ),
        "SECURITY_GOVERNANCE": len(
            tokens & SECURITY_TERMS
        ),
        "MIGRATION_INTEGRATION": len(
            tokens & MIGRATION_TERMS
        ),
        "OPERATIONS_RELIABILITY": len(
            tokens & OPERATIONS_TERMS
        ),
        "COST_ECONOMICS": len(
            tokens & COST_TERMS
        ),
    }

    best_score = max(
        scores.values(),
        default=0,
    )

    if best_score <= 0:
        if criterion_name.strip():
            return "GENERAL_TECHNICAL"

        return "GENERAL"

    # Explicit tie order keeps classification deterministic.
    precedence = [
        "SECURITY_GOVERNANCE",
        "MIGRATION_INTEGRATION",
        "PERFORMANCE_SCALE",
        "OPERATIONS_RELIABILITY",
        "COST_ECONOMICS",
    ]

    for strategy in precedence:
        if scores[strategy] == best_score:
            return strategy

    return "GENERAL"


def build_strategy_query(
    gap: ResearchGap,
    *,
    candidate_name: str,
    criterion_name: str,
) -> str:
    """
    Enrich the existing query without inventing technical facts.

    Query qualifiers indicate preferred retrieval directions only.
    """

    base_query = (
        gap.suggested_query
        or " ".join(
            value
            for value in (
                candidate_name,
                criterion_name,
                gap.description,
            )
            if value
        )
    ).strip()

    parts: list[str] = []

    if base_query:
        parts.append(base_query)

    parts.extend(
        gap.query_qualifiers
    )

    return _dedupe_query_terms(
        parts
    )


def _dedupe_query_terms(
    parts: list[str],
) -> str:
    result: list[str] = []
    seen: set[str] = set()

    for part in parts:
        value = " ".join(
            str(part).strip().split()
        )

        if not value:
            continue

        key = value.casefold()

        if key in seen:
            continue

        seen.add(key)
        result.append(value)

    return " ".join(result)
