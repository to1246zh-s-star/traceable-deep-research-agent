from services.context_engineering import (
    CONTEXT_PRIORITY_CRITICAL,
    CONTEXT_PRIORITY_HIGH,
    ContextBudget,
    ContextCompressor,
    ContextSection,
    ContextSelection,
    ContextUnitEstimator,
)


def test_compressor_is_deterministic_and_preserves_boundaries():
    section = ContextSection(
        name="Evidence Context",
        content="\n\n".join(f"paragraph {index}: " + "x" * 80 for index in range(20)),
        source_ids=("evidence-1",),
    )
    selection = ContextSelection(purpose="test", sections=(section,))
    compressor = ContextCompressor()

    first = compressor.compress(selection, max_section_units=400)
    second = compressor.compress(selection, max_section_units=400)

    assert first == second
    compressed = first.selection.sections[0]
    assert ContextCompressor.OMISSION_MARKER in compressed.content
    assert "paragraph 0:" in compressed.content
    assert "paragraph 19:" in compressed.content
    assert compressed.source_ids == ("evidence-1",)
    assert ContextUnitEstimator().estimate(compressed) <= 400


def test_compression_does_not_mutate_source_selection():
    original_content = "original-evidence-body-" * 100
    section = ContextSection(name="Context", content=original_content)
    selection = ContextSelection(purpose="test", sections=(section,))

    result = ContextCompressor().compress(selection, max_section_units=200)

    assert selection.sections[0] is section
    assert selection.sections[0].content == original_content
    assert result.selection.sections[0] is not section
    assert result.selection.sections[0].content != original_content


def test_sections_within_limit_are_not_replaced_or_traced():
    section = ContextSection(name="Context", content="small")
    selection = ContextSelection(purpose="test", sections=(section,))

    result = ContextCompressor().compress(selection, max_section_units=100)

    assert result.selection.sections == (section,)
    assert result.selection.sections[0] is section
    assert result.decisions == ()


def test_single_block_fallback_is_explicit_and_within_limit():
    section = ContextSection(name="Context", content="x" * 1000)
    result = ContextCompressor().compress(
        ContextSelection(purpose="test", sections=(section,)),
        max_section_units=180,
    )

    compressed = result.selection.sections[0]
    assert ContextCompressor.OMISSION_MARKER in compressed.content
    assert ContextUnitEstimator().estimate(compressed) <= 180
    decision = result.decisions[0]
    assert decision.original_estimated_units > decision.compressed_estimated_units
    assert decision.strategy == "semantic_head_tail"
    assert decision.reason == "section_exceeds_limit"


def test_budget_aware_compression_targets_actual_remaining_units():
    topic = ContextSection(
        name="Research Topic",
        content="topic",
        priority=CONTEXT_PRIORITY_CRITICAL,
        required=True,
    )
    task = ContextSection(
        name="Task",
        content="task metadata",
        priority=CONTEXT_PRIORITY_HIGH,
        required=True,
    )
    context = ContextSection(name="Task Context", content="retrieved-content-" * 1000)
    selection = ContextSelection(purpose="summary", sections=(context, task, topic))
    estimator = ContextUnitEstimator()
    available = 600
    higher_priority_units = estimator.estimate(topic) + estimator.estimate(task)

    result = ContextCompressor().compress_to_budget(
        selection,
        ContextBudget(max_units=available),
    )

    compressed = result.selection.sections[0]
    assert result.selection.sections[1] is task
    assert result.selection.sections[2] is topic
    assert estimator.estimate(compressed) <= available - higher_priority_units
    assert "retrieved-content-" in compressed.content
    assert ContextCompressor.OMISSION_MARKER in compressed.content
    assert context.content == "retrieved-content-" * 1000
    assert result.decisions[0].reason == "section_exceeds_remaining_budget"


def test_compression_keeps_body_fragment_after_short_context_label():
    content = "Task context:\n" + ("retrieved-content-" * 5000)
    section = ContextSection(name="Task Context", content=content)
    budget = ContextBudget(max_units=10000)

    result = ContextCompressor().compress_to_budget(
        ContextSelection(purpose="summary", sections=(section,)),
        budget,
    )

    compressed = result.selection.sections[0]
    assert "Task context:" in compressed.content
    assert "retrieved-content-" in compressed.content
    assert ContextCompressor.OMISSION_MARKER in compressed.content
    assert ContextUnitEstimator().estimate(compressed) <= 10000
    assert section.content == content


def test_budget_aware_compression_leaves_required_sections_untouched():
    required = ContextSection(
        name="Required",
        content="required-body-" * 100,
        required=True,
    )
    selection = ContextSelection(purpose="test", sections=(required,))

    result = ContextCompressor().compress_to_budget(
        selection,
        ContextBudget(max_units=100),
    )

    assert result.selection.sections[0] is required
    assert not result.decisions


def test_budget_aware_compression_defers_to_drop_below_safe_minimum():
    section = ContextSection(name="Context", content="x" * 1000)
    minimum = ContextCompressor.minimum_safe_units(section.name)

    result = ContextCompressor().compress_to_budget(
        ContextSelection(purpose="test", sections=(section,)),
        ContextBudget(max_units=minimum - 1),
    )

    assert result.selection.sections[0] is section
    assert not result.decisions
