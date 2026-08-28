"""Orchestrator coordinating the deep research workflow."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from queue import Empty, Queue
from threading import Lock, Semaphore, Thread
from typing import Any, Callable, Iterator

from hello_agents import HelloAgentsLLM, ToolAwareSimpleAgent
from hello_agents.tools import ToolRegistry
from hello_agents.tools.builtin.note_tool import NoteTool

from config import Configuration
from prompts import (
    report_writer_instructions,
    task_summarizer_instructions,
    todo_planner_system_prompt,
)
from models import (
    AdaptiveResearchIteration,
    AdaptiveResearchState,
    Claim,
    ExecutionEvent,
    ExecutionTrace,
    ResearchAnalysis,
    CandidateCriterionScore,
    DecisionCase,
    EvidenceAssessment,
    EvidenceSignal,
    ResearchBudget,
    ResearchUsage,
    ReevaluationPreparation,
    SummaryState,
    SummaryStateOutput,
    TodoItem,

    IntegrationAssessment,
    TechnicalContext,)
from services.constraint_resolver import ConstraintResolver
from services.decision_case_extractor import DecisionCaseExtractor
from services.decision_input_builder import (
    build_evidence_assessments,
    build_evidence_signals,
)
from services.decision_pipeline import run_decision_pipeline
from services.execution_errors import classify_execution_error
from services.runtime_notices import record_runtime_notice
from services.llm_runtime_circuit import (
    is_llm_circuit_open,
    open_llm_circuit_from_error,
    record_circuit_skip,
)
from services.execution_trace import ExecutionTraceService
from services.adaptive_decision_loop import run_adaptive_decision_loop
from services.reevaluation_execution import (
    activate_prepared_reevaluation,
)
from services.adaptive_research import (
    plan_adaptive_iteration,
    record_iteration_finished,
    record_iteration_started,
    select_research_gaps,
)
from services.planner import PlanningService
from services.semantic_signal_extractor import SemanticSignalExtractor
from services.incremental_semantic_signals import (
    merge_semantic_signals,
    partition_semantic_proposals,
)
from services.reporter import ReportingService
from services.search import dispatch_search, extract_evidence, prepare_research_context
from services.tool_runtime import (
    TOOL_SUCCESS,
    ToolDefinition,
    ToolInvocation,
    ToolParameter,
    ToolRegistry as RuntimeToolRegistry,
    serialize_tool_trace_for_persistence,
)
from services.summarizer import SummarizationService
from services.tool_events import ToolCallTracker

logger = logging.getLogger(__name__)


from services.technical_context_extractor import TechnicalContextExtractor
from services.integration_assessor import IntegrationAssessor

class DeepResearchAgent:
    """Coordinator orchestrating TODO-based research workflow using HelloAgents."""

    def __init__(self, config: Configuration | None = None) -> None:
        """Initialise the coordinator with configuration and shared tools."""
        self.config = config or Configuration.from_env()
        self.llm = self._init_llm()

        self.note_tool = (
            NoteTool(workspace=self.config.notes_workspace)
            if self.config.enable_notes
            else None
        )
        self.tools_registry: ToolRegistry | None = None
        if self.note_tool:
            registry = ToolRegistry()
            registry.register_tool(self.note_tool)
            self.tools_registry = registry

        self._tool_tracker = ToolCallTracker(
            self.config.notes_workspace if self.config.enable_notes else None
        )
        self._tool_event_sink_enabled = False
        self._state_lock = Lock()
        self._last_state: SummaryState | None = None
        self._execution_trace_service = ExecutionTraceService(
            lock=self._state_lock,
        )

        # Runtime registry used by the actual research execution pipeline.
        # This registry is separate from HelloAgents' note-tool registry.
        self._research_tool_registry = RuntimeToolRegistry()
        self._register_research_runtime_tools()

        self.todo_agent = self._create_tool_aware_agent(
            name="研究规划专家",
            system_prompt=todo_planner_system_prompt.strip(),
        )
        self.report_agent = self._create_tool_aware_agent(
            name="报告撰写专家",
            system_prompt=report_writer_instructions.strip(),
        )

        self.decision_case_agent = self._create_tool_aware_agent(
            name="技术决策结构化专家",
            system_prompt=(
                "Extract structured technical decision information. "
                "Follow the user prompt exactly and return only the "
                "requested JSON."
            ),
        )

        self.semantic_signal_agent = self._create_tool_aware_agent(
            name="证据语义判定专家",
            system_prompt=(
                "Interpret supplied evidence conservatively. "
                "Determine only evidence direction and strength, "
                "and return exactly the requested JSON."
            ),
        )

        self._summarizer_factory: Callable[[], ToolAwareSimpleAgent] = lambda: self._create_tool_aware_agent(  # noqa: E501
            name="任务总结专家",
            system_prompt=task_summarizer_instructions.strip(),
        )

        self.planner = PlanningService(self.todo_agent, self.config)
        self.constraint_resolution_agent = self._create_tool_aware_agent(
            name="硬约束证据判定专家",
            system_prompt=(
                "Evaluate whether supplied evidence explicitly establishes "
                "that a technical candidate satisfies or violates a hard "
                "constraint. Be conservative, never infer missing facts, "
                "and return structured JSON only."
            ),
        )

        self.summarizer = SummarizationService(self._summarizer_factory, self.config)
        self.reporting = ReportingService(self.report_agent, self.config)
        self.decision_case_extractor = DecisionCaseExtractor(
            self.decision_case_agent,
            self.config,
        )
        self.semantic_signal_extractor = SemanticSignalExtractor(
            self.semantic_signal_agent,
            self.config,
        )

        technical_context_agent = (
            self._create_tool_aware_agent(
                name="technical-context-extractor",
                system_prompt=(
                    "Extract structured technical architecture "
                    "context conservatively. Return JSON only."
                ),
            )
        )

        self.technical_context_extractor = (
            TechnicalContextExtractor(
                technical_context_agent,
                self.config,
            )
        )

        integration_assessment_agent = (
            self._create_tool_aware_agent(
                name="integration-assessor",
                system_prompt=(
                    "Assess candidate architecture "
                    "integration conservatively "
                    "from context and evidence. "
                    "Return JSON only."
                ),
            )
        )

        self.integration_assessor = (
            IntegrationAssessor(
                integration_assessment_agent,
                self.config,
            )
        )



        self.constraint_resolver = ConstraintResolver(
            self.constraint_resolution_agent,
            self.config,
        )
        self._last_search_notices: list[str] = []
        # Temporary sidecars used only by bounded initial-task
        # parallel execution. They are never persisted as business state.
        self._parallel_context_buffer: dict[
            int,
            tuple[str, str],
        ] | None = None
        self._parallel_loop_counts: dict[int, int] | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def extract_decision_case(
        self,
        research_topic: str,
    ) -> DecisionCase | None:
        """Extract a structured V3 DecisionCase from a research topic."""

        return self.decision_case_extractor.extract(
            research_topic,
        )

    def extract_semantic_signals(
        self,
        state: SummaryState,
        decision: DecisionCase,
        proposals: list[EvidenceSignal],
    ) -> list[EvidenceSignal]:
        """Interpret evidence proposals into semantic signal directions."""

        return self.semantic_signal_extractor.extract(
            state,
            decision,
            proposals,
        )

    def extract_technical_context(
        self,
        state: SummaryState,
        decision: DecisionCase,
    ) -> TechnicalContext | None:
        """Extract optional architecture-aware technical context."""

        if state.technical_context is not None:
            return state.technical_context

        extractor = getattr(
            self,
            "technical_context_extractor",
            None,
        )

        if extractor is None:
            return None

        if is_llm_circuit_open(state):
            record_circuit_skip(
                state,
                stage="technical_context_extraction",
            )
            return None

        try:
            return extractor.extract(
                state.research_topic,
                decision,
            )
        except Exception as exc:
            logger.exception(
                "Technical context extraction failed; "
                "continuing without architecture context"
            )

            open_llm_circuit_from_error(
                state,
                error=exc,
                trigger_stage="technical_context_extraction",
            )

            record_runtime_notice(
                state,
                stage="technical_context_extraction",
                error=exc,
                degraded=True,
            )

            return None

    def assess_integration(
        self,
        state: SummaryState,
        decision: DecisionCase,
        technical_context: TechnicalContext | None,
    ) -> list[IntegrationAssessment]:
        """Assess candidate architecture fit as optional enrichment."""

        assessor = getattr(
            self,
            "integration_assessor",
            None,
        )

        if assessor is None:
            return []

        if is_llm_circuit_open(state):
            record_circuit_skip(
                state,
                stage="integration_assessment",
            )
            return []

        try:
            return assessor.assess(
                state,
                decision,
                technical_context,
            )
        except Exception as exc:
            logger.exception(
                "Integration assessment failed; "
                "continuing without architecture assessment"
            )

            open_llm_circuit_from_error(
                state,
                error=exc,
                trigger_stage="integration_assessment",
            )

            record_runtime_notice(
                state,
                stage="integration_assessment",
                error=exc,
                degraded=True,
            )

            return []

    def execute_decision_intelligence(
        self,
        state: SummaryState,
        *,
        constraint_results: dict[str, dict[str, bool]] | None = None,
        research_budget: ResearchBudget | None = None,
        research_usage: ResearchUsage | None = None,
    ) -> SummaryState:
        """
        Run the complete V3 decision-intelligence enrichment pass.

        This method assumes research evidence has already been collected.
        If no DecisionCase is attached, the research state is returned
        unchanged.

        Semantic interpretation is optional enrichment: if it fails, the
        conservative neutral evidence proposals are preserved so the
        decision pipeline remains incomplete rather than inventing scores.
        """

        decision = state.decision_case

        if decision is None:
            return state

        usage = (
            research_usage
            or state.research_usage
            or ResearchUsage()
        )
        state.research_usage = usage

        semantic_calls_before = getattr(
            getattr(
                self,
                "semantic_signal_extractor",
                None,
            ),
            "llm_call_count",
            0,
        )

        context_extractor = getattr(
            self,
            "technical_context_extractor",
            None,
        )

        context_calls_before = getattr(
            context_extractor,
            "llm_call_count",
            0,
        )

        integration_assessor = getattr(
            self,
            "integration_assessor",
            None,
        )

        integration_calls_before = getattr(
            integration_assessor,
            "llm_call_count",
            0,
        )

        constraint_calls_before = getattr(
            getattr(
                self,
                "constraint_resolver",
                None,
            ),
            "llm_call_count",
            0,
        )

        assessments = build_evidence_assessments(
            state,
            decision,
        )
        state.evidence_assessments = assessments

        previous_signals = list(
            state.evidence_signals
        )

        proposals = build_evidence_signals(
            state,
            decision,
        )

        reusable_signals, pending_proposals = (
            partition_semantic_proposals(
                proposals,
                previous_signals,
            )
        )

        try:
            if (
                pending_proposals
                and is_llm_circuit_open(state)
            ):
                record_circuit_skip(
                    state,
                    stage="semantic_signal_extraction",
                )
                newly_interpreted = []
            else:
                newly_interpreted = (
                    self.extract_semantic_signals(
                        state,
                        decision,
                        pending_proposals,
                    )
                    if pending_proposals
                    else []
                )
        except Exception as exc:
            logger.exception(
                "Semantic signal extraction failed; "
                "preserving reusable semantics and "
                "conservative neutral proposals"
            )

            open_llm_circuit_from_error(
                state,
                error=exc,
                trigger_stage="semantic_signal_extraction",
            )

            record_runtime_notice(
                state,
                stage="semantic_signal_extraction",
                error=exc,
                degraded=True,
            )

            newly_interpreted = []

        semantic_signals = merge_semantic_signals(
            proposals,
            reusable_signals,
            newly_interpreted,
        )

        state.evidence_signals = semantic_signals

        if constraint_results is None and decision.constraints:
            try:
                if is_llm_circuit_open(state):
                    record_circuit_skip(
                        state,
                        stage="constraint_resolution",
                    )
                    constraint_results = {}
                else:
                    constraint_results = self.constraint_resolver.resolve(
                        state,
                        decision,
                    )
            except Exception as exc:
                logger.exception(
                    "Constraint resolution failed; "
                    "preserving unresolved constraints"
                )

                open_llm_circuit_from_error(
                    state,
                    error=exc,
                    trigger_stage="constraint_resolution",
                )

                record_runtime_notice(
                    state,
                    stage="constraint_resolution",
                    error=exc,
                    degraded=True,
                )

                constraint_results = {}

        technical_context = (
            state.technical_context
        )

        if technical_context is None:
            technical_context = (
                self.extract_technical_context(
                    state,
                    decision,
                )
            )

            if technical_context is not None:
                state.technical_context = (
                    technical_context
                )

        integration_assessments = (
            self.assess_integration(
                state,
                decision,
                technical_context,
            )
        )

        integration_calls_after = getattr(
            integration_assessor,
            "llm_call_count",
            0,
        )

        context_calls_after = getattr(
            context_extractor,
            "llm_call_count",
            0,
        )

        semantic_calls_after = getattr(
            getattr(
                self,
                "semantic_signal_extractor",
                None,
            ),
            "llm_call_count",
            semantic_calls_before,
        )

        constraint_calls_after = getattr(
            getattr(
                self,
                "constraint_resolver",
                None,
            ),
            "llm_call_count",
            constraint_calls_before,
        )

        usage.semantic_llm_calls += max(
            0,
            semantic_calls_after
            - semantic_calls_before,
        )

        usage.semantic_llm_calls += max(
            0,
            context_calls_after
            - context_calls_before,
        )

        usage.semantic_llm_calls += max(
            0,
            integration_calls_after
            - integration_calls_before,
        )

        usage.constraint_llm_calls += max(
            0,
            constraint_calls_after
            - constraint_calls_before,
        )

        return self.execute_decision_pipeline(
            state,
            decision,
            constraint_results=constraint_results,
            technical_context=technical_context,
            integration_assessments=integration_assessments,
            evidence_signals=semantic_signals,
            evidence_assessments=assessments,
            research_budget=research_budget,
            research_usage=usage,
        )

    def execute_decision_pipeline(
        self,
        state: SummaryState,
        decision: DecisionCase,
        *,
        constraint_results: dict[str, dict[str, bool]] | None = None,
        technical_context: TechnicalContext | None = None,
        integration_assessments: list[IntegrationAssessment] | None = None,
        criterion_scores: list[CandidateCriterionScore] | None = None,
        evidence_signals: list[EvidenceSignal] | None = None,
        evidence_assessments: list[EvidenceAssessment] | None = None,
        research_budget: ResearchBudget | None = None,
        research_usage: ResearchUsage | None = None,
    ) -> SummaryState:
        """Execute one V3 decision-intelligence pass on an existing state."""

        return run_decision_pipeline(
            state,
            decision,
            constraint_results=constraint_results,
            technical_context=technical_context,
            integration_assessments=integration_assessments,
            criterion_scores=criterion_scores,
            evidence_signals=evidence_signals,
            evidence_assessments=evidence_assessments,
            research_budget=research_budget,
            research_usage=research_usage,
        )

    @property
    def last_state(self) -> SummaryState | None:
        """Return the most recent research state, if available."""

        return getattr(self, "_last_state", None)

    def _init_llm(self) -> HelloAgentsLLM:
        """Instantiate HelloAgentsLLM following configuration preferences."""
        llm_kwargs: dict[str, Any] = {"temperature": 0.0}

        model_id = self.config.llm_model_id or self.config.local_llm
        if model_id:
            llm_kwargs["model"] = model_id

        provider = (self.config.llm_provider or "").strip()
        if provider:
            llm_kwargs["provider"] = provider

        if provider == "ollama":
            llm_kwargs["base_url"] = self.config.sanitized_ollama_url()
            if self.config.llm_api_key:
                llm_kwargs["api_key"] = self.config.llm_api_key
            else:
                llm_kwargs["api_key"] = "ollama"
        elif provider == "lmstudio":
            llm_kwargs["base_url"] = self.config.lmstudio_base_url
            if self.config.llm_api_key:
                llm_kwargs["api_key"] = self.config.llm_api_key
        else:
            if self.config.llm_base_url:
                llm_kwargs["base_url"] = self.config.llm_base_url
            if self.config.llm_api_key:
                llm_kwargs["api_key"] = self.config.llm_api_key

        return HelloAgentsLLM(**llm_kwargs)

    def _create_tool_aware_agent(self, *, name: str, system_prompt: str) -> ToolAwareSimpleAgent:
        """Instantiate a ToolAwareSimpleAgent sharing tool registry and tracker."""
        return ToolAwareSimpleAgent(
            name=name,
            llm=self.llm,
            system_prompt=system_prompt,
            enable_tool_calling=self.tools_registry is not None,
            tool_registry=self.tools_registry,
            tool_call_listener=self._tool_tracker.record,
        )

    def _set_tool_event_sink(self, sink: Callable[[dict[str, Any]], None] | None) -> None:
        """Enable or disable immediate tool event callbacks."""
        self._tool_event_sink_enabled = sink is not None
        self._tool_tracker.set_event_sink(sink)

    def _attach_decision_case(
        self,
        state: SummaryState,
    ) -> DecisionCase | None:
        """
        Detect and attach a V3 DecisionCase without breaking research.

        Decision extraction is optional enrichment. Any extractor failure
        must degrade gracefully to the normal research workflow.
        """

        try:
            decision = self.extract_decision_case(
                state.research_topic,
            )
        except Exception as exc:
            logger.exception(
                "DecisionCase extraction failed; "
                "continuing as normal research"
            )

            record_runtime_notice(
                state,
                stage="decision_case_extraction",
                error=exc,
                degraded=True,
            )

            return None

        if decision is not None:
            state.decision_case = decision

        return decision

    def _execute_initial_tasks(
        self,
        state: SummaryState,
    ) -> None:
        """Execute initial research TODOs with bounded concurrency."""

        tasks = list(state.todo_items)

        if not tasks:
            return

        configured_workers = int(
            getattr(
                self.config,
                "max_concurrent_research_tasks",
                1,
            )
        )

        max_workers = max(
            1,
            min(
                configured_workers,
                len(tasks),
            ),
        )

        # Preserve exact serial behavior when concurrency is disabled.
        if max_workers <= 1 or len(tasks) <= 1:
            for task in tasks:
                for _ in self._execute_task(
                    state,
                    task,
                    emit_stream=False,
                ):
                    pass
            return

        task_order = {
            task.id: index
            for index, task
            in enumerate(tasks)
        }

        base_loop_count = (
            state.research_loop_count
        )

        self._parallel_context_buffer = {}
        self._parallel_loop_counts = {
            task.id: (
                base_loop_count
                + index
            )
            for index, task
            in enumerate(tasks)
        }

        def worker(
            task: TodoItem,
        ) -> None:
            for _ in self._execute_task(
                state,
                task,
                emit_stream=False,
            ):
                pass

        try:
            with ThreadPoolExecutor(
                max_workers=max_workers,
                thread_name_prefix=(
                    "research-task"
                ),
            ) as executor:
                future_to_task = {
                    executor.submit(
                        worker,
                        task,
                    ): task
                    for task in tasks
                }

                for future in as_completed(
                    future_to_task
                ):
                    task = (
                        future_to_task[
                            future
                        ]
                    )

                    try:
                        future.result()
                    except Exception as exc:
                        # _execute_task already records the failed task
                        # and trace. Isolate failure so independent tasks
                        # can still complete.
                        logger.exception(
                            (
                                "Initial research task %s "
                                "failed independently"
                            ),
                            task.id,
                            exc_info=exc,
                        )

            self._merge_parallel_task_state(
                state,
                tasks,
                task_order,
            )

        finally:
            self._parallel_context_buffer = None
            self._parallel_loop_counts = None

    def _merge_parallel_task_state(
        self,
        state: SummaryState,
        tasks: list[TodoItem],
        task_order: dict[int, int],
    ) -> None:
        """Restore deterministic task ordering after parallel execution."""

        fallback_order = len(
            task_order
        )

        with self._state_lock:
            context_buffer = (
                self._parallel_context_buffer
                or {}
            )

            for task in tasks:
                buffered = (
                    context_buffer.get(
                        task.id
                    )
                )

                if buffered is None:
                    continue

                (
                    context,
                    sources_summary,
                ) = buffered

                state.web_research_results.append(
                    context
                )
                state.sources_gathered.append(
                    sources_summary
                )

            state.evidence_items.sort(
                key=lambda item: (
                    task_order.get(
                        item.task_id,
                        fallback_order,
                    ),
                    (
                        item.source_rank
                        if item.source_rank
                        is not None
                        else 10**9
                    ),
                    item.evidence_id,
                )
            )

            state.claims.sort(
                key=lambda item: (
                    task_order.get(
                        item.task_id,
                        fallback_order,
                    ),
                    item.claim_id,
                )
            )

            state.execution_traces.sort(
                key=lambda item: (
                    task_order.get(
                        item.task_id,
                        fallback_order,
                    ),
                    item.trace_id,
                )
            )

    def run(self, topic: str) -> SummaryStateOutput:
        """Execute the research workflow and return the final report."""
        state = SummaryState(research_topic=topic)
        self._last_state = state
        self._attach_decision_case(state)
        state.todo_items = self.planner.plan_todo_list(state)
        self._drain_tool_events(state)

        if not state.todo_items:
            logger.info("No TODO items generated; falling back to single task")
            state.todo_items = [self.planner.create_fallback_task(state)]

        self._execute_initial_tasks(
            state
        )

        if state.decision_case is not None:
            try:
                self.execute_decision_intelligence(state)

                self.execute_adaptive_decision_loop(
                    state
                )
            except Exception as exc:
                logger.exception(
                    "Decision intelligence failed; "
                    "continuing with normal report generation"
                )

                record_runtime_notice(
                    state,
                    stage="decision_intelligence",
                    error=exc,
                    degraded=True,
                )

        report = self.reporting.generate_report(state)
        self._drain_tool_events(state)
        state.structured_report = report
        state.running_summary = report
        self._persist_final_report(state, report)

        return SummaryStateOutput(
            running_summary=report,
            report_markdown=report,
            todo_items=state.todo_items,
        )

    def run_stream(self, topic: str) -> Iterator[dict[str, Any]]:
        """Execute the workflow yielding incremental progress events."""
        state = SummaryState(research_topic=topic)
        self._last_state = state
        self._attach_decision_case(state)
        logger.debug("Starting streaming research: topic=%s", topic)
        yield {"type": "status", "message": "初始化研究流程"}

        state.todo_items = self.planner.plan_todo_list(state)
        for event in self._drain_tool_events(state, step=0):
            yield event
        if not state.todo_items:
            state.todo_items = [self.planner.create_fallback_task(state)]

        channel_map: dict[int, dict[str, Any]] = {}
        for index, task in enumerate(state.todo_items, start=1):
            token = f"task_{task.id}"
            task.stream_token = token
            channel_map[task.id] = {"step": index, "token": token}

        yield {
            "type": "todo_list",
            "tasks": [self._serialize_task(t) for t in state.todo_items],
            "step": 0,
        }

        event_queue: Queue[dict[str, Any]] = Queue()

        def enqueue(
            event: dict[str, Any],
            *,
            task: TodoItem | None = None,
            step_override: int | None = None,
        ) -> None:
            payload = dict(event)
            target_task_id = payload.get("task_id")
            if task is not None:
                target_task_id = task.id
                payload["task_id"] = task.id

            channel = channel_map.get(target_task_id) if target_task_id is not None else None
            if channel:
                payload.setdefault("step", channel["step"])
                payload["stream_token"] = channel["token"]
            if step_override is not None:
                payload["step"] = step_override
            event_queue.put(payload)

        def tool_event_sink(event: dict[str, Any]) -> None:
            enqueue(event)

        self._set_tool_event_sink(tool_event_sink)

        threads: list[Thread] = []
        task_semaphore = Semaphore(2)

        def worker(task: TodoItem, step: int) -> None:
            try:
                enqueue(
                    {
                        "type": "task_status",
                        "task_id": task.id,
                        "status": "in_progress",
                        "title": task.title,
                        "intent": task.intent,
                        "note_id": task.note_id,
                        "note_path": task.note_path,
                    },
                    task=task,
                )

                for event in self._execute_task(state, task, emit_stream=True, step=step):
                    enqueue(event, task=task)
            except Exception as exc:  # pragma: no cover - defensive guardrail
                logger.exception("Task execution failed", exc_info=exc)
                enqueue(
                    {
                        "type": "task_status",
                        "task_id": task.id,
                        "status": "failed",
                        "detail": str(exc),
                        "title": task.title,
                        "intent": task.intent,
                        "note_id": task.note_id,
                        "note_path": task.note_path,
                    },
                    task=task,
                )
            finally:
                enqueue({"type": "__task_done__", "task_id": task.id})

        def limited_worker(task: TodoItem, step: int) -> None:
            with task_semaphore:
                worker(task, step)

        for task in state.todo_items:
            step = channel_map.get(task.id, {}).get("step", 0)
            thread = Thread(target=limited_worker, args=(task, step), daemon=True)
            threads.append(thread)
            thread.start()

        active_workers = len(state.todo_items)
        finished_workers = 0

        try:
            while finished_workers < active_workers:
                event = event_queue.get()
                if event.get("type") == "__task_done__":
                    finished_workers += 1
                    continue
                yield event

            while True:
                try:
                    event = event_queue.get_nowait()
                except Empty:
                    break
                if event.get("type") != "__task_done__":
                    yield event
        finally:
            self._set_tool_event_sink(None)
            for thread in threads:
                thread.join()

        if state.decision_case is not None:
            try:
                self.execute_decision_intelligence(state)

                self.execute_adaptive_decision_loop(
                    state
                )
            except Exception as exc:
                logger.exception(
                    "Decision intelligence failed during streaming; "
                    "continuing with normal report generation"
                )

                record_runtime_notice(
                    state,
                    stage="decision_intelligence",
                    error=exc,
                    degraded=True,
                    metadata={
                        "streaming": True,
                    },
                )

        report = self.reporting.generate_report(state)
        final_step = len(state.todo_items) + 1
        for event in self._drain_tool_events(state, step=final_step):
            yield event
        state.structured_report = report
        state.running_summary = report

        note_event = self._persist_final_report(state, report)
        if note_event:
            yield note_event

        yield {
            "type": "final_report",
            "report": report,
            "note_id": state.report_note_id,
            "note_path": state.report_note_path,
        }
        yield {"type": "done"}

    # ------------------------------------------------------------------
    # Execution helpers
    # ------------------------------------------------------------------
    def _emit_execution_event(
        self,
        state: SummaryState,
        *,
        trace_id: str | None = None,
        task_id: int,
        event_type: str,
        stage: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Append a runtime execution event."""

        event = ExecutionEvent(
            trace_id=trace_id or "trace_unknown",
            task_id=task_id,
            event_type=event_type,
            stage=stage,
            metadata=metadata or {},
        )

        with self._state_lock:
            state.execution_events.append(event)
            state.execution_event_history.append(event)

    def _drain_execution_events(
        self,
        state: SummaryState,
    ) -> list[dict[str, Any]]:
        """Convert stored execution events into stream events."""

        with self._state_lock:
            events = list(state.execution_events)
            state.execution_events.clear()

        return [
            {
                "type": "execution_event",
                "schema_version": event.schema_version,
                "event_id": event.event_id,
                "trace_id": event.trace_id,
                "timestamp": event.timestamp,
                "task_id": event.task_id,
                "event_type": event.event_type,
                "stage": event.stage,
                "metadata": event.metadata,
            }
            for event in events
        ]

    def get_execution_events(
        self,
        state: SummaryState,
        *,
        trace_id: str | None = None,
        task_id: int | None = None,
        event_type: str | None = None,
    ) -> list[ExecutionEvent]:
        """Query execution event history with optional filters."""

        return self._get_execution_trace_service().get_events(
            state,
            trace_id=trace_id,
            task_id=task_id,
            event_type=event_type,
        )

    def _get_execution_trace_service(self) -> ExecutionTraceService:
        """Return the trace service, creating it for lightweight test agents."""

        service = getattr(self, "_execution_trace_service", None)

        if service is None:
            service = ExecutionTraceService(
                lock=self._state_lock,
            )
            self._execution_trace_service = service

        return service

    def get_execution_trace(
        self,
        state: SummaryState,
        trace_id: str,
    ) -> dict[str, Any]:
        """Retrieve one execution trace together with related events."""

        return self._get_execution_trace_service().get_trace(
            state,
            trace_id,
        )

    def serialize_execution_trace(
        self,
        state: SummaryState,
        trace_id: str,
    ) -> dict[str, Any]:
        """Serialize execution trace and events into JSON-compatible data."""

        return self._get_execution_trace_service().serialize_trace(
            state,
            trace_id,
        )

    def get_execution_event_summary(
        self,
        state: SummaryState,
    ) -> dict[str, Any]:
        """Summarize execution event history."""

        return self._get_execution_trace_service().summarize_events(
            state,
        )

    def execute_prepared_reevaluation(
        self,
        state: SummaryState,
        preparation: ReevaluationPreparation,
        *,
        max_tasks_per_iteration: int = 3,
    ) -> SummaryState:
        """
        Activate and execute an already-prepared re-evaluation.

        Preparation remains authoritative for whether adaptive
        research may be reopened.

        BLOCKED / UNKNOWN / otherwise non-eligible preparation
        is a complete execution no-op.
        """

        reactivation = preparation.reactivation

        if (
            reactivation.status != "ELIGIBLE"
            or not reactivation.eligible
            or not reactivation.actionable_gap_ids
        ):
            return state

        activate_prepared_reevaluation(
            state,
            preparation,
        )

        stopping = state.stopping_decision

        if (
            stopping is None
            or not stopping.should_continue
        ):
            return state

        return self.execute_adaptive_decision_loop(
            state,
            max_tasks_per_iteration=(
                max_tasks_per_iteration
            ),
        )


    def execute_adaptive_decision_loop(
        self,
        state: SummaryState,
        *,
        max_tasks_per_iteration: int = 3,
    ) -> SummaryState:
        """
        Run bounded adaptive decision research using the existing
        follow-up executor and decision-intelligence pass.
        """

        return run_adaptive_decision_loop(
            state,
            execute_followups=self.execute_adaptive_followups,
            execute_decision_intelligence=(
                self.execute_decision_intelligence
            ),
            max_tasks_per_iteration=max_tasks_per_iteration,
        )

    def execute_adaptive_followups(
        self,
        state: SummaryState,
        analysis: ResearchAnalysis,
        adaptive_state: AdaptiveResearchState,
        *,
        max_tasks: int = 3,
    ) -> AdaptiveResearchIteration | None:
        """
        Execute one adaptive follow-up research iteration.

        ResearchGap planning is delegated to the Phase 12 adaptive
        planner. Actual research reuses the existing TodoItem executor.
        """

        starting_task_id = max(
            (
                task.id
                for task in state.todo_items
            ),
            default=0,
        )

        iteration, tasks = plan_adaptive_iteration(
            analysis,
            adaptive_state,
            starting_task_id=starting_task_id,
            max_tasks=max_tasks,
            research_budget=state.research_budget,
            research_usage=state.research_usage,
        )

        if iteration is None:
            return None

        selected_gap_ids = set(
            iteration.gap_ids
        )

        selected_gaps = [
            gap
            for gap in analysis.research_gaps
            if gap.gap_id in selected_gap_ids
        ]

        record_iteration_started(
            adaptive_state,
            iteration,
            selected_gaps,
        )

        state.todo_items.extend(tasks)

        success = True

        try:
            for task in tasks:
                for _ in self._execute_task(
                    state,
                    task,
                    emit_stream=False,
                ):
                    pass

                if task.status == "failed":
                    success = False

        except Exception:
            success = False
            record_iteration_finished(
                adaptive_state,
                iteration,
                success=False,
            )
            raise

        record_iteration_finished(
            adaptive_state,
            iteration,
            success=success,
        )

        return iteration


    def _get_research_tool_registry(
        self,
    ) -> RuntimeToolRegistry:
        """Return the per-agent research Tool Runtime.

        Some tests and compatibility paths construct DeepResearchAgent
        through __new__ without running __init__. Keep runtime
        infrastructure lazily recoverable, just like other observability
        services.
        """

        registry = getattr(
            self,
            "_research_tool_registry",
            None,
        )

        if registry is None:
            registry = RuntimeToolRegistry()

            self._research_tool_registry = (
                registry
            )

            self._register_research_runtime_tools()

        return registry

    def _register_research_runtime_tools(
        self,
    ) -> None:
        """Register tools used by the real research pipeline."""

        registry = getattr(
            self,
            "_research_tool_registry",
            None,
        )

        if registry is None:
            registry = RuntimeToolRegistry()
            self._research_tool_registry = registry

        # Registration is intentionally idempotent for lazy compatibility.
        if registry.get("web_search") is not None:
            return

        registry.register(
            definition=ToolDefinition(
                name="web_search",
                description=(
                    "Execute the configured research search backend."
                ),
                parameters=[
                    ToolParameter(
                        name="query",
                        type="string",
                        required=True,
                        description="Research query",
                    ),
                    ToolParameter(
                        name="loop_count",
                        type="integer",
                        required=True,
                        description=(
                            "Current research loop count"
                        ),
                    ),
                ],
                source="search",
                read_only=True,
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                        },
                        "loop_count": {
                            "type": "integer",
                            "minimum": 0,
                        },
                    },
                    "required": [
                        "query",
                        "loop_count",
                    ],
                },
            ),
            handler=self._run_research_search_tool,
        )

    def _run_research_search_tool(
        self,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        """Bridge the existing dispatch_search contract into Tool Runtime."""

        (
            search_result,
            notices,
            answer_text,
            backend,
        ) = dispatch_search(
            str(arguments["query"]),
            self.config,
            int(arguments["loop_count"]),
        )

        return {
            "search_result": search_result,
            "notices": list(notices),
            "answer_text": answer_text,
            "backend": backend,
        }

    def _invoke_research_search_tool(
        self,
        state: SummaryState,
        *,
        query: str,
        loop_count: int,
    ) -> tuple[
        dict[str, Any] | None,
        list[str],
        str | None,
        str,
    ]:
        """Execute real research search through the unified Tool Runtime."""

        registry = (
            self._get_research_tool_registry()
        )

        result = registry.invoke(
            ToolInvocation(
                tool_name="web_search",
                arguments={
                    "query": query,
                    "loop_count": loop_count,
                },
            )
        )

        persisted_trace = (
            serialize_tool_trace_for_persistence(
                result.trace
            )
        )

        if persisted_trace is not None:
            with self._state_lock:
                state.tool_execution_traces.append(
                    persisted_trace
                )

        if result.status != TOOL_SUCCESS:
            # Preserve the existing executor error taxonomy when the
            # runtime captured an original provider/bridge exception.
            # ToolResult remains the structured observability boundary,
            # while callers still see the original exception semantics.
            if result.exception is not None:
                raise result.exception

            raise RuntimeError(
                "Research search tool failed: "
                f"{result.error_type or result.status}: "
                f"{result.error_message or 'unknown error'}"
            )

        output = result.output

        if not isinstance(output, dict):
            raise RuntimeError(
                "Research search tool returned malformed output"
            )

        return (
            output.get("search_result"),
            list(output.get("notices") or []),
            output.get("answer_text"),
            str(output.get("backend") or "unknown"),
        )

    def _finish_execution_trace(
        self,
        trace: ExecutionTrace,
        *,
        status: str,
        started_counter: float,
        error: Exception | None = None,
    ) -> None:
        """Finalize an execution trace with timing and optional error details."""

        trace.status = status
        trace.finished_at = datetime.now(timezone.utc).isoformat()
        trace.duration_ms = (perf_counter() - started_counter) * 1000

        if error is None:
            trace.error_type = None
            trace.error_message = None
        else:
            trace.error_type = classify_execution_error(error)
            trace.error_message = str(error)

    def _execute_task(
        self,
        state: SummaryState,
        task: TodoItem,
        *,
        emit_stream: bool,
        step: int | None = None,
    ) -> Iterator[dict[str, Any]]:
        """Run search + summarization for a single task."""
        task.status = "in_progress"

        started_at = datetime.now(timezone.utc)
        started_counter = perf_counter()
        trace = ExecutionTrace(
            task_id=task.id,
            status="running",
            started_at=started_at.isoformat(),
            current_stage="search",
        )

        with self._state_lock:
            state.execution_traces.append(trace)

        self._emit_execution_event(
            state,
            trace_id=trace.trace_id,
            task_id=task.id,
            event_type="task_started",
            stage="executor",
        )

        try:
            self._emit_execution_event(
                state,
                trace_id=trace.trace_id,
                task_id=task.id,
                event_type="search_started",
                stage="search",
            )

            parallel_loop_counts = getattr(
                self,
                "_parallel_loop_counts",
                None,
            )

            search_loop_count = (
                parallel_loop_counts.get(
                    task.id,
                    state.research_loop_count,
                )
                if parallel_loop_counts is not None
                else state.research_loop_count
            )

            (
                search_result,
                notices,
                answer_text,
                backend,
            ) = self._invoke_research_search_tool(
                state,
                query=task.query,
                loop_count=search_loop_count,
            )

            self._emit_execution_event(
                state,
                trace_id=trace.trace_id,
                task_id=task.id,
                event_type="search_finished",
                stage="search",
                metadata={
                    "backend": backend,
                    "sources": len(
                        search_result.get("results", [])
                    )
                    if search_result
                    else 0,
                    "degraded": bool(
                        search_result.get("degraded")
                    )
                    if search_result
                    else False,
                    "notice_count": len(notices),
                },
            )
        except Exception as exc:
            task.status = "failed"

            self._emit_execution_event(
                state,
                trace_id=trace.trace_id,
                task_id=task.id,
                event_type="task_failed",
                stage="search",
                metadata={
                    "error_type": classify_execution_error(exc),
                },
            )

            self._finish_execution_trace(
                trace,
                status="failed",
                started_counter=started_counter,
                error=exc,
            )
            raise
        self._last_search_notices = notices
        task.notices = notices

        if emit_stream:
            for event in self._drain_execution_events(state):
                yield event

            for event in self._drain_tool_events(state, step=step):
                yield event
        else:
            self._drain_tool_events(state)

        if notices and emit_stream:
            for notice in notices:
                if notice:
                    yield {
                        "type": "status",
                        "message": notice,
                        "task_id": task.id,
                        "step": step,
                    }

        if not search_result or not search_result.get("results"):
            task.status = "skipped"

            self._emit_execution_event(
                state,
                trace_id=trace.trace_id,
                task_id=task.id,
                event_type="task_skipped",
                stage="search",
                metadata={
                    "reason": "empty_search_result",
                },
            )

            self._finish_execution_trace(
                trace,
                status="skipped",
                started_counter=started_counter,
            )

            if emit_stream:
                for event in self._drain_tool_events(state, step=step):
                    yield event
                yield {
                    "type": "task_status",
                    "task_id": task.id,
                    "status": "skipped",
                    "title": task.title,
                    "intent": task.intent,
                    "note_id": task.note_id,
                    "note_path": task.note_path,
                    "step": step,
                }
            else:
                self._drain_tool_events(state)
            return
        else:
            if not emit_stream:
                self._drain_tool_events(state)

        evidence_items = extract_evidence(
            search_result,
            task_id=task.id,
            trace_id=trace.trace_id,
            query=task.query,
            backend=backend,
        )

        with self._state_lock:
            state.evidence_items.extend(evidence_items)

        sources_summary, context = prepare_research_context(
            search_result,
            answer_text,
            self.config,
        )

        task.sources_summary = sources_summary

        with self._state_lock:
            parallel_context_buffer = getattr(
                self,
                "_parallel_context_buffer",
                None,
            )

            if parallel_context_buffer is None:
                state.web_research_results.append(
                    context
                )
                state.sources_gathered.append(
                    sources_summary
                )
            else:
                parallel_context_buffer[
                    task.id
                ] = (
                    context,
                    sources_summary,
                )

            state.research_loop_count += 1

        summary_text: str | None = None
        trace.current_stage = "summarization"

        if is_llm_circuit_open(state):
            task.status = "partial"

            if (
                "summarization_skipped:llm_circuit_open"
                not in task.notices
            ):
                task.notices.append(
                    "summarization_skipped:"
                    "llm_circuit_open"
                )

            task.summary = (
                "暂无可用信息：检索已完成并保留了来源与证据，"
                "但本次研究运行的 LLM circuit 已打开，"
                "因此跳过任务总结。"
            )

            record_circuit_skip(
                state,
                stage="task_summarization",
            )

            self._emit_execution_event(
                state,
                trace_id=trace.trace_id,
                task_id=task.id,
                event_type="task_partial",
                stage="summarization",
                metadata={
                    "error_type": "llm_circuit_open",
                    "evidence_preserved": len(
                        evidence_items
                    ),
                    "sources_preserved": bool(
                        sources_summary
                    ),
                    "llm_call_skipped": True,
                },
            )

            self._finish_execution_trace(
                trace,
                status="partial",
                started_counter=started_counter,
            )

            if emit_stream:
                for event in self._drain_execution_events(
                    state
                ):
                    yield event

                yield {
                    "type": "task_status",
                    "task_id": task.id,
                    "status": "partial",
                    "title": task.title,
                    "intent": task.intent,
                    "note_id": task.note_id,
                    "note_path": task.note_path,
                    "step": step,
                    "error_type": "llm_circuit_open",
                }

            return

        self._emit_execution_event(
            state,
            trace_id=trace.trace_id,
            task_id=task.id,
            event_type="summarization_started",
            stage="summarization",
        )

        try:
            if emit_stream:
                for event in self._drain_tool_events(state, step=step):
                    yield event
                yield {
                    "type": "sources",
                    "task_id": task.id,
                    "latest_sources": sources_summary,
                    "raw_context": context,
                    "step": step,
                    "backend": backend,
                    "note_id": task.note_id,
                    "note_path": task.note_path,
                }

                summary_stream, summary_getter = self.summarizer.stream_task_summary(state, task, context)
                try:
                    for event in self._drain_tool_events(state, step=step):
                        yield event
                    chunk_buffer = ""
                    chunk_size = 160

                    for chunk in summary_stream:
                        if chunk:
                            chunk_buffer += chunk

                        while len(chunk_buffer) >= chunk_size:
                            content = chunk_buffer[:chunk_size]
                            chunk_buffer = chunk_buffer[chunk_size:]

                            yield {
                                "type": "task_summary_chunk",
                                "task_id": task.id,
                                "content": content,
                                "note_id": task.note_id,
                                "step": step,
                            }

                        for event in self._drain_tool_events(state, step=step):
                            yield event

                    # 模型流结束后发送不足 chunk_size 的剩余内容
                    if chunk_buffer:
                        yield {
                            "type": "task_summary_chunk",
                            "task_id": task.id,
                            "content": chunk_buffer,
                            "note_id": task.note_id,
                            "step": step,
                        }
                finally:
                    summary_text = summary_getter()
            else:
                summary_text = self.summarizer.summarize_task(state, task, context)
                self._drain_tool_events(state)

            if not self.summarizer.is_valid_summary(summary_text):
                logger.warning(
                    "Invalid task summary detected; retrying once: task_id=%s",
                    task.id,
                )
                summary_text = self.summarizer.summarize_task(state, task, context)

            if self.summarizer.is_valid_summary(summary_text):
                task.summary = summary_text.strip()
            else:
                task.summary = "暂无可用信息：模型未返回有效的任务总结。"
        except Exception as exc:
            # Retrieval already succeeded and evidence/source context has
            # already been persisted. A summarization-provider failure must
            # therefore be represented as PARTIAL rather than as a failed
            # research task.
            error_type = classify_execution_error(
                exc
            )

            open_llm_circuit_from_error(
                state,
                error=exc,
                trigger_stage="task_summarization",
            )

            task.status = "partial"

            notice = (
                "summarization_failed:"
                f"{error_type}"
            )

            if notice not in task.notices:
                task.notices.append(notice)

            task.summary = (
                "暂无可用信息：检索已完成并保留了来源与证据，"
                "但任务总结模型暂时不可用。"
            )

            self._emit_execution_event(
                state,
                trace_id=trace.trace_id,
                task_id=task.id,
                event_type="task_partial",
                stage="summarization",
                metadata={
                    "error_type": error_type,
                    "evidence_preserved": len(
                        evidence_items
                    ),
                    "sources_preserved": bool(
                        sources_summary
                    ),
                },
            )

            self._finish_execution_trace(
                trace,
                status="partial",
                started_counter=started_counter,
                error=exc,
            )

            if emit_stream:
                for event in self._drain_execution_events(
                    state
                ):
                    yield event

                for event in self._drain_tool_events(
                    state,
                    step=step,
                ):
                    yield event

                yield {
                    "type": "task_status",
                    "task_id": task.id,
                    "status": "partial",
                    "title": task.title,
                    "intent": task.intent,
                    "note_id": task.note_id,
                    "note_path": task.note_path,
                    "step": step,
                    "error_type": error_type,
                }
            else:
                self._drain_tool_events(state)

            # Do not create a Claim from the fallback status text. Existing
            # Evidence remains available to downstream deterministic
            # decision intelligence.
            return


        evidence_ids = [
            evidence.evidence_id
            for evidence in state.evidence_items
            if evidence.task_id == task.id
            and evidence.trace_id == trace.trace_id
        ]

        claim = Claim(
            task_id=task.id,
            trace_id=trace.trace_id,
            text=task.summary or "",
            evidence_ids=evidence_ids,
        )

        with self._state_lock:
            state.claims.append(claim)

        task.status = "completed"
        self._finish_execution_trace(
            trace,
            status="completed",
            started_counter=started_counter,
        )

        self._emit_execution_event(
            state,
            trace_id=trace.trace_id,
            task_id=task.id,
            event_type="task_completed",
            stage="executor",
            metadata={
                "status": task.status,
            },
        )

        if emit_stream:
            for event in self._drain_tool_events(state, step=step):
                yield event
            yield {
                "type": "task_status",
                "task_id": task.id,
                "status": "completed",
                "summary": task.summary,
                "sources_summary": task.sources_summary,
                "note_id": task.note_id,
                "note_path": task.note_path,
                "step": step,
            }
        else:
            self._drain_tool_events(state)

    def _drain_tool_events(
        self,
        state: SummaryState,
        *,
        step: int | None = None,
    ) -> list[dict[str, Any]]:
        """Proxy to the shared tool call tracker."""
        events = self._tool_tracker.drain(state, step=step)
        if self._tool_event_sink_enabled:
            return []
        return events

    @property
    def _tool_call_events(self) -> list[dict[str, Any]]:
        """Expose recorded tool events for legacy integrations."""
        return self._tool_tracker.as_dicts()

    def _serialize_task(self, task: TodoItem) -> dict[str, Any]:
        """Convert task dataclass to serializable dict for frontend."""
        return {
            "id": task.id,
            "title": task.title,
            "intent": task.intent,
            "query": task.query,
            "status": task.status,
            "summary": task.summary,
            "sources_summary": task.sources_summary,
            "note_id": task.note_id,
            "note_path": task.note_path,
            "stream_token": task.stream_token,
        }

    def _persist_final_report(self, state: SummaryState, report: str) -> dict[str, Any] | None:
        if not self.note_tool or not report or not report.strip():
            return None

        note_title = f"研究报告：{state.research_topic}".strip() or "研究报告"
        tags = ["deep_research", "report"]
        content = report.strip()

        note_id = self._find_existing_report_note_id(state)
        response = ""

        if note_id:
            response = self.note_tool.run(
                {
                    "action": "update",
                    "note_id": note_id,
                    "title": note_title,
                    "note_type": "conclusion",
                    "tags": tags,
                    "content": content,
                }
            )
            if response.startswith("❌"):
                note_id = None

        if not note_id:
            response = self.note_tool.run(
                {
                    "action": "create",
                    "title": note_title,
                    "note_type": "conclusion",
                    "tags": tags,
                    "content": content,
                }
            )
            note_id = self._extract_note_id_from_text(response)

        if not note_id:
            return None

        state.report_note_id = note_id
        if self.config.notes_workspace:
            note_path = Path(self.config.notes_workspace) / f"{note_id}.md"
            state.report_note_path = str(note_path)
        else:
            note_path = None

        payload = {
            "type": "report_note",
            "note_id": note_id,
            "title": note_title,
            "content": content,
        }
        if note_path:
            payload["note_path"] = str(note_path)

        return payload

    def _find_existing_report_note_id(self, state: SummaryState) -> str | None:
        if state.report_note_id:
            return state.report_note_id

        for event in reversed(self._tool_tracker.as_dicts()):
            if event.get("tool") != "note":
                continue

            parameters = event.get("parsed_parameters") or {}
            if not isinstance(parameters, dict):
                continue

            action = parameters.get("action")
            if action not in {"create", "update"}:
                continue

            note_type = parameters.get("note_type")
            if note_type != "conclusion":
                title = parameters.get("title")
                if not (isinstance(title, str) and title.startswith("研究报告")):
                    continue

            note_id = parameters.get("note_id")
            if not note_id:
                note_id = self._tool_tracker._extract_note_id(event.get("result", ""))  # type: ignore[attr-defined]

            if note_id:
                return note_id

        return None

    @staticmethod
    def _extract_note_id_from_text(response: str) -> str | None:
        if not response:
            return None

        match = re.search(r"ID:\s*([^\n]+)", response)
        if not match:
            return None

        return match.group(1).strip()


def run_deep_research(topic: str, config: Configuration | None = None) -> SummaryStateOutput:
    """Convenience function mirroring the class-based API."""
    agent = DeepResearchAgent(config=config)
    return agent.run(topic)
