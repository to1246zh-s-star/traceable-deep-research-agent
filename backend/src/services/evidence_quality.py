"""Evidence quality assessment for V3 Phase 9."""

from urllib.parse import urlparse

from models import (
    DecisionCase,
    Evidence,
    EvidenceApplicability,
    EvidenceAssessment,
    EvidenceQuality,
    SourceDiversity,
    SourceQuality,
)

from services.source_authority import (
    authority_confidence,
    recognize_source_authority,
)


SOURCE_TYPE_CONFIDENCE = {
    "official_docs": 0.95,
    "official_benchmark": 0.95,
    "research_paper": 0.90,
    "independent_benchmark": 0.85,
    "technical_blog": 0.70,
    "community": 0.55,
    "unknown": 0.40,
}


def classify_source_type(evidence: Evidence) -> str:
    """
    Classify evidence into a coarse source type.

    Phase 9 uses a deterministic baseline only.
    More advanced provenance classification can be introduced later.
    """

    url = (evidence.source_url or "").lower()
    title = (evidence.source_title or "").lower()

    if "arxiv.org" in url or "doi.org" in url:
        return "research_paper"

    if "docs." in url or "/docs/" in url or "documentation" in title:
        return "official_docs"

    if "benchmark" in title:
        if any(
            token in url
            for token in (
                "github.com",
                "medium.com",
                "towardsdatascience.com",
            )
        ):
            return "independent_benchmark"

        return "official_benchmark"

    if any(
        token in url
        for token in (
            "reddit.com",
            "stackoverflow.com",
            "news.ycombinator.com",
        )
    ):
        return "community"

    if any(
        token in url
        for token in (
            "medium.com",
            "dev.to",
            "towardsdatascience.com",
        )
    ):
        return "technical_blog"

    return "unknown"


def assess_source_quality(
    evidence: Evidence,
    decision: DecisionCase | None = None,
) -> SourceQuality:
    """
    Assess source quality with optional Phase 26 authority recognition.

    Backward compatibility:
    when no DecisionCase is available, preserve the pre-Phase-26
    source-type confidence rather than pretending authority was resolved.
    """

    source_type = classify_source_type(
        evidence
    )

    legacy_confidence = (
        SOURCE_TYPE_CONFIDENCE[
            source_type
        ]
    )

    if decision is None:
        return SourceQuality(
            evidence_id=evidence.evidence_id,
            source_type=source_type,
            confidence=legacy_confidence,
            authority_type="UNKNOWN",
            authority_level="UNKNOWN",
            authority_signals=[
                "authority_not_evaluated_without_decision"
            ],
            rationale=(
                "Source classified as "
                f"{source_type!r}. "
                "Authority recognition was not evaluated "
                "because no DecisionCase was supplied; "
                "legacy source-type confidence was preserved."
            ),
        )

    authority = recognize_source_authority(
        evidence,
        decision,
    )

    confidence = authority_confidence(
        authority,
        legacy_confidence=legacy_confidence,
    )

    return SourceQuality(
        evidence_id=evidence.evidence_id,
        source_type=source_type,
        confidence=confidence,
        authority_type=(
            authority.authority_type
        ),
        authority_level=(
            authority.authority_level
        ),
        authority_signals=list(
            authority.signals
        ),
        rationale=(
            "Source classified as "
            f"{source_type!r}; authority "
            f"recognized as "
            f"{authority.authority_type!r} "
            f"({authority.authority_level}). "
            "Confidence is a deterministic "
            "heuristic, not a calibrated probability."
        ),
    )


