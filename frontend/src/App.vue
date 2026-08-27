<template>
  <main class="app-shell" :class="{ expanded: isExpanded }">
    <div class="aurora" aria-hidden="true">
      <span></span>
      <span></span>
      <span></span>
    </div>

    <!-- 初始状态：居中输入卡片 -->
    <div v-if="!isExpanded" class="layout layout-centered">
      <section class="panel panel-form panel-centered">
        <header class="panel-head">
          <div class="logo">
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <path
                d="M12 2.5c-.7 0-1.4.2-2 .6L4.6 7C3.6 7.6 3 8.7 3 9.9v4.2c0 1.2.6 2.3 1.6 2.9l5.4 3.9c1.2.8 2.8.8 4 0l5.4-3.9c1-.7 1.6-1.7 1.6-2.9V9.9c0-1.2-.6-2.3-1.6-2.9L14 3.1a3.6 3.6 0 0 0-2-.6Z"
              />
            </svg>
          </div>
          <div>
            <h1>深度研究助手</h1>
            <p>结合多轮智能检索与总结，实时呈现洞见与引用。</p>
          </div>
        </header>

        <form class="form" @submit.prevent="handleSubmit">
          <label class="field">
            <span>研究主题</span>
            <textarea
              v-model="form.topic"
              placeholder="例如：探索多模态模型在 2025 年的关键突破"
              rows="4"
              required
            ></textarea>
          </label>

          <section class="options">
            <label class="field option">
              <span>搜索引擎</span>
              <select v-model="form.searchApi">
                <option value="">沿用后端配置</option>
                <option
                  v-for="option in searchOptions"
                  :key="option"
                  :value="option"
                >
                  {{ option }}
                </option>
              </select>
            </label>
          </section>

          <div class="form-actions">
            <button class="submit" type="submit" :disabled="loading">
              <span class="submit-label">
                <svg
                  v-if="loading"
                  class="spinner"
                  viewBox="0 0 24 24"
                  aria-hidden="true"
                >
                  <circle cx="12" cy="12" r="9" stroke-width="3" />
                </svg>
                {{ loading ? "研究进行中..." : "开始研究" }}
              </span>
            </button>
            <button
              v-if="loading"
              type="button"
              class="secondary-btn"
              @click="cancelResearch"
            >
              取消研究
            </button>
          </div>
        </form>

        <p v-if="error" class="error-chip">
          <svg viewBox="0 0 20 20" aria-hidden="true">
            <path
              d="M10 3.2c-.3 0-.6.2-.8.5L3.4 15c-.4.7.1 1.6.8 1.6h11.6c.7 0 1.2-.9.8-1.6L10.8 3.7c-.2-.3-.5-.5-.8-.5Zm0 4.3c.4 0 .7.3.7.7v4c0 .4-.3.7-.7.7s-.7-.3-.7-.7V8.2c0-.4.3-.7.7-.7Zm0 6.6a1 1 0 1 1 0 2 1 1 0 0 1 0-2Z"
            />
          </svg>
          {{ error }}
        </p>
        <p v-else-if="loading" class="hint muted">
          正在收集线索与证据，实时进展见右侧区域。
        </p>
      </section>
    </div>

    <!-- 全屏状态：左右分栏布局 -->
    <div v-else class="layout layout-fullscreen">
      <!-- 左侧：研究信息 -->
      <aside class="sidebar">
        <div class="sidebar-header">
          <button class="back-btn" @click="goBack" :disabled="loading">
            <svg viewBox="0 0 24 24" width="20" height="20">
              <path d="M19 12H5M12 19l-7-7 7-7" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
            返回
          </button>
          <h2>🔍 深度研究助手</h2>
        </div>

        <div class="research-info">
          <div class="info-item">
            <label>研究主题</label>
            <p class="topic-display">{{ form.topic }}</p>
          </div>

          <div class="info-item" v-if="form.searchApi">
            <label>搜索引擎</label>
            <p>{{ form.searchApi }}</p>
          </div>

          <div class="info-item" v-if="totalTasks > 0">
            <label>研究进度</label>
            <div class="progress-bar">
              <div class="progress-fill" :style="{ width: `${(completedTasks / totalTasks) * 100}%` }"></div>
            </div>
            <p class="progress-text">{{ completedTasks }} / {{ totalTasks }} 任务完成</p>
          </div>
        </div>

        <div class="sidebar-actions">
          <button class="new-research-btn" @click="startNewResearch">
            <svg viewBox="0 0 24 24" width="18" height="18">
              <path d="M12 5v14M5 12h14" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round"/>
            </svg>
            开始新研究
          </button>
        </div>
      </aside>

      <!-- 右侧：研究结果 -->
      <section
        class="panel panel-result"
        v-if="todoTasks.length || reportMarkdown || progressLogs.length"
      >
        <header class="status-bar">
          <div class="status-main">
            <div class="status-chip" :class="{ active: loading }">
              <span class="dot"></span>
              {{ loading ? "研究进行中" : "研究流程完成" }}
            </div>
            <span class="status-meta">
              任务进度：{{ completedTasks }} / {{ totalTasks || todoTasks.length || 1 }}
              · 阶段记录 {{ progressLogs.length }} 条
            </span>
          </div>
          <div class="status-controls">
            <button class="secondary-btn" @click="logsCollapsed = !logsCollapsed">
              {{ logsCollapsed ? "展开流程" : "收起流程" }}
            </button>
          </div>
        </header>

        <div class="timeline-wrapper" v-show="!logsCollapsed && progressLogs.length">
          <transition-group name="timeline" tag="ul" class="timeline">
            <li v-for="(log, index) in progressLogs" :key="`${log}-${index}`">
              <span class="timeline-node"></span>
              <p>{{ log }}</p>
            </li>
          </transition-group>
        </div>

        <section
          id="research-replay"
          v-if="researchId"
          class="replay-inspector"
        >
          <header class="replay-header">
            <div>
              <p class="trace-eyebrow">Decision Intelligence</p>
              <h3>Research Replay</h3>
              <p class="replay-description">
                回放从研究任务、执行 Trace 到 Evidence 与 Claim 的完整研究过程。
              </p>
            </div>

            <button
              type="button"
              class="secondary-btn"
              :disabled="replayLoading"
              @click="researchId && loadResearchReplay(researchId)"
            >
              {{ replayLoading ? "加载中..." : "刷新 Replay" }}
            </button>
          </header>

          <p v-if="replayError" class="trace-error">
            {{ replayError }}
          </p>

          <template v-if="researchReplay">
            <div class="replay-summary-grid">
              <div class="replay-metric">
                <span>Tasks</span>
                <strong>{{ researchReplay.task_count }}</strong>
              </div>

              <div class="replay-metric">
                <span>Traces</span>
                <strong>{{ researchReplay.trace_count }}</strong>
              </div>

              <div class="replay-metric">
                <span>Claims</span>
                <strong>{{ researchReplay.claim_count }}</strong>
              </div>

              <div class="replay-metric">
                <span>Evidence</span>
                <strong>{{ researchReplay.evidence_count }}</strong>
              </div>
            </div>

            <section
              v-if="researchReplay.decision && researchReplay.decision.case"
              class="decision-panel"
            >
              <div class="decision-panel-header">
                <div>
                  <p class="trace-eyebrow">Decision Intelligence</p>
                  <h4>{{ researchReplay.decision.case.question }}</h4>
                </div>

                <span
                  v-if="researchReplay.decision.readiness"
                  class="decision-status"
                  :class="`decision-status-${researchReplay.decision.readiness.status.toLowerCase()}`"
                >
                  {{ researchReplay.decision.readiness.status }}
                </span>
              </div>

              <div
                v-if="researchReplay.decision.readiness"
                class="decision-readiness-grid"
              >
                <div class="decision-readiness-card">
                  <span>Readiness</span>
                  <strong>
                    {{
                      Math.round(
                        researchReplay.decision.readiness.overall_score * 100
                      )
                    }}%
                  </strong>
                </div>

                <div class="decision-readiness-card">
                  <span>Coverage</span>
                  <strong>
                    {{
                      Math.round(
                        researchReplay.decision.readiness.criterion_coverage * 100
                      )
                    }}%
                  </strong>
                </div>

                <div class="decision-readiness-card">
                  <span>Evidence Quality</span>
                  <strong>
                    {{
                      Math.round(
                        researchReplay.decision.readiness.evidence_quality * 100
                      )
                    }}%
                  </strong>
                </div>

                <div class="decision-readiness-card">
                  <span>Decision Margin</span>
                  <strong>
                    {{
                      Math.round(
                        researchReplay.decision.readiness.decision_margin * 100
                      )
                    }}%
                  </strong>
                </div>
              </div>

              <div class="decision-grid">
                <section class="decision-section">
                  <div class="event-section-header">
                    <h4>Candidates</h4>
                    <span>
                      {{ researchReplay.decision.case.candidates.length }}
                    </span>
                  </div>

                  <div class="decision-candidate-list">
                    <div
                      v-for="candidate in researchReplay.decision.case.candidates"
                      :key="candidate.candidate_id"
                      class="decision-candidate-card"
                    >
                      <strong>{{ candidate.name }}</strong>
                      <p v-if="candidate.description">
                        {{ candidate.description }}
                      </p>
                      <code>{{ candidate.candidate_id }}</code>
                    </div>
                  </div>
                </section>

                <section
                  v-if="
                    researchReplay.decision.comparison &&
                    (
                      researchReplay.decision.comparison.ranked_candidates?.length ||
                      researchReplay.decision.comparison.candidate_scores?.length
                    )
                  "
                  class="decision-section"
                >
                  <div class="event-section-header">
                    <h4>Ranking</h4>
                    <span>
                      {{ researchReplay.decision.comparison.status }}
                    </span>
                  </div>

                  <div class="decision-ranking-list">
                    <div
                      v-for="score in (
                        researchReplay.decision.comparison.ranked_candidates ||
                        researchReplay.decision.comparison.candidate_scores ||
                        []
                      )"
                      :key="score.candidate_id"
                      class="decision-ranking-row"
                    >
                      <span>#{{ score.rank }}</span>
                      <strong>
                        {{
                          researchReplay.decision.case.candidates.find(
                            candidate =>
                              candidate.candidate_id === score.candidate_id
                          )?.name || score.candidate_id
                        }}
                      </strong>
                      <code>{{ score.weighted_score.toFixed(2) }}</code>
                    </div>
                  </div>
                </section>

                <section
                  v-if="
                    researchReplay.decision.research_analysis?.research_gaps?.length
                  "
                  class="decision-section"
                >
                  <div class="event-section-header">
                    <h4>Research Gaps</h4>
                    <span>
                      {{
                        researchReplay.decision.research_analysis.research_gaps.length
                      }}
                    </span>
                  </div>

                  <div class="decision-gap-list">
                    <div
                      v-for="gap in researchReplay.decision.research_analysis.research_gaps"
                      :key="gap.gap_id"
                      class="decision-gap-card"
                    >
                      <div class="decision-gap-header">
                        <strong>{{ gap.gap_type }}</strong>
                        <span>
                          severity {{ Math.round(gap.severity * 100) }}%
                        </span>
                      </div>

                      <p>{{ gap.description }}</p>

                      <code v-if="gap.suggested_query">
                        {{ gap.suggested_query }}
                      </code>
                    </div>
                  </div>
                </section>
              </div>

              <div
                v-if="researchReplay.decision.stopping_decision"
                class="decision-stop-row"
              >
                <div>
                  <span>Research Status</span>
                  <strong>
                    {{
                      researchReplay.decision.stopping_decision.should_continue
                        ? "Continue Research"
                        : "Stop Research"
                    }}
                  </strong>
                </div>

                <div>
                  <span>Reason</span>
                  <strong>
                    {{ researchReplay.decision.stopping_decision.reason }}
                  </strong>
                </div>

                <div
                  v-if="researchReplay.decision.research_usage"
                >
                  <span>Adaptive Usage</span>
                  <strong>
                    {{ researchReplay.decision.research_usage.iterations }}
                    iterations /
                    {{ researchReplay.decision.research_usage.tasks }}
                    tasks
                  </strong>
                </div>

                <div
                  v-if="researchReplay.decision.research_usage"
                >
                  <span>Decision LLM Usage</span>
                  <strong>
                    {{ researchReplay.decision.research_usage.semantic_llm_calls }}
                    semantic /
                    {{ researchReplay.decision.research_usage.constraint_llm_calls }}
                    constraint calls
                  </strong>
                </div>

                <div
                  v-if="researchReplay.decision.adaptive_research_state"
                >
                  <span>Adaptive State</span>
                  <strong>
                    {{ researchReplay.decision.adaptive_research_state.status }}
                  </strong>
                </div>
              </div>

              <section
                v-if="
                  researchReplay.decision.adaptive_research_state?.iterations?.length
                "
                class="adaptive-research-iterations"
                aria-labelledby="adaptive-research-title"
              >
                <div class="adaptive-research-heading">
                  <div>
                    <p class="trace-eyebrow">
                      Adaptive Research
                    </p>
                    <h4 id="adaptive-research-title">
                      Research Journey
                    </h4>
                    <p class="adaptive-journey-description">
                      How each follow-up research iteration changed
                      the decision-relevant knowledge state.
                    </p>
                  </div>

                  <span class="adaptive-iteration-count">
                    {{
                      researchReplay.decision
                        .adaptive_research_state
                        .iterations.length
                    }}
                    iterations
                  </span>
                </div>

                <div
                  class="adaptive-journey-summary"
                  aria-label="Adaptive research journey summary"
                >
                  <div class="adaptive-journey-metric">
                    <span>Iterations</span>
                    <strong>
                      {{
                        researchReplay.decision
                          .adaptive_research_state
                          .iterations.length
                      }}
                    </strong>
                  </div>

                  <div class="adaptive-journey-metric">
                    <span>New Evidence</span>
                    <strong>
                      {{ adaptiveTotalEvidence() }}
                    </strong>
                  </div>

                  <div class="adaptive-journey-metric">
                    <span>Novel Claims</span>
                    <strong>
                      {{ adaptiveTotalNovelClaims() }}
                    </strong>
                  </div>

                  <div class="adaptive-journey-metric">
                    <span>New Coverage</span>
                    <strong>
                      {{ adaptiveTotalNewCoverage() }}
                    </strong>
                  </div>

                  <div class="adaptive-journey-metric">
                    <span>Final Value</span>
                    <strong>
                      {{
                        formatResearchStatusLabel(
                          adaptiveFinalResearchValue()
                        )
                      }}
                    </strong>
                  </div>

                  <div class="adaptive-journey-metric">
                    <span>Final Reason</span>
                    <strong>
                      {{
                        formatResearchStatusLabel(
                          adaptiveFinalStoppingReason()
                        )
                      }}
                    </strong>
                  </div>
                </div>

                <div class="adaptive-iteration-list">
                  <details
                    v-for="(iteration, index) in researchReplay.decision.adaptive_research_state.iterations"
                    :key="iteration.iteration_number"
                    class="adaptive-iteration-card"
                    :class="{
                      'adaptive-iteration-final':
                        isFinalAdaptiveIteration(index)
                    }"
                    :open="
                      researchReplay.decision
                        .adaptive_research_state
                        .iterations.length <= 2 ||
                      isFinalAdaptiveIteration(index)
                    "
                  >
                    <summary
                      class="adaptive-iteration-header"
                    >
                      <div class="adaptive-iteration-title">
                        <span
                          class="adaptive-iteration-chevron"
                          aria-hidden="true"
                        >
                          ›
                        </span>

                        <div>
                          <span
                            class="adaptive-iteration-label"
                          >
                            Iteration
                            {{ iteration.iteration_number }}
                          </span>

                          <span
                            v-if="iteration.status"
                            class="adaptive-run-status"
                          >
                            {{
                              formatResearchStatusLabel(
                                iteration.status
                              )
                            }}
                          </span>
                        </div>
                      </div>

                      <span
                        class="research-value-badge"
                        :class="`research-value-${(
                          iteration.adaptive_research_value_status ||
                          'UNKNOWN'
                        ).toLowerCase()}`"
                      >
                        {{
                          formatResearchStatusLabel(
                            iteration
                              .adaptive_research_value_status
                          )
                        }}
                      </span>
                    </summary>

                    <div class="adaptive-iteration-body">
                      <p
                        v-if="iteration.research_value_summary"
                        class="adaptive-value-summary"
                      >
                        {{ iteration.research_value_summary }}
                      </p>

                      <p
                        v-else
                        class="adaptive-value-summary adaptive-value-summary-empty"
                      >
                        No research-value explanation was recorded
                        for this iteration.
                      </p>

                      <div
                        class="adaptive-signal-grid"
                        aria-label="Research value diagnostics"
                      >
                        <div class="adaptive-signal">
                          <span>Retrieval Yield</span>
                          <strong>
                            {{
                              formatResearchStatusLabel(
                                iteration
                                  .retrieval_yield_status
                              )
                            }}
                          </strong>
                        </div>

                        <div class="adaptive-signal">
                          <span>Evidence Saturation</span>
                          <strong>
                            {{
                              formatResearchStatusLabel(
                                iteration
                                  .evidence_saturation_status
                              )
                            }}
                          </strong>
                        </div>

                        <div class="adaptive-signal">
                          <span>Information Gain</span>
                          <strong>
                            {{
                              formatResearchStatusLabel(
                                iteration
                                  .information_gain_status
                              )
                            }}
                          </strong>
                        </div>
                      </div>

                      <div
                        v-if="
                          iteration
                            .research_value_observations
                            ?.length
                        "
                        class="adaptive-observations"
                      >
                        <span class="adaptive-subheading">
                          Observed
                        </span>

                        <ul>
                          <li
                            v-for="observation in iteration.research_value_observations"
                            :key="observation"
                          >
                            {{ observation }}
                          </li>
                        </ul>
                      </div>

                      <details
                        v-if="
                          iteration
                            .research_value_explanation
                            ?.length
                        "
                        class="adaptive-explanation"
                      >
                        <summary>
                          Why this research value?
                        </summary>

                        <ul>
                          <li
                            v-for="reason in iteration.research_value_explanation"
                            :key="reason"
                          >
                            {{ reason }}
                          </li>
                        </ul>
                      </details>

                      <div
                        v-if="
                          iteration
                            .new_candidate_criterion_pairs
                            ?.length
                        "
                        class="adaptive-new-coverage"
                      >
                        <span class="adaptive-subheading">
                          New decision coverage
                        </span>

                        <div class="adaptive-pair-list">
                          <code
                            v-for="pair in iteration.new_candidate_criterion_pairs"
                            :key="pair"
                          >
                            {{ pair }}
                          </code>
                        </div>
                      </div>

                      <div
                        v-if="
                          iteration.stopping_explanation
                        "
                        class="adaptive-stopping"
                        :class="{
                          'adaptive-stopping-final':
                            isFinalAdaptiveIteration(index)
                        }"
                      >
                        <span class="adaptive-subheading">
                          {{
                            isFinalAdaptiveIteration(index)
                              ? "Final stopping decision"
                              : "Stopping state"
                          }}
                        </span>

                        <p>
                          {{
                            iteration.stopping_explanation
                          }}
                        </p>
                      </div>
                    </div>
                  </details>
                </div>
              </section>

              <div
                v-if="
                  researchReplay.decision.readiness?.blocking_reasons?.length
                "
                class="decision-blockers"
              >
                <strong>Blocking reasons</strong>
                <ul>
                  <li
                    v-for="reason in researchReplay.decision.readiness.blocking_reasons"
                    :key="reason"
                  >
                    {{ reason }}
                  </li>
                </ul>
              </div>
            </section>

            <div class="replay-layout">
              <section class="replay-task-section">
                <div class="event-section-header">
                  <h4>Research Tasks</h4>
                  <span>{{ researchReplay.tasks.length }} tasks</span>
                </div>

                <div class="replay-task-list">
                  <button
                    v-for="task in researchReplay.tasks"
                    :key="task.task_id"
                    type="button"
                    class="replay-task-card"
                    @click="openReplayTask(task)"
                  >
                    <div class="replay-task-title">
                      <span>Task {{ task.task_id }}</span>

                      <span
                        class="trace-status"
                        :class="`trace-status-${task.status}`"
                      >
                        {{ task.status }}
                      </span>
                    </div>

                    <strong>{{ task.title }}</strong>

                    <p>{{ task.intent }}</p>

                    <code>{{ task.query }}</code>

                    <div class="replay-artifact-counts">
                      <span>{{ task.trace_ids.length }} traces</span>
                      <span>{{ task.claim_ids.length }} claims</span>
                      <span>{{ task.evidence_ids.length }} evidence</span>
                    </div>
                  </button>
                </div>
              </section>

              <section class="replay-timeline-section">
                <div class="event-section-header">
                  <h4>Research Timeline</h4>
                  <span>{{ researchReplay.timeline.length }} events</span>
                </div>

                <ol
                  v-if="researchReplay.timeline.length"
                  class="replay-timeline"
                >
                  <li
                    v-for="(event, index) in researchReplay.timeline"
                    :key="`${event.reference_id || event.event_type}-${index}`"
                    class="replay-event"
                  >
                    <span class="replay-event-node"></span>

                    <button
                      type="button"
                      class="replay-event-card"
                      :class="{ clickable: !!event.trace_id }"
                      @click="openReplayEvent(event.trace_id)"
                    >
                      <div class="replay-event-header">
                        <strong>{{ event.event_type }}</strong>

                        <time>
                          {{ formatTraceTimestamp(event.timestamp) }}
                        </time>
                      </div>

                      <p v-if="event.summary">
                        {{ event.summary }}
                      </p>

                      <div class="replay-event-meta">
                        <span v-if="event.task_id !== null">
                          Task {{ event.task_id }}
                        </span>

                        <code v-if="event.reference_id">
                          {{ event.reference_id }}
                        </code>
                      </div>
                    </button>
                  </li>
                </ol>

                <p v-else class="trace-empty">
                  当前研究暂无可回放事件。
                </p>
              </section>
            </div>
          </template>

          <p
            v-else-if="!replayLoading && !replayError"
            class="trace-empty"
          >
            当前研究暂无 Replay 数据。
          </p>
        </section>

        <section
          id="trace-inspector"
          v-if="researchId"
          class="trace-inspector"
        >
          <header class="trace-inspector-header">
            <div>
              <p class="trace-eyebrow">Execution Observability</p>
              <h3>Trace Inspector</h3>
              <p class="trace-research-id">
                Research ID：{{ researchId }}
              </p>
            </div>

            <button
              type="button"
              class="secondary-btn"
              :disabled="traceLoading"
              @click="researchId && loadResearchTraces(researchId)"
            >
              {{ traceLoading ? "加载中..." : "刷新 Trace" }}
            </button>
          </header>

          <p v-if="traceError" class="trace-error">
            {{ traceError }}
          </p>

          <div
            v-if="executionTraces.length"
            class="trace-layout"
          >
            <aside class="trace-list">
              <button
                v-for="trace in executionTraces"
                :key="trace.trace_id"
                type="button"
                class="trace-list-item"
                :class="{
                  active: trace.trace_id === activeTraceId,
                  'trace-failed': trace.status === 'failed',
                  'trace-skipped': trace.status === 'skipped'
                }"
                @click="selectTrace(trace.trace_id)"
              >
                <div class="trace-list-title">
                  <span>Task {{ trace.task_id }}</span>
                  <span
                    class="trace-status"
                    :class="`trace-status-${trace.status}`"
                  >
                    {{ trace.status }}
                  </span>
                </div>

                <code>{{ trace.trace_id }}</code>

                <div class="trace-list-meta">
                  <span>{{ formatDuration(trace.duration_ms) }}</span>
                  <span>Retry {{ trace.retry_count }}</span>
                </div>

                <p
                  v-if="trace.error_type || trace.error_message"
                  class="trace-list-error"
                >
                  <strong>{{ trace.error_type || "ExecutionError" }}</strong>
                  <span v-if="trace.error_message">
                    {{ trace.error_message }}
                  </span>
                </p>
              </button>
            </aside>

            <article class="trace-detail">
              <div
                v-if="traceLoading && !activeTraceDetail"
                class="trace-empty"
              >
                正在加载执行轨迹…
              </div>

              <template v-else-if="activeTraceDetail">
                <header class="trace-detail-header">
                  <div>
                    <h4>
                      Task {{ activeTraceDetail.trace.task_id }}
                    </h4>
                    <code>
                      {{ activeTraceDetail.trace.trace_id }}
                    </code>
                  </div>

                  <span
                    class="trace-status"
                    :class="`trace-status-${activeTraceDetail.trace.status}`"
                  >
                    {{ activeTraceDetail.trace.status }}
                  </span>
                </header>

                <div class="trace-metrics">
                  <div>
                    <span>阶段</span>
                    <strong>
                      {{
                        activeTraceDetail.trace.current_stage ||
                        "—"
                      }}
                    </strong>
                  </div>

                  <div>
                    <span>耗时</span>
                    <strong>
                      {{
                        formatDuration(
                          activeTraceDetail.trace.duration_ms
                        )
                      }}
                    </strong>
                  </div>

                  <div>
                    <span>重试</span>
                    <strong>
                      {{ activeTraceDetail.trace.retry_count }}
                    </strong>
                  </div>

                  <div>
                    <span>开始</span>
                    <strong>
                      {{
                        formatTraceTimestamp(
                          activeTraceDetail.trace.started_at
                        )
                      }}
                    </strong>
                  </div>
                </div>

                <div
                  v-if="
                    activeTraceDetail.trace.error_type ||
                    activeTraceDetail.trace.error_message
                  "
                  class="trace-failure"
                >
                  <strong>
                    {{
                      activeTraceDetail.trace.error_type ||
                      "ExecutionError"
                    }}
                  </strong>
                  <p>
                    {{
                      activeTraceDetail.trace.error_message ||
                      "未提供错误详情"
                    }}
                  </p>
                </div>

                <section class="event-section">
                  <div class="event-section-header">
                    <h4>Event Timeline</h4>
                    <span>
                      {{ activeTraceDetail.events.length }} events
                    </span>
                  </div>

                  <ol
                    v-if="activeTraceDetail.events.length"
                    class="event-timeline"
                  >
                    <li
                      v-for="event in activeTraceDetail.events"
                      :key="event.event_id"
                      class="event-item"
                    >
                      <span class="event-node"></span>

                      <div class="event-card">
                        <div class="event-card-header">
                          <div>
                            <strong>{{ event.event_type }}</strong>
                            <span>{{ event.stage }}</span>
                          </div>

                          <time>
                            {{
                              formatTraceTimestamp(event.timestamp)
                            }}
                          </time>
                        </div>

                        <code>{{ event.event_id }}</code>

                        <template
                          v-if="Object.keys(event.metadata).length"
                        >
                          <div class="event-metadata-summary">
                            <span v-if="event.metadata.backend">
                              Backend: {{ event.metadata.backend }}
                            </span>
                            <span
                              v-if="
                                event.metadata.sources !== undefined
                              "
                            >
                              Sources: {{ event.metadata.sources }}
                            </span>
                            <span v-if="event.metadata.reason">
                              Reason: {{ event.metadata.reason }}
                            </span>
                            <span v-if="event.metadata.error_type">
                              Error: {{ event.metadata.error_type }}
                            </span>
                          </div>

                          <details class="event-metadata">
                            <summary>完整 Metadata</summary>
                            <pre>{{
                              formatEventMetadata(event.metadata)
                            }}</pre>
                          </details>
                        </template>
                      </div>
                    </li>
                  </ol>

                  <p v-else class="trace-empty">
                    该 Trace 暂无执行事件。
                  </p>
                </section>
              </template>

              <p v-else class="trace-empty">
                选择一个 Trace 查看执行详情。
              </p>
            </article>
          </div>

          <p
            v-else-if="!traceLoading && !traceError"
            class="trace-empty"
          >
            当前研究没有可展示的执行 Trace。
          </p>
        </section>

        <section
          id="evidence-inspector"
          v-if="researchId"
          class="evidence-inspector"
        >
          <header class="evidence-inspector-header">
            <div>
              <p class="trace-eyebrow">Evidence Grounding</p>
              <h3>Evidence Inspector</h3>
              <p class="evidence-description">
                查看任务结论以及支持该结论的检索证据。
              </p>
            </div>

            <button
              type="button"
              class="secondary-btn"
              :disabled="claimLoading"
              @click="researchId && loadResearchClaims(researchId)"
            >
              {{ claimLoading ? "加载中..." : "刷新 Evidence" }}
            </button>
          </header>

          <p v-if="claimError" class="trace-error">
            {{ claimError }}
          </p>

          <div
            v-if="researchClaims.length"
            class="evidence-layout"
          >
            <aside class="claim-list">
              <button
                v-for="claim in researchClaims"
                :key="claim.claim_id"
                type="button"
                class="claim-list-item"
                :class="{
                  active: claim.claim_id === activeClaimId
                }"
                @click="selectClaim(claim.claim_id)"
              >
                <div class="claim-list-title">
                  <span>Task {{ claim.task_id }}</span>
                  <span class="claim-evidence-count">
                    {{ claim.evidence_ids.length }} evidence
                  </span>
                </div>

                <p class="claim-preview">
                  {{ claim.text }}
                </p>

                <code>{{ claim.claim_id }}</code>
              </button>
            </aside>

            <article class="claim-detail">
              <div
                v-if="claimLoading && !activeClaimDetail"
                class="trace-empty"
              >
                正在加载 Claim 与证据…
              </div>

              <template v-else-if="activeClaimDetail">
                <header class="claim-detail-header">
                  <div>
                    <span class="claim-task-label">
                      Task {{ activeClaimDetail.claim.task_id }}
                    </span>
                    <h4>Research Claim</h4>
                  </div>

                  <span class="claim-support-count">
                    {{ activeClaimDetail.evidence.length }} supporting sources
                  </span>
                </header>

                <div class="claim-text">
                  {{ activeClaimDetail.claim.text }}
                </div>

                <div class="claim-provenance">
                  <div>
                    <span>Claim ID</span>
                    <code>{{ activeClaimDetail.claim.claim_id }}</code>
                  </div>

                  <div>
                    <span>Trace</span>
                    <button
                      type="button"
                      class="claim-trace-link"
                      @click="
                        openEvidenceTrace(
                          activeClaimDetail.claim.trace_id
                        )
                      "
                    >
                      {{ activeClaimDetail.claim.trace_id }}
                    </button>
                  </div>
                </div>

                <section class="supporting-evidence-section">
                  <div class="event-section-header">
                    <h4>Supporting Evidence</h4>
                    <span>
                      {{ activeClaimDetail.evidence.length }} sources
                    </span>
                  </div>

                  <div
                    v-if="activeClaimDetail.evidence.length"
                    class="evidence-card-list"
                  >
                    <article
                      v-for="evidence in activeClaimDetail.evidence"
                      :key="evidence.evidence_id"
                      class="evidence-card"
                    >
                      <header class="evidence-card-header">
                        <div>
                          <span class="evidence-rank">
                            #{{ evidence.source_rank ?? "—" }}
                          </span>
                          <span class="evidence-backend">
                            {{ evidence.backend }}
                          </span>
                        </div>

                        <code>{{ evidence.evidence_id }}</code>
                      </header>

                      <h5>
                        {{
                          evidence.source_title ||
                          "Untitled source"
                        }}
                      </h5>

                      <a
                        v-if="evidence.source_url"
                        class="evidence-source-link"
                        :href="evidence.source_url"
                        target="_blank"
                        rel="noopener noreferrer"
                      >
                        {{ evidence.source_url }}
                      </a>

                      <p
                        v-if="evidence.snippet"
                        class="evidence-snippet"
                      >
                        {{ evidence.snippet }}
                      </p>

                      <div class="evidence-provenance">
                        <span>
                          Query: {{ evidence.query }}
                        </span>

                        <button
                          type="button"
                          class="claim-trace-link"
                          @click="
                            openEvidenceTrace(evidence.trace_id)
                          "
                        >
                          Trace: {{ evidence.trace_id }}
                        </button>
                      </div>

                      <details
                        v-if="evidence.content"
                        class="evidence-content"
                      >
                        <summary>查看完整抓取内容</summary>
                        <pre>{{ evidence.content }}</pre>
                      </details>
                    </article>
                  </div>

                  <p v-else class="trace-empty">
                    当前 Claim 没有关联的 Supporting Evidence。
                  </p>
                </section>
              </template>

              <p v-else class="trace-empty">
                选择一个 Claim 查看证据链。
              </p>
            </article>
          </div>

          <p
            v-else-if="!claimLoading && !claimError"
            class="trace-empty"
          >
            当前研究没有可展示的 Claim。
          </p>
        </section>

        <div class="tasks-section" v-if="todoTasks.length">
          <aside class="tasks-list">
            <h3>任务清单</h3>
            <ul>
              <li
                v-for="task in todoTasks"
                :key="task.id"
                :class="['task-item', { active: task.id === activeTaskId, completed: task.status === 'completed' }]"
              >
                <button
                  type="button"
                  class="task-button"
                  @click="activeTaskId = task.id"
                >
                  <span class="task-title">{{ task.title }}</span>
                  <span class="task-status" :class="task.status">
                    {{ formatTaskStatus(task.status) }}
                  </span>
                </button>
                <p class="task-intent">{{ task.intent }}</p>

                <button
                  v-if="getTraceForTask(task.id)"
                  type="button"
                  class="task-trace-link"
                  @click.stop="openTraceForTask(task.id)"
                >
                  查看 Trace
                  <span>
                    {{ getTraceForTask(task.id)?.status }}
                  </span>
                </button>
              </li>
            </ul>
          </aside>

          <article class="task-detail" v-if="currentTask">
            <header class="task-header">
              <div>
                <h3>{{ currentTaskTitle || "当前任务" }}</h3>
                <p class="muted" v-if="currentTaskIntent">
                  {{ currentTaskIntent }}
                </p>
              </div>
              <div class="task-chip-group">
                <span class="task-label">查询：{{ currentTaskQuery || "" }}</span>
                <span
                  v-if="currentTaskNoteId"
                  class="task-label note-chip"
                  :title="currentTaskNoteId"
                >
                  笔记：{{ currentTaskNoteId }}
                </span>
                <span
                  v-if="currentTaskNotePath"
                  class="task-label note-chip path-chip"
                  :title="currentTaskNotePath"
                >
                  <span class="path-label">路径：</span>
                  <span class="path-text">{{ currentTaskNotePath }}</span>
                  <button
                    class="chip-action"
                    type="button"
                    @click="copyNotePath(currentTaskNotePath)"
                  >
                    复制
                  </button>
                </span>
              </div>
            </header>

            <section v-if="currentTask && currentTask.notices.length" class="task-notices">
              <h4>系统提示</h4>
              <ul>
                <li v-for="(notice, idx) in currentTask.notices" :key="`${notice}-${idx}`">
                  {{ notice }}
                </li>
              </ul>
            </section>

            <section
              class="sources-block"
              :class="{ 'block-highlight': sourcesHighlight }"
            >
              <h3>最新来源</h3>
              <template v-if="currentTaskSources.length">
                <ul class="sources-list">
                  <li
                    v-for="(item, index) in currentTaskSources"
                    :key="`${item.title}-${index}`"
                    class="source-item"
                  >
                    <a
                      class="source-link"
                      :href="item.url || '#'"
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      {{ item.title || item.url || `来源 ${index + 1}` }}
                    </a>
                    <div v-if="item.snippet || item.raw" class="source-tooltip">
                      <p v-if="item.snippet">{{ item.snippet }}</p>
                      <p v-if="item.raw" class="muted-text">{{ item.raw }}</p>
                    </div>
                  </li>
                </ul>
              </template>
              <p v-else class="muted">暂无可用来源</p>
            </section>

            <section
              class="summary-block"
              :class="{ 'block-highlight': summaryHighlight }"
            >
              <h3>任务总结</h3>
              <div
                class="markdown-body"
                v-html="renderMarkdown(currentTaskSummary || '暂无可用信息')"
              ></div>
            </section>

            <section
              class="tools-block"
              :class="{ 'block-highlight': toolHighlight }"
              v-if="currentTaskToolCalls.length"
            >
              <h3>工具调用记录</h3>
              <ul class="tool-list">
                <li
                  v-for="entry in currentTaskToolCalls"
                  :key="`${entry.eventId}-${entry.timestamp}`"
                >
                  <details class="tool-entry">
                    <summary class="tool-entry-summary">
                      <span class="tool-entry-title">
                        #{{ entry.eventId }} {{ entry.agent }} → {{ entry.tool }}
                      </span>
                      <span
                        v-if="entry.noteId"
                        class="tool-entry-note"
                      >
                        笔记：{{ entry.noteId }}
                      </span>
                    </summary>

                    <div class="tool-entry-content">
                      <p v-if="entry.notePath" class="tool-entry-path">
                        笔记路径：
                        <button
                          class="link-btn"
                          type="button"
                          @click.stop="copyNotePath(entry.notePath)"
                        >
                          复制
                        </button>
                        <span class="path-text">{{ entry.notePath }}</span>
                      </p>

                      <p class="tool-subtitle">参数</p>
                      <pre class="tool-pre">{{ formatToolParameters(entry.parameters) }}</pre>

                      <template v-if="entry.result">
                        <p class="tool-subtitle">执行结果</p>
                        <pre class="tool-pre">{{ formatToolResult(entry.result) }}</pre>
                      </template>
                    </div>
                  </details>
                </li>
              </ul>
            </section>
          </article>

          <article class="task-detail" v-else>
            <p class="muted">等待任务规划或执行结果。</p>
          </article>
        </div>

        <div
          v-if="reportMarkdown"
          class="report-block"
          :class="{ 'block-highlight': reportHighlight }"
        >
          <h3>最终报告</h3>
          <div
            class="markdown-body"
            v-html="renderMarkdown(reportMarkdown)"
          ></div>
        </div>
      </section>

    </div>
  </main>
</template>

<script lang="ts" setup>
import {
  getResearchClaim,
  getResearchReplay,
  getResearchTrace,
  listResearchClaims,
  listResearchTraces,
  type ClaimDetailResponse,
  type ClaimResponse,
  type ExecutionTraceResponse,
  type ResearchReplayResponse,
  type ResearchReplayTaskResponse,
  type TraceDetailResponse
} from "./services/api";
import { computed, onBeforeUnmount, reactive, ref } from "vue";
import DOMPurify from "dompurify";
import { marked } from "marked";

import {
  runResearchStream,
  type ResearchStreamEvent
} from "./services/api";

marked.setOptions({
  gfm: true,
  breaks: true
});

const renderMarkdown = (content: string): string => {
  if (!content) {
    return "";
  }

  const html = marked.parse(content) as string;
  return DOMPurify.sanitize(html);
};

interface SourceItem {
  title: string;
  url: string;
  snippet: string;
  raw: string;
}

interface ToolCallLog {
  eventId: number;
  agent: string;
  tool: string;
  parameters: Record<string, unknown>;
  result: string;
  noteId: string | null;
  notePath: string | null;
  timestamp: number;
}

interface TodoTaskView {
  id: number;
  title: string;
  intent: string;
  query: string;
  status: string;
  summary: string;
  sourcesSummary: string;
  sourceItems: SourceItem[];
  notices: string[];
  noteId: string | null;
  notePath: string | null;
  toolCalls: ToolCallLog[];
}

const form = reactive({
  topic: "",
  searchApi: ""
});

const loading = ref(false);
const error = ref("");
const progressLogs = ref<string[]>([]);
const logsCollapsed = ref(false);
const isExpanded = ref(false);

const todoTasks = ref<TodoTaskView[]>([]);
const activeTaskId = ref<number | null>(null);
const reportMarkdown = ref("");

const summaryHighlight = ref(false);
const sourcesHighlight = ref(false);
const reportHighlight = ref(false);
const toolHighlight = ref(false);

let currentController: AbortController | null = null;

const searchOptions = [
  "advanced",
  "duckduckgo",
  "tavily",
  "perplexity",
  "searxng"
];

const TASK_STATUS_LABEL: Record<string, string> = {
  pending: "待执行",
  in_progress: "进行中",
  completed: "已完成",
  skipped: "已跳过"
};

function formatTaskStatus(status: string): string {
  return TASK_STATUS_LABEL[status] ?? status;
}

const totalTasks = computed(() => todoTasks.value.length);
const completedTasks = computed(() =>
  todoTasks.value.filter((task) => task.status === "completed").length
);

const currentTask = computed(() => {
  if (activeTaskId.value !== null) {
    return todoTasks.value.find((task) => task.id === activeTaskId.value) ?? null;
  }
  return todoTasks.value[0] ?? null;
});

const currentTaskSources = computed(() => currentTask.value?.sourceItems ?? []);
const currentTaskSummary = computed(() => currentTask.value?.summary ?? "");
const currentTaskTitle = computed(() => currentTask.value?.title ?? "");
const currentTaskIntent = computed(() => currentTask.value?.intent ?? "");
const currentTaskQuery = computed(() => currentTask.value?.query ?? "");
const currentTaskNoteId = computed(() => currentTask.value?.noteId ?? "");
const currentTaskNotePath = computed(() => currentTask.value?.notePath ?? "");
const currentTaskToolCalls = computed(
  () => currentTask.value?.toolCalls ?? []
);

const pulse = (flag: typeof summaryHighlight) => {
  flag.value = false;
  requestAnimationFrame(() => {
    flag.value = true;
    window.setTimeout(() => {
      flag.value = false;
    }, 1200);
  });
};

function parseSources(raw: string): SourceItem[] {
  if (!raw) {
    return [];
  }

  const items: SourceItem[] = [];
  const lines = raw.split("\n");

  let current: SourceItem | null = null;
  const truncate = (value: string, max = 360) => {
    const trimmed = value.trim();
    return trimmed.length > max ? `${trimmed.slice(0, max)}…` : trimmed;
  };

  const flush = () => {
    if (!current) {
      return;
    }
    const normalized: SourceItem = {
      title: current.title?.trim() || "",
      url: current.url?.trim() || "",
      snippet: current.snippet ? truncate(current.snippet) : "",
      raw: current.raw ? truncate(current.raw, 420) : ""
    };

    if (
      normalized.title ||
      normalized.url ||
      normalized.snippet ||
      normalized.raw
    ) {
      if (!normalized.title && normalized.url) {
        normalized.title = normalized.url;
      }
      items.push(normalized);
    }
    current = null;
  };

  const ensureCurrent = () => {
    if (!current) {
      current = { title: "", url: "", snippet: "", raw: "" };
    }
  };

  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed) {
      continue;
    }

    if (/^\*/.test(trimmed) && trimmed.includes(" : ")) {
      flush();
      const withoutBullet = trimmed.replace(/^\*\s*/, "");
      const [titlePart, urlPart] = withoutBullet.split(" : ");
      current = {
        title: titlePart?.trim() || "",
        url: urlPart?.trim() || "",
        snippet: "",
        raw: ""
      };
      continue;
    }

    if (/^(Source|信息来源)\s*:/.test(trimmed)) {
      flush();
      const [, titlePart = ""] = trimmed.split(/:\s*(.+)/);
      current = {
        title: titlePart.trim(),
        url: "",
        snippet: "",
        raw: ""
      };
      continue;
    }

    if (/^URL\s*:/.test(trimmed)) {
      ensureCurrent();
      const [, urlPart = ""] = trimmed.split(/:\s*(.+)/);
      current!.url = urlPart.trim();
      continue;
    }

    if (
      /^(Most relevant content from source|信息内容)\s*:/.test(trimmed)
    ) {
      ensureCurrent();
      const [, contentPart = ""] = trimmed.split(/:\s*(.+)/);
      current!.snippet = contentPart.trim();
      continue;
    }

    if (
      /^(Full source content limited to|信息内容限制为)\s*:/.test(trimmed)
    ) {
      ensureCurrent();
      const [, rawPart = ""] = trimmed.split(/:\s*(.+)/);
      current!.raw = rawPart.trim();
      continue;
    }

    if (/^https?:\/\//.test(trimmed)) {
      ensureCurrent();
      if (!current!.url) {
        current!.url = trimmed;
        continue;
      }
    }

    ensureCurrent();
    current!.raw = current!.raw ? `${current!.raw}\n${trimmed}` : trimmed;
  }

  flush();
  return items;
}

function extractOptionalString(value: unknown): string | null {
  if (typeof value !== "string") {
    return null;
  }
  const trimmed = value.trim();
  return trimmed ? trimmed : null;
}

function ensureRecord(value: unknown): Record<string, unknown> {
  if (value && typeof value === "object" && !Array.isArray(value)) {
    return value as Record<string, unknown>;
  }
  return {};
}

function applyNoteMetadata(
  task: TodoTaskView,
  payload: Record<string, unknown>
): void {
  const noteId = extractOptionalString(payload.note_id);
  if (noteId) {
    task.noteId = noteId;
  }
  const notePath = extractOptionalString(payload.note_path);
  if (notePath) {
    task.notePath = notePath;
  }
}

function formatToolParameters(parameters: Record<string, unknown>): string {
  try {
    return JSON.stringify(parameters, null, 2);
  } catch (error) {
    console.warn("无法格式化工具参数", error, parameters);
    return Object.entries(parameters)
      .map(([key, value]) => `${key}: ${String(value)}`)
      .join("\n");
  }
}

function formatToolResult(result: string): string {
  const trimmed = result.trim();
  const limit = 900;
  if (trimmed.length > limit) {
    return `${trimmed.slice(0, limit)}…`;
  }
  return trimmed;
}

async function copyNotePath(path: string | null | undefined) {
  if (!path) {
    return;
  }

  try {
    await navigator.clipboard.writeText(path);
    progressLogs.value.push(`已复制笔记路径：${path}`);
  } catch (error) {
    console.warn("无法直接复制到剪贴板", error);
    window.prompt("复制以下笔记路径", path);
    progressLogs.value.push("请手动复制笔记路径");
  }
}

const researchId = ref<string | null>(null);
const researchReplay = ref<ResearchReplayResponse | null>(null);


function formatResearchStatusLabel(
  value?: string | null
): string {
  const normalized = (value || "UNKNOWN")
    .trim()
    .replaceAll("_", " ")
    .toLowerCase();

  return normalized.replace(
    /\b\w/g,
    character => character.toUpperCase()
  );
}

function adaptiveReplayIterations() {
  return (
    researchReplay.value?.decision
      ?.adaptive_research_state
      ?.iterations || []
  );
}

function adaptiveTotalEvidence(): number {
  return adaptiveReplayIterations().reduce(
    (total, iteration) =>
      total + (iteration.new_evidence_count || 0),
    0
  );
}

function adaptiveTotalNovelClaims(): number {
  return adaptiveReplayIterations().reduce(
    (total, iteration) =>
      total + (iteration.novel_claim_count || 0),
    0
  );
}

function adaptiveTotalNewCoverage(): number {
  return adaptiveReplayIterations().reduce(
    (total, iteration) =>
      total +
      (
        iteration.new_candidate_criterion_pairs
        ?.length || 0
      ),
    0
  );
}

function adaptiveFinalResearchValue(): string {
  const iterations = adaptiveReplayIterations();

  if (!iterations.length) {
    return "UNKNOWN";
  }

  return (
    iterations[iterations.length - 1]
      .adaptive_research_value_status ||
    "UNKNOWN"
  );
}

function adaptiveFinalStoppingReason(): string {
  return (
    researchReplay.value?.decision
      ?.stopping_decision?.reason ||
    "not recorded"
  );
}

function isFinalAdaptiveIteration(
  index: number
): boolean {
  return (
    index ===
    adaptiveReplayIterations().length - 1
  );
}
const replayLoading = ref(false);
const replayError = ref("");
const executionTraces = ref<ExecutionTraceResponse[]>([]);
const activeTraceId = ref<string | null>(null);
const activeTraceDetail = ref<TraceDetailResponse | null>(null);
const traceLoading = ref(false);
const traceError = ref("");

const researchClaims = ref<ClaimResponse[]>([]);
const activeClaimId = ref<string | null>(null);
const activeClaimDetail = ref<ClaimDetailResponse | null>(null);
const claimLoading = ref(false);
const claimError = ref("");

function formatDuration(durationMs: number | null): string {
  if (durationMs === null || !Number.isFinite(durationMs)) {
    return "—";
  }

  if (durationMs < 1000) {
    return `${Math.round(durationMs)} ms`;
  }

  return `${(durationMs / 1000).toFixed(2)} s`;
}

function formatTraceTimestamp(value: string | null): string {
  if (!value) {
    return "—";
  }

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return date.toLocaleString();
}

function getTraceForTask(
  taskId: number
): ExecutionTraceResponse | undefined {
  return executionTraces.value.find(
    (trace) => trace.task_id === taskId
  );
}

async function openTraceForTask(taskId: number): Promise<void> {
  const trace = getTraceForTask(taskId);

  if (!trace) {
    return;
  }

  await selectTrace(trace.trace_id);

  requestAnimationFrame(() => {
    document
      .getElementById("trace-inspector")
      ?.scrollIntoView({
        behavior: "smooth",
        block: "start"
      });
  });
}

function formatEventMetadata(
  metadata: Record<string, unknown>
): string {
  if (!Object.keys(metadata).length) {
    return "{}";
  }

  try {
    return JSON.stringify(metadata, null, 2);
  } catch {
    return String(metadata);
  }
}

async function selectTrace(
  traceId: string,
  targetResearchId = researchId.value
): Promise<void> {
  if (!targetResearchId) {
    return;
  }

  activeTraceId.value = traceId;
  traceLoading.value = true;
  traceError.value = "";

  try {
    activeTraceDetail.value = await getResearchTrace(
      targetResearchId,
      traceId
    );
  } catch (err) {
    activeTraceDetail.value = null;
    traceError.value =
      err instanceof Error ? err.message : "Trace 加载失败";
  } finally {
    traceLoading.value = false;
  }
}



function llmCircuitStatus(): string {
  return (
    researchReplay.value
      ?.llm_runtime_circuit
      ?.status || "closed"
  );
}

function isLlmCircuitOpen(): boolean {
  return (
    llmCircuitStatus().toLowerCase()
    === "open"
  );
}

function llmCircuitReason(): string {
  const errorType =
    researchReplay.value
      ?.llm_runtime_circuit
      ?.error_type;

  if (!errorType) {
    return "No terminal provider failure detected";
  }

  return formatRuntimeErrorType(
    errorType
  );
}

function llmCircuitTriggerStage(): string {
  const stage =
    researchReplay.value
      ?.llm_runtime_circuit
      ?.trigger_stage;

  if (!stage) {
    return "Not triggered";
  }

  return formatRuntimeStage(stage);
}

function formatRuntimeStage(stage: string): string {
  const labels: Record<string, string> = {
    decision_case_extraction: "Decision Detection",
    technical_context_extraction: "Technical Context",
    integration_assessment: "Integration Assessment",
    semantic_signal_extraction: "Evidence Interpretation",
    constraint_resolution: "Constraint Resolution",
    decision_intelligence: "Decision Intelligence",
    report_generation: "Report Generation",
  };

  return labels[stage] ?? formatResearchStatusLabel(stage);
}

function formatRuntimeErrorType(errorType: string): string {
  const labels: Record<string, string> = {
    quota_exceeded: "Provider quota exhausted",
    rate_limited: "Provider rate limited",
    timeout: "Provider timeout",
    authentication: "Provider authentication failure",
    provider_unavailable: "Provider unavailable",
    provider_error: "Provider error",
    unknown_error: "Runtime provider error",
  };

  return labels[errorType] ?? formatResearchStatusLabel(errorType);
}

function runtimeNoticeExplanation(
  stage: string,
  errorType: string,
  metadata?: Record<string, unknown>
): string {
  if (
    stage === "report_generation" &&
    metadata?.fallback === "deterministic"
  ) {
    return "The final report model was unavailable, so a deterministic fallback report was produced from the preserved research state.";
  }

  const stageMessages: Record<string, string> = {
    decision_case_extraction:
      "Decision-specific enrichment was unavailable. The normal research workflow continued.",
    technical_context_extraction:
      "Architecture context could not be enriched. The workflow continued without this optional context.",
    integration_assessment:
      "Architecture and migration assessment was unavailable. Existing evidence and decision state were preserved.",
    semantic_signal_extraction:
      "Semantic interpretation degraded. Conservative evidence handling was preserved.",
    constraint_resolution:
      "Constraint resolution was unavailable. Unresolved constraints were preserved rather than treated as violations.",
    decision_intelligence:
      "Decision enrichment degraded, but the normal research report workflow continued.",
  };

  if (stageMessages[stage]) {
    return stageMessages[stage];
  }

  if (errorType === "rate_limited") {
    return "The external model provider temporarily limited requests. Available research state was preserved.";
  }

  if (errorType === "quota_exceeded") {
    return "The external model provider reported insufficient quota. Available research state was preserved.";
  }

  return "An optional runtime component degraded. Available research state was preserved.";
}

function runtimeNoticeClass(errorType: string): string {
  if (
    errorType === "quota_exceeded" ||
    errorType === "rate_limited" ||
    errorType === "timeout" ||
    errorType === "provider_unavailable"
  ) {
    return "runtime-notice-warning";
  }

  return "runtime-notice-neutral";
}

async function loadResearchReplay(
  targetResearchId: string
): Promise<void> {
  replayLoading.value = true;
  replayError.value = "";

  try {
    researchReplay.value = await getResearchReplay(
      targetResearchId
    );
  } catch (err) {
    researchReplay.value = null;

    replayError.value =
      err instanceof Error
        ? err.message
        : "加载 Research Replay 失败";
  } finally {
    replayLoading.value = false;
  }
}

async function openReplayTask(
  task: ResearchReplayTaskResponse
): Promise<void> {
  const traceId = task.trace_ids[0];

  if (!traceId) {
    return;
  }

  await openEvidenceTrace(traceId);
}

async function openReplayEvent(
  traceId: string | null
): Promise<void> {
  if (!traceId) {
    return;
  }

  await openEvidenceTrace(traceId);
}

async function loadResearchTraces(
  targetResearchId: string
): Promise<void> {
  traceLoading.value = true;
  traceError.value = "";

  try {
    const response = await listResearchTraces(targetResearchId);

    executionTraces.value = response.traces;

    if (!response.traces.length) {
      activeTraceId.value = null;
      activeTraceDetail.value = null;
      return;
    }

    const firstTrace = response.traces[0];

    await selectTrace(firstTrace.trace_id, targetResearchId);
  } catch (err) {
    executionTraces.value = [];
    activeTraceId.value = null;
    activeTraceDetail.value = null;
    traceError.value =
      err instanceof Error ? err.message : "Trace 列表加载失败";
  } finally {
    traceLoading.value = false;
  }
}

async function selectClaim(
  claimId: string,
  targetResearchId = researchId.value
): Promise<void> {
  if (!targetResearchId) {
    return;
  }

  activeClaimId.value = claimId;
  claimLoading.value = true;
  claimError.value = "";

  try {
    activeClaimDetail.value = await getResearchClaim(
      targetResearchId,
      claimId
    );
  } catch (err) {
    activeClaimDetail.value = null;
    claimError.value =
      err instanceof Error ? err.message : "Claim 加载失败";
  } finally {
    claimLoading.value = false;
  }
}

async function loadResearchClaims(
  targetResearchId: string
): Promise<void> {
  claimLoading.value = true;
  claimError.value = "";

  try {
    const response = await listResearchClaims(
      targetResearchId
    );

    researchClaims.value = response.claims;

    if (!response.claims.length) {
      activeClaimId.value = null;
      activeClaimDetail.value = null;
      return;
    }

    const firstClaim = response.claims[0];

    await selectClaim(
      firstClaim.claim_id,
      targetResearchId
    );
  } catch (err) {
    researchClaims.value = [];
    activeClaimId.value = null;
    activeClaimDetail.value = null;
    claimError.value =
      err instanceof Error ? err.message : "Claim 列表加载失败";
  } finally {
    claimLoading.value = false;
  }
}

async function openEvidenceTrace(
  traceId: string
): Promise<void> {
  await selectTrace(traceId);

  requestAnimationFrame(() => {
    document
      .getElementById("trace-inspector")
      ?.scrollIntoView({
        behavior: "smooth",
        block: "start"
      });
  });
}

function resetWorkflowState() {
  todoTasks.value = [];
  activeTaskId.value = null;
  reportMarkdown.value = "";
  progressLogs.value = [];
  researchId.value = null;
  researchReplay.value = null;
  replayError.value = "";
  executionTraces.value = [];
  activeTraceId.value = null;
  activeTraceDetail.value = null;
  traceLoading.value = false;
  traceError.value = "";

  researchClaims.value = [];
  activeClaimId.value = null;
  activeClaimDetail.value = null;
  claimLoading.value = false;
  claimError.value = "";

  summaryHighlight.value = false;
  sourcesHighlight.value = false;
  reportHighlight.value = false;
  toolHighlight.value = false;
  logsCollapsed.value = false;
}

function findTask(taskId: unknown): TodoTaskView | undefined {
  const numeric =
    typeof taskId === "number"
      ? taskId
      : typeof taskId === "string"
      ? Number(taskId)
      : NaN;
  if (Number.isNaN(numeric)) {
    return undefined;
  }
  return todoTasks.value.find((task) => task.id === numeric);
}

function upsertTaskMetadata(task: TodoTaskView, payload: Record<string, unknown>) {
  if (typeof payload.title === "string" && payload.title.trim()) {
    task.title = payload.title.trim();
  }
  if (typeof payload.intent === "string" && payload.intent.trim()) {
    task.intent = payload.intent.trim();
  }
  if (typeof payload.query === "string" && payload.query.trim()) {
    task.query = payload.query.trim();
  }
}

const handleSubmit = async () => {
  if (!form.topic.trim()) {
    error.value = "请输入研究主题";
    return;
  }

  if (currentController) {
    currentController.abort();
    currentController = null;
  }

  loading.value = true;
  error.value = "";
  isExpanded.value = true;
  resetWorkflowState();

  const controller = new AbortController();
  currentController = controller;

  const payload = {
    topic: form.topic.trim(),
    search_api: form.searchApi || undefined
  };

  try {
    await runResearchStream(
      payload,
      (event: ResearchStreamEvent) => {
        if (event.type === "status") {
          const message =
            typeof event.message === "string" && event.message.trim()
              ? event.message
              : "流程状态更新";
          progressLogs.value.push(message);

          const payload = event as Record<string, unknown>;
          const task = findTask(payload.task_id);
          if (task && message) {
            task.notices.push(message);
            applyNoteMetadata(task, payload);
          }
          return;
        }

        if (event.type === "todo_list") {
          const tasks = Array.isArray(event.tasks)
            ? (event.tasks as Record<string, unknown>[])
            : [];

          todoTasks.value = tasks.map((item, index) => {
            const rawId =
              typeof item.id === "number"
                ? item.id
                : typeof item.id === "string"
                ? Number(item.id)
                : index + 1;
            const id = Number.isFinite(rawId) ? Number(rawId) : index + 1;
            const noteId =
              typeof item.note_id === "string" && item.note_id.trim()
                ? item.note_id.trim()
                : null;
            const notePath =
              typeof item.note_path === "string" && item.note_path.trim()
                ? item.note_path.trim()
                : null;

            return {
              id,
              title:
                typeof item.title === "string" && item.title.trim()
                  ? item.title.trim()
                  : `任务${id}`,
              intent:
                typeof item.intent === "string" && item.intent.trim()
                  ? item.intent.trim()
                  : "探索与主题相关的关键信息",
              query:
                typeof item.query === "string" && item.query.trim()
                  ? item.query.trim()
                  : form.topic.trim(),
              status:
                typeof item.status === "string" && item.status.trim()
                  ? item.status.trim()
                  : "pending",
              summary: "",
              sourcesSummary: "",
              sourceItems: [],
              notices: [],
              noteId,
              notePath,
              toolCalls: []
            } as TodoTaskView;
          });

          if (todoTasks.value.length) {
            activeTaskId.value = todoTasks.value[0].id;
            progressLogs.value.push("已生成任务清单");
          } else {
            progressLogs.value.push("未生成任务清单，使用默认任务继续");
          }
          return;
        }

        if (event.type === "task_status") {
          const payload = event as Record<string, unknown>;
          const task = findTask(event.task_id);
          if (!task) {
            return;
          }

          upsertTaskMetadata(task, payload);
          applyNoteMetadata(task, payload);
          const status =
            typeof event.status === "string" && event.status.trim()
              ? event.status.trim()
              : task.status;
          task.status = status;

          if (status === "in_progress") {
            task.summary = "";
            task.sourcesSummary = "";
            task.sourceItems = [];
            task.notices = [];
            activeTaskId.value = task.id;
            progressLogs.value.push(`开始执行任务：${task.title}`);
          } else if (status === "completed") {
            if (typeof event.summary === "string" && event.summary.trim()) {
              task.summary = event.summary.trim();
            }
            if (
              typeof event.sources_summary === "string" &&
              event.sources_summary.trim()
            ) {
              task.sourcesSummary = event.sources_summary.trim();
              task.sourceItems = parseSources(task.sourcesSummary);
            }
            progressLogs.value.push(`完成任务：${task.title}`);
            if (activeTaskId.value === task.id) {
              pulse(summaryHighlight);
              pulse(sourcesHighlight);
            }
          } else if (status === "skipped") {
            progressLogs.value.push(`任务跳过：${task.title}`);
          }
          return;
        }

        if (event.type === "sources") {
          const payload = event as Record<string, unknown>;
          const task = findTask(event.task_id);
          if (!task) {
            return;
          }

          const textCandidates = [
            payload.latest_sources,
            payload.sources_summary,
            payload.raw_context
          ];
          const latestText = textCandidates
            .map((value) => (typeof value === "string" ? value.trim() : ""))
            .find((value) => value);

          if (latestText) {
            task.sourcesSummary = latestText;
            task.sourceItems = parseSources(latestText);
            if (activeTaskId.value === task.id) {
              pulse(sourcesHighlight);
            }
            progressLogs.value.push(`已更新任务来源：${task.title}`);
          }

          if (typeof payload.backend === "string") {
            progressLogs.value.push(
              `当前使用搜索后端：${payload.backend}`
            );
          }

          applyNoteMetadata(task, payload);

          return;
        }

        if (event.type === "task_summary_chunk") {
          const payload = event as Record<string, unknown>;
          const task = findTask(event.task_id);
          if (!task) {
            return;
          }
          const chunk =
            typeof event.content === "string" ? event.content : "";
          task.summary += chunk;
          applyNoteMetadata(task, payload);
          if (activeTaskId.value === task.id) {
            pulse(summaryHighlight);
          }
          return;
        }

        if (event.type === "tool_call") {
          const payload = event as Record<string, unknown>;
          const eventId =
            typeof payload.event_id === "number"
              ? payload.event_id
              : Date.now();
          const agent =
            typeof payload.agent === "string" && payload.agent.trim()
              ? payload.agent.trim()
              : "Agent";
          const tool =
            typeof payload.tool === "string" && payload.tool.trim()
              ? payload.tool.trim()
              : "tool";
          const parameters = ensureRecord(payload.parameters);
          const result =
            typeof payload.result === "string" ? payload.result : "";
          const noteId = extractOptionalString(payload.note_id);
          const notePath = extractOptionalString(payload.note_path);

          const task = findTask(payload.task_id);
          if (task) {
            task.toolCalls.push({
              eventId,
              agent,
              tool,
              parameters,
              result,
              noteId,
              notePath,
              timestamp: Date.now()
            });
            if (noteId) {
              task.noteId = noteId;
            }
            if (notePath) {
              task.notePath = notePath;
            }
            const logSummary = noteId
              ? `${agent} 调用了 ${tool}（任务 ${task.id}，笔记 ${noteId}）`
              : `${agent} 调用了 ${tool}（任务 ${task.id}）`;
            progressLogs.value.push(logSummary);
            if (activeTaskId.value === task.id) {
              pulse(toolHighlight);
            }
          } else {
            progressLogs.value.push(`${agent} 调用了 ${tool}`);
          }
          return;
        }

        if (event.type === "research_stored") {
          const storedResearchId =
            typeof event.research_id === "string" &&
            event.research_id.trim()
              ? event.research_id.trim()
              : "";

          if (!storedResearchId) {
            traceError.value = "后端未返回有效 research_id";
            return;
          }

          researchId.value = storedResearchId;
          progressLogs.value.push(
            `研究状态已持久化：${storedResearchId}`
          );

          void Promise.all([
            loadResearchTraces(storedResearchId),
            loadResearchClaims(storedResearchId),
            loadResearchReplay(storedResearchId)
          ]);

          return;
        }

        if (event.type === "final_report") {
          const report =
            typeof event.report === "string" && event.report.trim()
              ? event.report.trim()
              : "";
          reportMarkdown.value = report || "报告生成失败，未获得有效内容";
          pulse(reportHighlight);
          progressLogs.value.push("最终报告已生成");
          return;
        }

        if (event.type === "error") {
          const detail =
            typeof event.detail === "string" && event.detail.trim()
              ? event.detail
              : "研究过程中发生错误";
          error.value = detail;
          progressLogs.value.push("研究失败，已停止流程");
        }
      },
      { signal: controller.signal }
    );

    if (!reportMarkdown.value) {
      reportMarkdown.value = "暂无生成的报告";
    }
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") {
      progressLogs.value.push("已取消当前研究任务");
    } else {
      error.value = err instanceof Error ? err.message : "请求失败";
    }
  } finally {
    loading.value = false;
    if (currentController === controller) {
      currentController = null;
    }
  }
};

const cancelResearch = () => {
  if (!loading.value || !currentController) {
    return;
  }
  progressLogs.value.push("正在尝试取消当前研究任务…");
  currentController.abort();
};

const goBack = () => {
  if (loading.value) {
    return; // 研究进行中不允许返回
  }
  isExpanded.value = false;
};

const startNewResearch = () => {
  if (loading.value) {
    cancelResearch();
  }
  resetWorkflowState();
  isExpanded.value = false;
  form.topic = "";
  form.searchApi = "";
};

onBeforeUnmount(() => {
  if (currentController) {
    currentController.abort();
    currentController = null;
  }
});
</script>


<style scoped>
.app-shell {
  position: relative;
  min-height: 100vh;
  padding: 72px 24px;
  display: flex;
  justify-content: center;
  align-items: center;
  background: radial-gradient(circle at 20% 20%, #f8fafc, #dbeafe 60%);
  color: #1f2937;
  overflow: hidden;
  box-sizing: border-box;
  transition: padding 0.4s ease;
}

.app-shell.expanded {
  padding: 0;
  align-items: stretch;
}

.aurora {
  position: absolute;
  inset: 0;
  pointer-events: none;
  opacity: 0.55;
}

.aurora span {
  position: absolute;
  width: 45vw;
  height: 45vw;
  max-width: 520px;
  max-height: 520px;
  background: radial-gradient(circle, rgba(148, 197, 255, 0.35), transparent 60%);
  filter: blur(90px);
  animation: float 26s infinite linear;
}

.aurora span:nth-child(1) {
  top: -20%;
  left: -18%;
  animation-delay: 0s;
}

.aurora span:nth-child(2) {
  bottom: -25%;
  right: -20%;
  background: radial-gradient(circle, rgba(166, 139, 255, 0.28), transparent 60%);
  animation-delay: -9s;
}

.aurora span:nth-child(3) {
  top: 35%;
  left: 45%;
  background: radial-gradient(circle, rgba(164, 219, 216, 0.26), transparent 60%);
  animation-delay: -16s;
}

.layout {
  position: relative;
  width: 100%;
  display: flex;
  gap: 24px;
  z-index: 1;
  transition: all 0.4s ease;
}

.layout-centered {
  max-width: 600px;
  justify-content: center;
  align-items: center;
}

.layout-fullscreen {
  height: 100vh;
  max-width: 100%;
  gap: 0;
  align-items: stretch;
}

.panel {
  position: relative;
  flex: 1 1 360px;
  padding: 24px;
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.95);
  border: 1px solid rgba(148, 163, 184, 0.18);
  box-shadow: 0 24px 48px rgba(15, 23, 42, 0.12);
  backdrop-filter: blur(8px);
  overflow: hidden;
}

.panel-form {
  max-width: 420px;
}

.panel-centered {
  width: 100%;
  max-width: 600px;
  padding: 40px;
  box-shadow: 0 32px 64px rgba(15, 23, 42, 0.15);
  transform: scale(1);
  transition: transform 0.3s ease, box-shadow 0.3s ease;
}

.panel-centered:hover {
  transform: scale(1.02);
  box-shadow: 0 40px 80px rgba(15, 23, 42, 0.2);
}

.panel-result {
  min-width: 360px;
  flex: 2 1 420px;
}

.panel::before {
  content: "";
  position: absolute;
  inset: 0;
  background: linear-gradient(135deg, rgba(59, 130, 246, 0.12), rgba(125, 86, 255, 0.1));
  opacity: 0;
  transition: opacity 0.35s ease;
  z-index: 0;
}

.panel:hover::before {
  opacity: 1;
}

.panel > * {
  position: relative;
  z-index: 1;
}

.panel-form h1 {
  margin: 0;
  font-size: 26px;
  letter-spacing: 0.01em;
}

.panel-form p {
  margin: 4px 0 0;
  color: #64748b;
  font-size: 13px;
}

.panel-head {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 24px;
}

.logo {
  width: 52px;
  height: 52px;
  display: grid;
  place-items: center;
  border-radius: 16px;
  background: linear-gradient(135deg, #2563eb, #7c3aed);
  box-shadow: 0 12px 28px rgba(59, 130, 246, 0.4);
}

.logo svg {
  width: 28px;
  height: 28px;
  fill: #f8fafc;
}

.form {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.field span {
  font-weight: 600;
  color: #475569;
}

textarea,
input,
select {
  padding: 14px 16px;
  border-radius: 16px;
  border: 1px solid rgba(148, 163, 184, 0.35);
  background: rgba(255, 255, 255, 0.92);
  color: #1f2937;
  font-size: 14px;
  transition: border-color 0.2s, box-shadow 0.2s, background 0.2s;
}

textarea:focus,
input:focus,
select:focus {
  outline: none;
  border-color: rgba(37, 99, 235, 0.65);
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.2);
  background: #ffffff;
}

.options {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
}

.option {
  flex: 1;
  min-width: 140px;
}

.form-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.submit {
  align-self: flex-start;
  padding: 12px 24px;
  border-radius: 16px;
  border: none;
  background: linear-gradient(135deg, #2563eb, #7c3aed);
  color: #ffffff;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  transition: transform 0.2s, box-shadow 0.2s, opacity 0.2s;
  display: inline-flex;
  align-items: center;
  gap: 10px;
  position: relative;
}

.submit-label {
  display: inline-flex;
  align-items: center;
  gap: 10px;
}

.submit .spinner {
  width: 18px;
  height: 18px;
  fill: none;
  stroke: rgba(255, 255, 255, 0.85);
  stroke-linecap: round;
  animation: spin 1s linear infinite;
}

.submit:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}

.submit:not(:disabled):hover {
  transform: translateY(-2px);
  box-shadow: 0 12px 28px rgba(37, 99, 235, 0.28);
}

.secondary-btn {
  padding: 10px 18px;
  border-radius: 14px;
  background: rgba(148, 163, 184, 0.12);
  border: 1px solid rgba(148, 163, 184, 0.28);
  color: #1f2937;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.2s ease, border-color 0.2s ease, color 0.2s ease;
}

.secondary-btn:hover {
  background: rgba(148, 163, 184, 0.2);
  border-color: rgba(148, 163, 184, 0.35);
  color: #0f172a;
}

.error-chip {
  margin-top: 16px;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  background: rgba(248, 113, 113, 0.12);
  border: 1px solid rgba(248, 113, 113, 0.35);
  border-radius: 14px;
  color: #b91c1c;
  font-size: 14px;
}

.error-chip svg {
  width: 18px;
  height: 18px;
  fill: currentColor;
}

.panel-result {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.status-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.status-main {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.status-controls {
  display: flex;
  gap: 8px;
}

.status-chip {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  background: rgba(191, 219, 254, 0.28);
  padding: 8px 14px;
  border-radius: 999px;
  font-size: 13px;
  color: #1f2937;
  border: 1px solid rgba(59, 130, 246, 0.35);
  transition: background 0.3s ease, color 0.3s ease;
}

.status-chip.active {
  background: rgba(129, 140, 248, 0.2);
  border-color: rgba(129, 140, 248, 0.4);
  color: #1e293b;
}

.status-chip .dot {
  width: 8px;
  height: 8px;
  border-radius: 999px;
  background: #2563eb;
  box-shadow: 0 0 12px rgba(37, 99, 235, 0.45);
  animation: pulse 1.8s ease-in-out infinite;
}

.status-meta {
  color: #64748b;
  font-size: 13px;
}

.timeline-wrapper {
  margin-top: 12px;
  max-height: 220px;
  overflow-y: auto;
  padding-right: 8px;
  scrollbar-width: thin;
  scrollbar-color: rgba(129, 140, 248, 0.45) rgba(226, 232, 240, 0.6);
}

.timeline-wrapper::-webkit-scrollbar {
  width: 6px;
}

.timeline-wrapper::-webkit-scrollbar-track {
  background: rgba(226, 232, 240, 0.6);
  border-radius: 999px;
}

.timeline-wrapper::-webkit-scrollbar-thumb {
  background: linear-gradient(180deg, rgba(129, 140, 248, 0.8), rgba(59, 130, 246, 0.7));
  border-radius: 999px;
}

.timeline-wrapper::-webkit-scrollbar-thumb:hover {
  background: linear-gradient(180deg, rgba(99, 102, 241, 0.9), rgba(37, 99, 235, 0.8));
}

.timeline {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 14px;
  position: relative;
  padding-left: 12px;
}

.timeline::before {
  content: "";
  position: absolute;
  top: 8px;
  bottom: 8px;
  left: 0;
  width: 2px;
  background: linear-gradient(180deg, rgba(59, 130, 246, 0.35), rgba(129, 140, 248, 0.15));
}

.timeline li {
  position: relative;
  padding-left: 24px;
  color: #1e293b;
  font-size: 14px;
  line-height: 1.5;
}

.timeline-node {
  position: absolute;
  left: -12px;
  top: 6px;
  width: 10px;
  height: 10px;
  border-radius: 999px;
  background: linear-gradient(135deg, #38bdf8, #7c3aed);
  box-shadow: 0 0 0 4px rgba(59, 130, 246, 0.22);
}

.timeline-enter-active,
.timeline-leave-active {
  transition: all 0.35s ease, opacity 0.35s ease;
}

.timeline-enter-from,
.timeline-leave-to {
  opacity: 0;
  transform: translateY(-6px);
}

.tasks-section {
  display: grid;
  grid-template-columns: 280px 1fr;
  gap: 20px;
  align-items: start;
}

.decision-panel {
  margin-top: 22px;
  padding: 18px;
  border: 1px solid rgba(79, 70, 229, 0.18);
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.72);
}

.decision-panel-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.decision-panel-header h4 {
  margin: 4px 0 0;
  color: #1e293b;
  font-size: 17px;
}

.decision-status {
  padding: 5px 10px;
  border-radius: 999px;
  background: rgba(99, 102, 241, 0.1);
  color: #4338ca;
  font-size: 10px;
  font-weight: 700;
}

.decision-status-ready {
  background: rgba(16, 185, 129, 0.12);
  color: #047857;
}

.decision-status-tentative {
  background: rgba(245, 158, 11, 0.12);
  color: #b45309;
}

.decision-readiness-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
  margin-top: 16px;
}

.decision-readiness-card {
  display: flex;
  flex-direction: column;
  gap: 5px;
  padding: 12px;
  border: 1px solid rgba(148, 163, 184, 0.18);
  border-radius: 12px;
  background: rgba(248, 250, 252, 0.9);
}

.decision-readiness-card span,
.decision-stop-row span {
  color: #64748b;
  font-size: 10px;
}

.decision-readiness-card strong {
  color: #1e293b;
  font-size: 18px;
}

.decision-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
  margin-top: 18px;
}

.decision-section {
  min-width: 0;
}

.decision-candidate-list,
.decision-ranking-list,
.decision-gap-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 10px;
}

.decision-candidate-card,
.decision-gap-card,
.decision-ranking-row {
  padding: 11px;
  border: 1px solid rgba(148, 163, 184, 0.18);
  border-radius: 11px;
  background: rgba(248, 250, 252, 0.78);
}

.decision-candidate-card strong {
  display: block;
  color: #1e293b;
  font-size: 12px;
}

.decision-candidate-card p,
.decision-gap-card p {
  margin: 5px 0;
  color: #64748b;
  font-size: 10px;
  line-height: 1.5;
}

.decision-candidate-card code,
.decision-gap-card code,
.decision-ranking-row code {
  color: #64748b;
  font-size: 9px;
}

.decision-ranking-row {
  display: grid;
  grid-template-columns: auto 1fr auto;
  align-items: center;
  gap: 8px;
}

.decision-ranking-row > span {
  color: #6366f1;
  font-size: 10px;
  font-weight: 700;
}

.decision-ranking-row > strong {
  color: #334155;
  font-size: 11px;
}

.decision-gap-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.decision-gap-header strong {
  color: #334155;
  font-size: 10px;
}

.decision-gap-header span {
  color: #94a3b8;
  font-size: 9px;
}

.decision-stop-row {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
  margin-top: 16px;
}

.decision-stop-row > div {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 10px;
  border-radius: 10px;
  background: rgba(99, 102, 241, 0.06);
}

.decision-stop-row strong {
  color: #334155;
  font-size: 11px;
}

.decision-blockers {
  margin-top: 14px;
  padding: 11px 13px;
  border-radius: 10px;
  background: rgba(245, 158, 11, 0.08);
}

.decision-blockers > strong {
  color: #92400e;
  font-size: 11px;
}

.decision-blockers ul {
  margin: 7px 0 0;
  padding-left: 18px;
  color: #78350f;
  font-size: 10px;
  line-height: 1.6;
}

@media (max-width: 960px) {
  .tasks-section {
    grid-template-columns: 1fr;
  }
}

.tasks-list {
  background: rgba(255, 255, 255, 0.92);
  border: 1px solid rgba(148, 163, 184, 0.26);
  border-radius: 18px;
  padding: 18px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  box-shadow: inset 0 0 0 1px rgba(226, 232, 240, 0.4);
}

.tasks-list h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: #1f2937;
}

.tasks-list ul {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.task-item {
  border-radius: 14px;
  border: 1px solid transparent;
  transition: border-color 0.2s ease, background 0.2s ease;
}

.task-item.completed {
  border-color: rgba(56, 189, 248, 0.35);
  background: rgba(191, 219, 254, 0.28);
}

.task-item.active {
  border-color: rgba(129, 140, 248, 0.5);
  background: rgba(224, 231, 255, 0.5);
}

.task-button {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 14px 6px;
  background: transparent;
  border: none;
  color: inherit;
  cursor: pointer;
  text-align: left;
}

.task-title {
  font-weight: 600;
  font-size: 14px;
  color: #1e293b;
}

.task-status {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 500;
  color: #1f2937;
  background: rgba(148, 163, 184, 0.2);
}

.task-status.pending {
  background: rgba(148, 163, 184, 0.18);
  color: #475569;
}

.task-status.in_progress {
  background: rgba(129, 140, 248, 0.24);
  color: #312e81;
}

.task-status.completed {
  background: rgba(34, 197, 94, 0.2);
  color: #15803d;
}

.task-status.skipped {
  background: rgba(248, 113, 113, 0.18);
  color: #b91c1c;
}

.task-intent {
  margin: 0;
  padding: 0 14px 12px 14px;
  font-size: 13px;
  color: #64748b;
}

.task-detail {
  background: rgba(255, 255, 255, 0.94);
  border: 1px solid rgba(148, 163, 184, 0.26);
  border-radius: 18px;
  padding: 22px;
  display: flex;
  flex-direction: column;
  gap: 18px;
  box-shadow: inset 0 0 0 1px rgba(226, 232, 240, 0.5);
}

.task-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  flex-wrap: wrap;
  gap: 12px;
}

.task-chip-group {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.task-header h3 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: #1f2937;
}

.task-header .muted {
  margin: 6px 0 0;
}

.task-label {
  padding: 6px 12px;
  border-radius: 999px;
  background: rgba(191, 219, 254, 0.32);
  border: 1px solid rgba(59, 130, 246, 0.35);
  font-size: 12px;
  color: #1e3a8a;
}

.task-label.note-chip {
  background: rgba(34, 197, 94, 0.2);
  border-color: rgba(34, 197, 94, 0.35);
  color: #15803d;
}

.task-label.path-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  max-width: 360px;
  background: rgba(56, 189, 248, 0.2);
  border-color: rgba(56, 189, 248, 0.35);
  color: #0369a1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.path-label {
  font-weight: 500;
}

.path-text {
  max-width: 220px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.chip-action {
  border: none;
  background: rgba(56, 189, 248, 0.2);
  color: #0369a1;
  padding: 3px 8px;
  border-radius: 10px;
  font-size: 11px;
  cursor: pointer;
  transition: background 0.2s ease, color 0.2s ease;
}

.chip-action:hover {
  background: rgba(14, 165, 233, 0.28);
  color: #0f172a;
}

.task-notices {
  background: rgba(191, 219, 254, 0.28);
  border: 1px solid rgba(96, 165, 250, 0.35);
  border-radius: 16px;
  padding: 14px 18px;
  color: #1f2937;
}

.task-notices h4 {
  margin: 0 0 8px;
  font-size: 14px;
  font-weight: 600;
}

.task-notices ul {
  list-style: disc;
  margin: 0 0 0 18px;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.task-notices li {
  font-size: 13px;
}

.report-block {
  background: rgba(255, 255, 255, 0.94);
  border: 1px solid rgba(148, 163, 184, 0.26);
  border-radius: 18px;
  padding: 22px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.report-block h3 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: #1f2937;
}

.block-pre {
  font-family: "JetBrains Mono", "Fira Code", ui-monospace, SFMono-Regular,
    Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
  font-size: 13px;
  line-height: 1.7;
  white-space: pre-wrap;
  word-break: break-word;
  color: #1f2937;
  background: rgba(248, 250, 252, 0.9);
  padding: 16px;
  border-radius: 14px;
  border: 1px solid rgba(148, 163, 184, 0.35);
  overflow: auto;
  max-height: 420px;
  scrollbar-width: thin;
  scrollbar-color: rgba(129, 140, 248, 0.6) rgba(226, 232, 240, 0.7);
}

.block-pre::-webkit-scrollbar {
  width: 6px;
}

.block-pre::-webkit-scrollbar-track {
  background: rgba(226, 232, 240, 0.7);
  border-radius: 999px;
}

.block-pre::-webkit-scrollbar-thumb {
  background: linear-gradient(180deg, rgba(99, 102, 241, 0.75), rgba(59, 130, 246, 0.65));
  border-radius: 999px;
}

.block-pre::-webkit-scrollbar-thumb:hover {
  background: linear-gradient(180deg, rgba(79, 70, 229, 0.8), rgba(37, 99, 235, 0.75));
}

.summary-block .block-pre,
.sources-block .block-pre {
  max-height: 360px;
}


.tools-block {
  position: relative;
  margin-top: 16px;
  padding: 20px;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.94);
  border: 1px solid rgba(148, 163, 184, 0.18);
  box-shadow: inset 0 0 0 1px rgba(226, 232, 240, 0.4);
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.tools-block h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: #1f2937;
  letter-spacing: 0.02em;
}

.tool-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.tool-entry {
  background: rgba(248, 250, 252, 0.95);
  border: 1px solid rgba(148, 163, 184, 0.24);
  border-radius: 14px;
  padding: 14px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.tool-entry-header {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  justify-content: space-between;
}

.tool-entry-title {
  font-weight: 600;
  color: #1f2937;
}

.tool-entry-note {
  font-size: 12px;
  color: #0f766e;
}

.tool-entry-path {
  margin: 0;
  font-size: 12px;
  display: flex;
  align-items: center;
  gap: 6px;
  color: #2563eb;
}

.tool-subtitle {
  margin: 0;
  font-size: 13px;
  color: #475569;
  font-weight: 500;
}

.tool-pre {
  font-family: "JetBrains Mono", "Fira Code", ui-monospace, SFMono-Regular,
    Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
  font-size: 12px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
  color: #1f2937;
  background: rgba(248, 250, 252, 0.9);
  padding: 12px;
  border-radius: 12px;
  border: 1px solid rgba(148, 163, 184, 0.28);
  overflow: auto;
  max-height: 260px;
  scrollbar-width: thin;
  scrollbar-color: rgba(129, 140, 248, 0.6) rgba(226, 232, 240, 0.7);
}

.tool-pre::-webkit-scrollbar {
  width: 6px;
}

.tool-pre::-webkit-scrollbar-track {
  background: rgba(226, 232, 240, 0.7);
}

.tool-pre::-webkit-scrollbar-thumb {
  background: rgba(99, 102, 241, 0.7);
  border-radius: 10px;
}

.link-btn {
  background: none;
  border: none;
  color: #0369a1;
  cursor: pointer;
  padding: 0 4px;
  font-size: 12px;
  border-radius: 8px;
  transition: color 0.2s ease, background 0.2s ease;
}

.link-btn:hover {
  color: #0ea5e9;
  background: rgba(14, 165, 233, 0.16);
}


.sources-block,
.summary-block {
  position: relative;
  margin-top: 16px;
  padding: 18px;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.94);
  border: 1px solid rgba(148, 163, 184, 0.18);
  box-shadow: inset 0 0 0 1px rgba(226, 232, 240, 0.4);
}

.sources-history {
  margin-top: 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.sources-history h4 {
  margin: 0;
  color: #1f2937;
  font-size: 14px;
  letter-spacing: 0.01em;
}

.history-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.history-list details {
  background: rgba(248, 250, 252, 0.95);
  border: 1px solid rgba(148, 163, 184, 0.24);
  border-radius: 14px;
  padding: 12px 16px;
  color: #1f2937;
  transition: border-color 0.2s ease, background 0.2s ease;
}

.history-list details[open] {
  background: rgba(224, 231, 255, 0.55);
  border-color: rgba(129, 140, 248, 0.4);
}

.history-list summary {
  cursor: pointer;
  font-weight: 600;
  outline: none;
  list-style: none;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.history-list summary::-webkit-details-marker {
  display: none;
}

.history-list summary::after {
  content: "▾";
  margin-left: 6px;
  font-size: 12px;
  opacity: 0.7;
  transition: transform 0.2s ease;
}

.history-list details[open] summary::after {
  transform: rotate(180deg);
}

.block-highlight {
  animation: glow 1.2s ease;
}

.sources-block h3,
.summary-block h3 {
  margin: 0 0 14px;
  color: #1f2937;
  letter-spacing: 0.02em;
}

.sources-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.source-item {
  position: relative;
  display: inline-flex;
  flex-direction: column;
  gap: 6px;
}

.source-link {
  color: #2563eb;
  text-decoration: none;
  font-weight: 600;
  letter-spacing: 0.01em;
  transition: color 0.2s ease;
}

.source-link::after {
  content: " ↗";
  font-size: 12px;
  opacity: 0.6;
}

.source-link:hover {
  color: #0f172a;
}

.source-tooltip {
  display: none;
  position: absolute;
  bottom: calc(100% + 12px);
  left: 50%;
  transform: translateX(-50%);
  background: rgba(255, 255, 255, 0.98);
  color: #1f2937;
  padding: 14px 16px;
  border-radius: 16px;
  box-shadow: 0 18px 32px rgba(15, 23, 42, 0.18);
  width: min(420px, 90vw);
  z-index: 20;
  border: 1px solid rgba(148, 163, 184, 0.24);
}

.source-tooltip::after {
  content: "";
  position: absolute;
  top: 100%;
  left: 50%;
  transform: translateX(-50%);
  border-width: 10px;
  border-style: solid;
  border-color: rgba(255, 255, 255, 0.98) transparent transparent transparent;
}

.source-tooltip::before {
  content: "";
  position: absolute;
  bottom: -12px;
  left: 50%;
  transform: translateX(-50%);
  border-width: 12px 10px 0 10px;
  border-style: solid;
  border-color: rgba(255, 255, 255, 0.98) transparent transparent transparent;
  filter: drop-shadow(0 -2px 4px rgba(15, 23, 42, 0.12));
}

.source-tooltip p {
  margin: 0 0 8px;
  font-size: 13px;
  line-height: 1.6;
}

.source-tooltip p:last-child {
  margin-bottom: 0;
}

.muted-text {
  color: #64748b;
}

.source-item:hover .source-tooltip,
.source-item:focus-within .source-tooltip {
  display: block;
}

.hint.muted {
  color: #64748b;
}

@keyframes float {
  0% {
    transform: translate3d(0, 0, 0) rotate(0deg);
  }
  50% {
    transform: translate3d(10%, 6%, 0) rotate(3deg);
  }
  100% {
    transform: translate3d(0, 0, 0) rotate(0deg);
  }
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

@keyframes pulse {
  0%,
  100% {
    transform: scale(1);
    opacity: 1;
  }
  50% {
    transform: scale(1.3);
    opacity: 0.5;
  }
}

@keyframes glow {
  0% {
    box-shadow: 0 0 0 rgba(59, 130, 246, 0.3);
    border-color: rgba(59, 130, 246, 0.5);
  }
  100% {
    box-shadow: inset 0 0 0 1px rgba(59, 130, 246, 0.12);
    border-color: rgba(148, 163, 184, 0.2);
  }
}

@media (max-width: 960px) {
  .app-shell {
    padding: 56px 16px;
  }

  .layout {
    flex-direction: column;
    align-items: stretch;
  }

  .panel {
    padding: 22px;
  }

  .panel-form,
  .panel-result {
    max-width: none;
  }

  .status-bar {
    flex-direction: column;
    align-items: flex-start;
  }

  .status-main,
  .status-controls {
    width: 100%;
  }

  .status-controls {
    justify-content: flex-start;
  }
}

@media (max-width: 600px) {
  .options {
    flex-direction: column;
  }

  .status-meta {
    font-size: 12px;
  }

  .panel-head {
    flex-direction: column;
    align-items: flex-start;
  }

  .panel-form h1 {
    font-size: 24px;
  }
}

/* 侧边栏样式 */
.sidebar {
  width: 400px;
  min-width: 400px;
  height: 100vh;
  background: rgba(255, 255, 255, 0.98);
  border-right: 1px solid rgba(148, 163, 184, 0.2);
  padding: 32px 24px;
  display: flex;
  flex-direction: column;
  gap: 24px;
  overflow-y: auto;
  box-shadow: 4px 0 24px rgba(15, 23, 42, 0.08);
}

.sidebar-header {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.sidebar-header h2 {
  font-size: 24px;
  font-weight: 700;
  margin: 0;
  color: #1f2937;
}

.back-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
  background: transparent;
  border: 1px solid rgba(148, 163, 184, 0.3);
  border-radius: 12px;
  color: #64748b;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
  width: fit-content;
}

.back-btn:hover:not(:disabled) {
  background: rgba(59, 130, 246, 0.1);
  border-color: #3b82f6;
  color: #3b82f6;
}

.back-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.research-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.info-item {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.info-item label {
  font-size: 12px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: #64748b;
}

.info-item p {
  margin: 0;
  font-size: 14px;
  color: #1f2937;
  line-height: 1.6;
}

.topic-display {
  font-size: 16px !important;
  font-weight: 600;
  color: #0f172a !important;
  padding: 12px;
  background: rgba(59, 130, 246, 0.05);
  border-radius: 8px;
  border-left: 3px solid #3b82f6;
}

.progress-bar {
  width: 100%;
  height: 8px;
  background: rgba(148, 163, 184, 0.2);
  border-radius: 4px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #3b82f6, #8b5cf6);
  border-radius: 4px;
  transition: width 0.5s ease;
}

.progress-text {
  font-size: 13px !important;
  color: #64748b !important;
  font-weight: 500;
}

.sidebar-actions {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding-top: 16px;
  border-top: 1px solid rgba(148, 163, 184, 0.2);
}

.new-research-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 14px 20px;
  background: linear-gradient(135deg, #3b82f6, #8b5cf6);
  border: none;
  border-radius: 12px;
  color: white;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s ease;
  box-shadow: 0 4px 12px rgba(59, 130, 246, 0.3);
}

.new-research-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(59, 130, 246, 0.4);
}

.new-research-btn:active {
  transform: translateY(0);
}

/* 全屏状态下的结果面板 */
.layout-fullscreen .panel-result {
  flex: 1;
  height: 100vh;
  border-radius: 0;
  border: none;
  overflow-y: auto;
  max-width: none;
}

@media (max-width: 1024px) {
  .sidebar {
    width: 320px;
    min-width: 320px;
  }
}

@media (max-width: 768px) {
  .layout-fullscreen {
    flex-direction: column;
  }

  .sidebar {
    width: 100%;
    min-width: 100%;
    height: auto;
    max-height: 40vh;
  }

  .layout-fullscreen .panel-result {
    height: 60vh;
  }
}

.trace-inspector {
  padding: 20px;
  border: 1px solid rgba(99, 102, 241, 0.2);
  border-radius: 18px;
  background: rgba(248, 250, 252, 0.88);
}

.trace-inspector-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 18px;
}

.trace-inspector-header h3 {
  margin: 2px 0 4px;
  font-size: 18px;
}

.trace-eyebrow {
  margin: 0;
  color: #6366f1;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.trace-research-id {
  margin: 0;
  color: #64748b;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 12px;
}

.trace-error {
  padding: 10px 12px;
  border: 1px solid rgba(239, 68, 68, 0.24);
  border-radius: 12px;
  background: rgba(254, 226, 226, 0.65);
  color: #b91c1c;
  font-size: 13px;
}

.trace-layout {
  display: grid;
  grid-template-columns: minmax(210px, 0.8fr) minmax(0, 2fr);
  gap: 16px;
}

.trace-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 520px;
  overflow-y: auto;
}

.trace-list-item {
  width: 100%;
  padding: 12px;
  border: 1px solid rgba(148, 163, 184, 0.25);
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.82);
  text-align: left;
  cursor: pointer;
  transition:
    border-color 0.2s ease,
    background 0.2s ease,
    transform 0.2s ease;
}

.trace-list-item:hover {
  transform: translateY(-1px);
  border-color: rgba(99, 102, 241, 0.4);
}

.trace-list-item.active {
  border-color: rgba(79, 70, 229, 0.55);
  background: rgba(238, 242, 255, 0.9);
}

.trace-list-title,
.trace-list-meta,
.event-card-header,
.trace-detail-header,
.event-section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.trace-list-title {
  margin-bottom: 7px;
  font-weight: 650;
}

.trace-list-item code,
.trace-detail code,
.event-card code {
  color: #64748b;
  font-size: 11px;
  word-break: break-all;
}

.trace-list-meta {
  margin-top: 8px;
  color: #64748b;
  font-size: 11px;
}

.trace-list-error {
  margin: 8px 0 0;
  color: #b91c1c;
  font-size: 11px;
}

.trace-status {
  display: inline-flex;
  align-items: center;
  padding: 4px 8px;
  border-radius: 999px;
  background: #e2e8f0;
  color: #475569;
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
}

.trace-status-completed {
  background: #dcfce7;
  color: #166534;
}

.trace-status-failed {
  background: #fee2e2;
  color: #991b1b;
}

.trace-status-running,
.trace-status-in_progress {
  background: #dbeafe;
  color: #1d4ed8;
}

.trace-status-skipped {
  background: #f1f5f9;
  color: #64748b;
}

.trace-detail {
  min-width: 0;
  padding: 16px;
  border: 1px solid rgba(148, 163, 184, 0.2);
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.9);
}

.trace-detail-header {
  align-items: flex-start;
  margin-bottom: 16px;
}

.trace-detail-header h4 {
  margin: 0 0 4px;
}

.trace-metrics {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
  margin-bottom: 18px;
}

.trace-metrics > div {
  padding: 10px;
  border-radius: 12px;
  background: #f8fafc;
}

.trace-metrics span {
  display: block;
  margin-bottom: 4px;
  color: #94a3b8;
  font-size: 10px;
}

.trace-metrics strong {
  display: block;
  overflow: hidden;
  color: #334155;
  font-size: 12px;
  text-overflow: ellipsis;
}

.trace-failure {
  margin-bottom: 16px;
  padding: 12px;
  border-left: 3px solid #ef4444;
  border-radius: 8px;
  background: #fef2f2;
  color: #991b1b;
}

.trace-failure p {
  margin: 4px 0 0;
  font-size: 12px;
}

.event-section {
  border-top: 1px solid #e2e8f0;
  padding-top: 16px;
}

.event-section-header {
  margin-bottom: 14px;
}

.event-section-header h4 {
  margin: 0;
}

.event-section-header span {
  color: #94a3b8;
  font-size: 11px;
}

.event-timeline {
  position: relative;
  margin: 0;
  padding: 0 0 0 22px;
  list-style: none;
}

.event-timeline::before {
  content: "";
  position: absolute;
  top: 8px;
  bottom: 8px;
  left: 6px;
  width: 2px;
  background: #e2e8f0;
}

.event-item {
  position: relative;
  margin-bottom: 12px;
}

.event-node {
  position: absolute;
  top: 14px;
  left: -21px;
  z-index: 1;
  width: 10px;
  height: 10px;
  border: 2px solid #ffffff;
  border-radius: 50%;
  background: #6366f1;
  box-shadow: 0 0 0 2px #c7d2fe;
}

.event-card {
  padding: 12px;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  background: #ffffff;
}

.event-card-header {
  align-items: flex-start;
  margin-bottom: 6px;
}

.event-card-header strong {
  display: block;
  color: #1e293b;
  font-size: 12px;
}

.event-card-header span {
  color: #6366f1;
  font-size: 10px;
}

.event-card-header time {
  color: #94a3b8;
  font-size: 10px;
  white-space: nowrap;
}

.event-metadata {
  margin-top: 10px;
}

.event-metadata summary {
  color: #475569;
  font-size: 11px;
  cursor: pointer;
}

.event-metadata pre {
  max-height: 220px;
  margin: 8px 0 0;
  padding: 10px;
  overflow: auto;
  border-radius: 8px;
  background: #0f172a;
  color: #e2e8f0;
  font-size: 10px;
  white-space: pre-wrap;
  word-break: break-word;
}

.trace-empty {
  margin: 12px 0;
  color: #94a3b8;
  font-size: 12px;
}

@media (max-width: 960px) {
  .trace-layout {
    grid-template-columns: 1fr;
  }

  .trace-list {
    max-height: 260px;
  }

  .trace-metrics {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}


/* Phase 5.2 — Trace UX */

.task-trace-link {
  margin: 0 14px 12px;
  padding: 6px 9px;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  border: 1px solid rgba(99, 102, 241, 0.25);
  border-radius: 8px;
  background: rgba(238, 242, 255, 0.72);
  cursor: pointer;
  font-size: 11px;
  color: #4338ca;
}

.task-trace-link:hover {
  background: rgba(224, 231, 255, 0.95);
}

.task-trace-link span {
  text-transform: uppercase;
  font-size: 10px;
  opacity: 0.72;
}

.trace-list-item.trace-failed {
  border-color: rgba(239, 68, 68, 0.38);
  background: rgba(254, 242, 242, 0.72);
}

.trace-list-item.trace-skipped {
  border-color: rgba(245, 158, 11, 0.38);
  background: rgba(255, 251, 235, 0.78);
}

.trace-list-error {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.trace-list-error span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 11px;
}

.event-metadata-summary {
  margin-top: 10px;
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.event-metadata-summary span {
  padding: 4px 8px;
  border-radius: 999px;
  background: rgba(238, 242, 255, 0.86);
  border: 1px solid rgba(129, 140, 248, 0.2);
  color: #4338ca;
  font-size: 11px;
  line-height: 1.3;
}


/* Phase 6 — Evidence Grounding */

.evidence-inspector {
  margin-top: 22px;
  padding: 22px;
  border-radius: 20px;
  border: 1px solid rgba(99, 102, 241, 0.2);
  background: rgba(255, 255, 255, 0.94);
  box-shadow: 0 18px 42px rgba(15, 23, 42, 0.06);
}

.evidence-inspector-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 18px;
  margin-bottom: 18px;
}

.evidence-inspector-header h3 {
  margin: 2px 0 4px;
}

.evidence-description {
  margin: 0;
  font-size: 13px;
  color: #64748b;
}

.evidence-layout {
  display: grid;
  grid-template-columns: minmax(230px, 0.34fr) minmax(0, 1fr);
  gap: 18px;
}

.claim-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.claim-list-item {
  width: 100%;
  padding: 13px;
  border-radius: 14px;
  border: 1px solid rgba(148, 163, 184, 0.25);
  background: rgba(248, 250, 252, 0.88);
  text-align: left;
  cursor: pointer;
  transition:
    border-color 0.2s ease,
    background 0.2s ease,
    transform 0.2s ease;
}

.claim-list-item:hover {
  transform: translateY(-1px);
  border-color: rgba(99, 102, 241, 0.34);
}

.claim-list-item.active {
  border-color: rgba(99, 102, 241, 0.52);
  background: rgba(238, 242, 255, 0.95);
}

.claim-list-title {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  align-items: center;
  margin-bottom: 8px;
  font-size: 12px;
  font-weight: 600;
}

.claim-evidence-count {
  padding: 3px 7px;
  border-radius: 999px;
  background: rgba(99, 102, 241, 0.1);
  color: #4f46e5;
  font-size: 10px;
}

.claim-preview {
  display: -webkit-box;
  margin: 0 0 8px;
  overflow: hidden;
  -webkit-line-clamp: 4;
  -webkit-box-orient: vertical;
  color: #475569;
  font-size: 12px;
  line-height: 1.55;
}

.claim-list-item code {
  color: #94a3b8;
  font-size: 10px;
}

.claim-detail {
  min-width: 0;
  border-radius: 16px;
  border: 1px solid rgba(226, 232, 240, 0.9);
  padding: 18px;
  background: #ffffff;
}

.claim-detail-header {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: center;
}

.claim-detail-header h4 {
  margin: 4px 0 0;
}

.claim-task-label {
  color: #6366f1;
  font-size: 11px;
  font-weight: 600;
}

.claim-support-count {
  padding: 5px 9px;
  border-radius: 999px;
  background: rgba(16, 185, 129, 0.1);
  color: #047857;
  font-size: 11px;
}

.claim-text {
  margin-top: 16px;
  padding: 15px;
  border-radius: 14px;
  background: rgba(248, 250, 252, 0.9);
  color: #1e293b;
  font-size: 13px;
  line-height: 1.7;
  white-space: pre-wrap;
}

.claim-provenance {
  margin-top: 14px;
  display: flex;
  flex-wrap: wrap;
  gap: 14px;
}

.claim-provenance > div {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.claim-provenance span {
  color: #94a3b8;
  font-size: 10px;
  text-transform: uppercase;
}

.claim-provenance code {
  font-size: 11px;
}

.claim-trace-link {
  padding: 0;
  border: 0;
  background: transparent;
  color: #4f46e5;
  cursor: pointer;
  font: inherit;
  font-size: 11px;
  text-align: left;
}

.claim-trace-link:hover {
  text-decoration: underline;
}

.supporting-evidence-section {
  margin-top: 22px;
}

.evidence-card-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-top: 12px;
}

.evidence-card {
  padding: 15px;
  border-radius: 14px;
  border: 1px solid rgba(148, 163, 184, 0.22);
  background: rgba(248, 250, 252, 0.58);
}

.evidence-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}

.evidence-card-header > div {
  display: flex;
  gap: 6px;
}

.evidence-rank,
.evidence-backend {
  padding: 3px 7px;
  border-radius: 999px;
  font-size: 10px;
}

.evidence-rank {
  background: rgba(14, 165, 233, 0.1);
  color: #0369a1;
}

.evidence-backend {
  background: rgba(99, 102, 241, 0.1);
  color: #4338ca;
}

.evidence-card-header code {
  color: #94a3b8;
  font-size: 10px;
}

.evidence-card h5 {
  margin: 12px 0 6px;
  color: #1e293b;
  font-size: 14px;
}

.evidence-source-link {
  display: block;
  overflow-wrap: anywhere;
  color: #2563eb;
  font-size: 11px;
  text-decoration: none;
}

.evidence-source-link:hover {
  text-decoration: underline;
}

.evidence-snippet {
  margin: 12px 0 0;
  color: #475569;
  font-size: 12px;
  line-height: 1.65;
}

.evidence-provenance {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 12px;
  color: #64748b;
  font-size: 10px;
}

.evidence-content {
  margin-top: 12px;
}

.evidence-content summary {
  cursor: pointer;
  color: #64748b;
  font-size: 11px;
}

.evidence-content pre {
  max-height: 320px;
  overflow: auto;
  margin: 10px 0 0;
  padding: 12px;
  border-radius: 10px;
  background: #0f172a;
  color: #e2e8f0;
  font-size: 10px;
  line-height: 1.55;
  white-space: pre-wrap;
  word-break: break-word;
}

@media (max-width: 960px) {
  .evidence-layout {
    grid-template-columns: 1fr;
  }

  .evidence-inspector-header {
    flex-direction: column;
  }
}

</style>

<style scoped>
.markdown-body {
  line-height: 1.75;
  color: #1f2937;
  overflow-wrap: anywhere;
}

.markdown-body :deep(h1),
.markdown-body :deep(h2),
.markdown-body :deep(h3),
.markdown-body :deep(h4) {
  margin: 1.1em 0 0.55em;
  line-height: 1.35;
}

.markdown-body :deep(h1) {
  font-size: 1.5rem;
}

.markdown-body :deep(h2) {
  font-size: 1.3rem;
}

.markdown-body :deep(h3) {
  font-size: 1.15rem;
}

.markdown-body :deep(p) {
  margin: 0.7em 0;
}

.markdown-body :deep(ul),
.markdown-body :deep(ol) {
  margin: 0.7em 0;
  padding-left: 1.6em;
}

.markdown-body :deep(blockquote) {
  margin: 0.8em 0;
  padding: 0.65em 1em;
  border-left: 4px solid #818cf8;
  background: #f8fafc;
}

.markdown-body :deep(code) {
  padding: 0.12em 0.35em;
  border-radius: 4px;
  background: #eef2ff;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
}

.markdown-body :deep(pre) {
  overflow-x: auto;
  padding: 1em;
  border-radius: 10px;
  background: #f8fafc;
}

.markdown-body :deep(a) {
  color: #2563eb;
  text-decoration: underline;
}
</style>

<style scoped>
.tool-entry {
  padding: 0;
  overflow: hidden;
}

.tool-entry-summary {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 14px;
  cursor: pointer;
  list-style: none;
  user-select: none;
}

.tool-entry-summary::-webkit-details-marker {
  display: none;
}

.tool-entry-summary::after {
  content: "▾";
  margin-left: auto;
  font-size: 12px;
  color: #64748b;
  transition: transform 0.2s ease;
}

.tool-entry[open] .tool-entry-summary::after {
  transform: rotate(180deg);
}

.tool-entry[open] .tool-entry-summary {
  background: rgba(224, 231, 255, 0.45);
  border-bottom: 1px solid rgba(148, 163, 184, 0.2);
}

.tool-entry-content {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 14px;
}

.tool-entry-summary:hover {
  background: rgba(238, 242, 255, 0.7);
}
</style>

<style scoped>
.replay-inspector {
  margin-top: 24px;
  padding: 22px;
  border: 1px solid rgba(99, 102, 241, 0.18);
  border-radius: 18px;
  background:
    linear-gradient(
      135deg,
      rgba(238, 242, 255, 0.72),
      rgba(248, 250, 252, 0.9)
    );
}

.replay-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 20px;
}

.replay-header h3 {
  margin: 4px 0 0;
}

.replay-description {
  margin: 6px 0 0;
  color: #64748b;
  font-size: 12px;
  line-height: 1.6;
}

.replay-summary-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  margin-top: 20px;
}

.replay-metric {
  display: flex;
  flex-direction: column;
  gap: 5px;
  padding: 14px;
  border: 1px solid rgba(148, 163, 184, 0.18);
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.75);
}

.replay-metric span {
  color: #64748b;
  font-size: 11px;
}

.replay-metric strong {
  color: #1e293b;
  font-size: 22px;
}

.replay-layout {
  display: grid;
  grid-template-columns: minmax(260px, 0.8fr) minmax(0, 1.4fr);
  gap: 22px;
  margin-top: 22px;
}

.replay-task-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-top: 12px;
}

.replay-task-card {
  width: 100%;
  padding: 14px;
  border: 1px solid rgba(148, 163, 184, 0.22);
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.75);
  cursor: pointer;
  text-align: left;
}

.replay-task-card:hover {
  border-color: rgba(79, 70, 229, 0.4);
  background: rgba(238, 242, 255, 0.75);
}

.replay-task-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.replay-task-card > strong {
  display: block;
  margin-top: 10px;
  color: #1e293b;
  font-size: 13px;
}

.replay-task-card p {
  margin: 7px 0;
  color: #64748b;
  font-size: 11px;
  line-height: 1.55;
}

.replay-task-card code {
  display: block;
  overflow-wrap: anywhere;
  color: #475569;
  font-size: 10px;
}

.replay-artifact-counts {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 10px;
}

.replay-artifact-counts span {
  padding: 3px 7px;
  border-radius: 999px;
  background: rgba(99, 102, 241, 0.08);
  color: #4338ca;
  font-size: 9px;
}

.replay-timeline {
  position: relative;
  margin: 14px 0 0;
  padding: 0;
  list-style: none;
}

.replay-event {
  position: relative;
  display: grid;
  grid-template-columns: 18px minmax(0, 1fr);
  gap: 10px;
  padding-bottom: 12px;
}

.replay-event::before {
  position: absolute;
  top: 16px;
  bottom: -4px;
  left: 6px;
  width: 1px;
  background: rgba(148, 163, 184, 0.35);
  content: "";
}

.replay-event:last-child::before {
  display: none;
}

.replay-event-node {
  z-index: 1;
  width: 9px;
  height: 9px;
  margin-top: 12px;
  margin-left: 2px;
  border: 2px solid #6366f1;
  border-radius: 50%;
  background: #fff;
}

.replay-event-card {
  width: 100%;
  padding: 12px;
  border: 1px solid rgba(148, 163, 184, 0.18);
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.68);
  font: inherit;
  text-align: left;
}

.replay-event-card.clickable {
  cursor: pointer;
}

.replay-event-card.clickable:hover {
  border-color: rgba(79, 70, 229, 0.36);
  background: rgba(238, 242, 255, 0.72);
}

.replay-event-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.replay-event-header strong {
  color: #334155;
  font-size: 11px;
}

.replay-event-header time {
  color: #94a3b8;
  font-size: 9px;
}

.replay-event-card p {
  margin: 7px 0 0;
  color: #64748b;
  font-size: 11px;
  line-height: 1.5;
}

.replay-event-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 9px;
  margin-top: 8px;
  color: #64748b;
  font-size: 9px;
}

.replay-event-meta code {
  color: #94a3b8;
}

@media (max-width: 960px) {
  .replay-header {
    flex-direction: column;
  }

  .replay-summary-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .replay-layout {
    grid-template-columns: 1fr;
  }

  .decision-readiness-grid,
  .decision-stop-row {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .decision-grid {
    grid-template-columns: 1fr;
  }
}

.adaptive-research-iterations {
  margin-top: 20px;
  padding-top: 18px;
  border-top: 1px solid rgba(148, 163, 184, 0.18);
}

.adaptive-research-heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 14px;
}

.adaptive-research-heading h4 {
  margin: 3px 0 0;
}

.adaptive-iteration-count {
  flex-shrink: 0;
  font-size: 12px;
  opacity: 0.68;
}

.adaptive-iteration-list {
  display: grid;
  gap: 12px;
}

.adaptive-iteration-card {
  padding: 15px;
  border: 1px solid rgba(148, 163, 184, 0.18);
  border-radius: 12px;
  background: rgba(15, 23, 42, 0.18);
}

.adaptive-iteration-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}

.adaptive-iteration-header > div {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.adaptive-iteration-label {
  font-weight: 700;
}

.adaptive-run-status {
  padding: 2px 7px;
  border-radius: 999px;
  font-size: 11px;
  opacity: 0.72;
  border: 1px solid rgba(148, 163, 184, 0.22);
}

.research-value-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 5px 9px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.03em;
  white-space: nowrap;
  border: 1px solid rgba(148, 163, 184, 0.24);
}

.research-value-high_value {
  background: rgba(34, 197, 94, 0.12);
  border-color: rgba(34, 197, 94, 0.32);
}

.research-value-moderate_value {
  background: rgba(59, 130, 246, 0.10);
  border-color: rgba(59, 130, 246, 0.28);
}

.research-value-low_value {
  background: rgba(245, 158, 11, 0.10);
  border-color: rgba(245, 158, 11, 0.30);
}

.research-value-no_value,
.research-value-unknown {
  background: rgba(148, 163, 184, 0.08);
  border-color: rgba(148, 163, 184, 0.20);
  opacity: 0.82;
}

.adaptive-value-summary {
  margin: 10px 0 0;
  line-height: 1.55;
  opacity: 0.86;
}

.adaptive-signal-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
  margin-top: 13px;
}

.adaptive-signal {
  min-width: 0;
  padding: 9px 10px;
  border-radius: 9px;
  background: rgba(148, 163, 184, 0.07);
}

.adaptive-signal span {
  display: block;
  margin-bottom: 4px;
  font-size: 11px;
  opacity: 0.62;
}

.adaptive-signal strong {
  display: block;
  overflow-wrap: anywhere;
  font-size: 12px;
  font-weight: 650;
}

.adaptive-subheading {
  display: block;
  margin-bottom: 6px;
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  opacity: 0.62;
}

.adaptive-observations,
.adaptive-new-coverage,
.adaptive-stopping,
.adaptive-explanation {
  margin-top: 12px;
}

.adaptive-observations ul,
.adaptive-explanation ul {
  margin: 6px 0 0;
  padding-left: 18px;
}

.adaptive-observations li,
.adaptive-explanation li {
  margin: 3px 0;
  line-height: 1.45;
  font-size: 12px;
  opacity: 0.82;
}

.adaptive-explanation {
  border-top: 1px solid rgba(148, 163, 184, 0.12);
  padding-top: 10px;
}

.adaptive-explanation summary {
  cursor: pointer;
  font-size: 12px;
  font-weight: 650;
  opacity: 0.76;
}

.adaptive-pair-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.adaptive-pair-list code {
  padding: 4px 7px;
  border-radius: 6px;
  background: rgba(148, 163, 184, 0.09);
  font-size: 11px;
}

.adaptive-stopping {
  padding: 10px 11px;
  border-radius: 9px;
  border: 1px solid rgba(148, 163, 184, 0.16);
  background: rgba(148, 163, 184, 0.06);
}

.adaptive-stopping p {
  margin: 0;
  line-height: 1.5;
  font-size: 12px;
  opacity: 0.82;
}

@media (max-width: 760px) {
  .adaptive-signal-grid {
    grid-template-columns: 1fr;
  }

  .adaptive-iteration-header,
  .adaptive-research-heading {
    align-items: flex-start;
    flex-direction: column;
  }
}



.adaptive-journey-description {
  max-width: 620px;
  margin: 5px 0 0;
  line-height: 1.45;
  font-size: 12px;
  opacity: 0.66;
}

.adaptive-journey-summary {
  display: grid;
  grid-template-columns:
    repeat(3, minmax(0, 1fr));
  gap: 8px;
  margin-bottom: 14px;
}

.adaptive-journey-metric {
  min-width: 0;
  padding: 10px 11px;
  border-radius: 9px;
  border:
    1px solid rgba(148, 163, 184, 0.14);
  background:
    rgba(148, 163, 184, 0.055);
}

.adaptive-journey-metric span {
  display: block;
  margin-bottom: 4px;
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  opacity: 0.58;
}

.adaptive-journey-metric strong {
  display: block;
  overflow-wrap: anywhere;
  font-size: 13px;
}

details.adaptive-iteration-card {
  overflow: hidden;
}

details.adaptive-iteration-card > summary {
  list-style: none;
}

details.adaptive-iteration-card > summary::-webkit-details-marker {
  display: none;
}

.adaptive-iteration-card[open] {
  background: rgba(15, 23, 42, 0.23);
}

.adaptive-iteration-final {
  border-color:
    rgba(148, 163, 184, 0.30);
}

.adaptive-iteration-title {
  display: flex;
  align-items: center;
  min-width: 0;
  gap: 8px;
}

.adaptive-iteration-title > div {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.adaptive-iteration-chevron {
  display: inline-block;
  font-size: 21px;
  line-height: 1;
  opacity: 0.55;
  transition: transform 0.18s ease;
}

.adaptive-iteration-card[open]
  .adaptive-iteration-chevron {
  transform: rotate(90deg);
}

.adaptive-iteration-header {
  cursor: pointer;
  user-select: none;
}

.adaptive-iteration-header:hover {
  opacity: 0.92;
}

.adaptive-iteration-header:focus-visible {
  outline:
    2px solid rgba(96, 165, 250, 0.65);
  outline-offset: 4px;
  border-radius: 8px;
}

.adaptive-iteration-body {
  padding-top: 2px;
}

.adaptive-value-summary-empty {
  font-style: italic;
  opacity: 0.5;
}

.adaptive-stopping-final {
  border-color:
    rgba(245, 158, 11, 0.25);
}

@media (max-width: 980px) {
  .adaptive-journey-summary {
    grid-template-columns:
      repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 620px) {
  .adaptive-journey-summary {
    grid-template-columns: 1fr;
  }

  .adaptive-iteration-header {
    align-items: flex-start;
  }

  .research-value-badge {
    white-space: normal;
    text-align: right;
  }
}



.runtime-degradation-panel {
  margin-top: 1rem;
  padding: 1rem;
  border: 1px solid var(--border-color, rgba(148, 163, 184, 0.24));
  border-radius: 14px;
}

.runtime-degradation-heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
  margin-bottom: 0.85rem;
}

.runtime-degradation-heading h4 {
  margin: 0.15rem 0 0;
}

.runtime-degradation-description {
  margin: 0.35rem 0 0;
  max-width: 720px;
  opacity: 0.72;
  line-height: 1.5;
}

.runtime-degradation-count {
  flex: 0 0 auto;
  font-size: 0.78rem;
  opacity: 0.72;
}

.runtime-notice-list {
  display: grid;
  gap: 0.65rem;
}

.runtime-notice-card {
  padding: 0.8rem 0.9rem;
  border-radius: 10px;
  border: 1px solid rgba(148, 163, 184, 0.18);
  background: rgba(148, 163, 184, 0.05);
}

.runtime-notice-warning {
  border-color: rgba(245, 158, 11, 0.3);
  background: rgba(245, 158, 11, 0.06);
}

.runtime-notice-neutral {
  border-color: rgba(148, 163, 184, 0.22);
}

.runtime-notice-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
}

.runtime-notice-header strong {
  font-size: 0.92rem;
}

.runtime-notice-badge {
  flex: 0 0 auto;
  padding: 0.18rem 0.5rem;
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.1);
  font-size: 0.72rem;
  font-weight: 600;
}

.runtime-notice-card p {
  margin: 0.45rem 0 0;
  font-size: 0.84rem;
  line-height: 1.5;
  opacity: 0.78;
}

@media (max-width: 720px) {
  .runtime-degradation-heading,
  .runtime-notice-header {
    flex-direction: column;
  }

  .runtime-notice-badge {
    align-self: flex-start;
  }
}



.llm-circuit-banner {
  margin-bottom: 0.8rem;
  padding: 0.85rem 0.95rem;
  border: 1px solid rgba(148, 163, 184, 0.22);
  border-radius: 10px;
  background: rgba(148, 163, 184, 0.04);
}

.llm-circuit-open {
  border-color: rgba(245, 158, 11, 0.34);
  background: rgba(245, 158, 11, 0.07);
}

.llm-circuit-closed {
  border-color: rgba(148, 163, 184, 0.18);
}

.llm-circuit-main {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.8rem;
}

.llm-circuit-main > div {
  display: flex;
  align-items: center;
  gap: 0.55rem;
}

.llm-circuit-label {
  font-size: 0.78rem;
  opacity: 0.7;
}

.llm-circuit-main strong {
  font-size: 0.82rem;
  letter-spacing: 0.04em;
}

.llm-circuit-state {
  font-size: 0.76rem;
  opacity: 0.72;
}

.llm-circuit-details {
  display: flex;
  flex-wrap: wrap;
  gap: 0.55rem 1.25rem;
  margin-top: 0.65rem;
  font-size: 0.78rem;
  opacity: 0.82;
}

.llm-circuit-description {
  margin: 0.65rem 0 0;
  font-size: 0.8rem;
  line-height: 1.5;
  opacity: 0.74;
}

@media (max-width: 720px) {
  .llm-circuit-main {
    align-items: flex-start;
    flex-direction: column;
  }

  .llm-circuit-details {
    flex-direction: column;
    gap: 0.35rem;
  }
}

</style>
