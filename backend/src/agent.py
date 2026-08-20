"""Orchestrator coordinating the deep research workflow."""

from __future__ import annotations

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
    SummaryState,
    SummaryStateOutput,
    TodoItem,
)
from services.constraint_resolver import ConstraintResolver
from services.decision_case_extractor import DecisionCaseExtractor
from services.decision_input_builder import (
    build_evidence_assessments,
    build_evidence_signals,
)
from services.decision_pipeline import run_decision_pipeline
from services.execution_errors import classify_execution_error
from services.execution_trace import ExecutionTraceService
from services.adaptive_research import (
    plan_adaptive_iteration,
    record_iteration_finished,
    record_iteration_started,
    select_research_gaps,
)
from services.planner import PlanningService
from services.semantic_signal_extractor import SemanticSignalExtractor
from services.reporter import ReportingService
from services.search import dispatch_search, extract_evidence, prepare_research_context
from services.summarizer import SummarizationService
from services.tool_events import ToolCallTracker

logger = logging.getLogger(__name__)


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

        self.constraint_resolver = ConstraintResolver(
            self.constraint_resolution_agent,
            self.config,
        )
        self._last_search_notices: list[str] = []

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

        assessments = build_evidence_assessments(
            state,
            decision,
        )
        state.evidence_assessments = assessments

        proposals = build_evidence_signals(
            state,
            decision,
        )

        try:
            semantic_signals = self.extract_semantic_signals(
                state,
                decision,
                proposals,
            )
        except Exception:
            logger.exception(
                "Semantic signal extraction failed; "
                "using conservative neutral proposals"
            )
            semantic_signals = proposals

        state.evidence_signals = semantic_signals

        if constraint_results is None and decision.constraints:
            try:
                constraint_results = self.constraint_resolver.resolve(
                    state,
                    decision,
                )
            except Exception:
                logger.exception(
                    "Constraint resolution failed; "
                    "preserving unresolved constraints"
                )
                constraint_results = {}

        return self.execute_decision_pipeline(
            state,
            decision,
            constraint_results=constraint_results,
            evidence_signals=semantic_signals,
            evidence_assessments=assessments,
            research_budget=research_budget,
            research_usage=research_usage,
        )

    def execute_decision_pipeline(
        self,
        state: SummaryState,
        decision: DecisionCase,
        *,
        constraint_results: dict[str, dict[str, bool]] | None = None,
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
        except Exception:
            logger.exception(
                "DecisionCase extraction failed; "
                "continuing as normal research"
            )
            return None

        if decision is not None:
            state.decision_case = decision

        return decision

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

        for task in state.todo_items:
            for _ in self._execute_task(state, task, emit_stream=False):
                pass

        if state.decision_case is not None:
            try:
                self.execute_decision_intelligence(state)
            except Exception:
                logger.exception(
                    "Decision intelligence failed; "
                    "continuing with normal report generation"
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
            except Exception:
                logger.exception(
                    "Decision intelligence failed during streaming; "
                    "continuing with normal report generation"
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

            search_result, notices, answer_text, backend = dispatch_search(
                task.query,
                self.config,
                state.research_loop_count,
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
            state.web_research_results.append(context)
            state.sources_gathered.append(sources_summary)
            state.research_loop_count += 1

        summary_text: str | None = None
        trace.current_stage = "summarization"

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
            task.status = "failed"

            self._emit_execution_event(
                state,
                trace_id=trace.trace_id,
                task_id=task.id,
                event_type="task_failed",
                stage="summarization",
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