def assess_evidence_quality(
    evidence: Evidence,
) -> EvidenceQuality:
    """
    Assess intrinsic evidence completeness.

    This does not judge whether the evidence is correct.
    It measures whether enough structured content exists to inspect it.
    """

    quality_components: list[float] = []

    quality_components.append(
        1.0 if evidence.source_url else 0.0
    )

    quality_components.append(
        1.0 if evidence.source_title else 0.0
    )

    quality_components.append(
        1.0 if evidence.snippet else 0.0
    )

    quality_components.append(
        1.0 if evidence.content else 0.0
    )

    completeness = sum(quality_components) / len(
        quality_components
    )

    content_length = len(
        (evidence.content or evidence.snippet or "").strip()
    )

    if content_length >= 500:
        content_factor = 1.0
    elif content_length >= 200:
        content_factor = 0.8
    elif content_length >= 50:
        content_factor = 0.6
    elif content_length > 0:
        content_factor = 0.4
    else:
        content_factor = 0.0

    quality_score = (
        0.6 * completeness
        + 0.4 * content_factor
    )

    return EvidenceQuality(
        evidence_id=evidence.evidence_id,
        quality_score=quality_score,
        completeness=completeness,
        rationale=(
            "Baseline evidence quality combines structured field "
            "completeness and available content depth"
        ),
    )


def assess_applicability(
    evidence: Evidence,
    decision: DecisionCase,
) -> EvidenceApplicability:
    """
    Estimate evidence applicability to the DecisionCase.

    Phase 9 baseline uses lexical overlap between DecisionCase context
    and available evidence text. This is deliberately simple and
    explainable; semantic applicability belongs to later iterations.
    """

    decision_text = " ".join(
        part
        for part in (
            decision.question,
            decision.context or "",
            " ".join(
                requirement.text
                for requirement in decision.requirements
            ),
            " ".join(
                constraint.text
                for constraint in decision.constraints
            ),
            " ".join(
                criterion.name
                for criterion in decision.criteria
            ),
        )
        if part
    ).lower()

    evidence_text = " ".join(
        part
        for part in (
            evidence.source_title or "",
            evidence.snippet or "",
            evidence.content or "",
        )
        if part
    ).lower()

    decision_tokens = {
        token
        for token in decision_text.replace("/", " ").split()
        if len(token) >= 4
    }

    evidence_tokens = {
        token
        for token in evidence_text.replace("/", " ").split()
        if len(token) >= 4
    }

    if not decision_tokens or not evidence_tokens:
        applicability_score = 0.0
    else:
        overlap = decision_tokens & evidence_tokens
        applicability_score = min(
            1.0,
            len(overlap) / max(1, len(decision_tokens)),
        )

    return EvidenceApplicability(
        evidence_id=evidence.evidence_id,
        decision_id=decision.decision_id,
        applicability_score=applicability_score,
        rationale=(
            "Baseline applicability derived from lexical overlap "
            "between evidence and decision context"
        ),
    )


def assess_evidence(
    evidence: Evidence,
    decision: DecisionCase,
) -> EvidenceAssessment:
    """Combine source quality, evidence quality, and applicability."""

    source_quality = assess_source_quality(
        evidence,
        decision,
    )
    evidence_quality = assess_evidence_quality(evidence)
    applicability = assess_applicability(
        evidence,
        decision,
    )

    overall_score = (
        source_quality.confidence
        * evidence_quality.quality_score
        * applicability.applicability_score
    )

    return EvidenceAssessment(
        evidence_id=evidence.evidence_id,
        decision_id=decision.decision_id,
        source_quality=source_quality,
        evidence_quality=evidence_quality,
        applicability=applicability,
        overall_score=overall_score,
    )


def calculate_source_diversity(
    evidence_items: list[Evidence],
) -> SourceDiversity:
    """
    Calculate source-type diversity for a collection of Evidence.

    The score reflects variety of source categories, not truthfulness.
    """

    if not evidence_items:
        return SourceDiversity(
            evidence_count=0,
            source_type_count=0,
            diversity_score=0.0,
            source_types=[],
        )

    source_types = sorted(
        {
            classify_source_type(evidence)
            for evidence in evidence_items
        }
    )

    diversity_score = min(
        1.0,
        len(source_types) / len(evidence_items),
    )

    return SourceDiversity(
        evidence_count=len(evidence_items),
        source_type_count=len(source_types),
        diversity_score=diversity_score,
        source_types=source_types,
    )


def source_domain(
    evidence: Evidence,
) -> str | None:
    """Return source hostname for future diversity extensions."""

    if not evidence.source_url:
        return None

    parsed = urlparse(evidence.source_url)
    return parsed.hostname
