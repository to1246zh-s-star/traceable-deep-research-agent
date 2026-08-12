const baseURL =
  import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export interface ResearchRequest {
  topic: string;
  search_api?: string;
}

export interface ResearchStreamEvent {
  type: string;
  [key: string]: unknown;
}

export interface StreamOptions {
  signal?: AbortSignal;
}

function parseSseBlock(rawBlock: string): ResearchStreamEvent | null {
  const dataLines = rawBlock
    .split("\n")
    .filter((line) => line.startsWith("data:"))
    .map((line) => line.slice(5).trimStart());

  if (!dataLines.length) {
    return null;
  }

  const payload = dataLines.join("\n").trim();

  if (!payload) {
    return null;
  }

  return JSON.parse(payload) as ResearchStreamEvent;
}

export async function runResearchStream(
  payload: ResearchRequest,
  onEvent: (event: ResearchStreamEvent) => void,
  options: StreamOptions = {}
): Promise<void> {
  const response = await fetch(`${baseURL}/research/stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "text/event-stream"
    },
    body: JSON.stringify(payload),
    signal: options.signal
  });

  if (!response.ok) {
    const errorText = await response.text().catch(() => "");
    throw new Error(
      errorText || `研究请求失败，状态码：${response.status}`
    );
  }

  if (!response.body) {
    throw new Error("浏览器不支持流式响应，无法获取研究进度");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";

  const dispatchBlock = (rawBlock: string): boolean => {
    const trimmed = rawBlock.trim();

    if (!trimmed) {
      return false;
    }

    try {
      const event = parseSseBlock(trimmed);

      if (!event) {
        return false;
      }

      onEvent(event);

      return event.type === "error";
    } catch (error) {
      console.error("解析流式事件失败：", error, trimmed);
      return false;
    }
  };

  while (true) {
    const { value, done } = await reader.read();

    buffer += decoder.decode(
      value || new Uint8Array(),
      { stream: !done }
    );

    // 统一处理 Windows/代理可能产生的 CRLF。
    buffer = buffer.replace(/\r\n/g, "\n");

    let boundary = buffer.indexOf("\n\n");

    while (boundary !== -1) {
      const rawBlock = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);

      if (dispatchBlock(rawBlock)) {
        await reader.cancel().catch(() => undefined);
        return;
      }

      boundary = buffer.indexOf("\n\n");
    }

    if (done) {
      // 处理没有以空行结尾的最后一个 SSE 事件。
      if (buffer.trim()) {
        dispatchBlock(buffer);
      }
      break;
    }
  }
}

export interface ExecutionTraceResponse {
  trace_id: string;
  task_id: number;
  status: string;
  started_at: string | null;
  finished_at: string | null;
  duration_ms: number | null;
  current_stage: string | null;
  retry_count: number;
  error_type: string | null;
  error_message: string | null;
}

export interface ExecutionEventResponse {
  schema_version: number;
  event_id: string;
  trace_id: string;
  timestamp: string;
  task_id: number;
  event_type: string;
  stage: string;
  metadata: Record<string, unknown>;
}

export interface EvidenceResponse {
  evidence_id: string;
  task_id: number;
  trace_id: string;
  query: string;
  backend: string;
  source_title: string | null;
  source_url: string | null;
  snippet: string | null;
  content: string | null;
  source_rank: number | null;
  created_at: string;
}

export interface EvidenceListResponse {
  research_id: string;
  evidence: EvidenceResponse[];
}

export interface EvidenceDetailResponse {
  research_id: string;
  evidence: EvidenceResponse;
}

export interface ClaimResponse {
  claim_id: string;
  task_id: number;
  trace_id: string;
  text: string;
  evidence_ids: string[];
  created_at: string;
}

export interface ClaimListResponse {
  research_id: string;
  claims: ClaimResponse[];
}

export interface ClaimDetailResponse {
  research_id: string;
  claim: ClaimResponse;
  evidence: EvidenceResponse[];
}

export interface TraceListResponse {
  research_id: string;
  traces: ExecutionTraceResponse[];
}

export interface TraceDetailResponse {
  research_id: string;
  trace: ExecutionTraceResponse;
  events: ExecutionEventResponse[];
}

export interface TraceEventsResponse {
  research_id: string;
  trace_id: string;
  events: ExecutionEventResponse[];
}

async function requestJson<T>(path: string): Promise<T> {
  const response = await fetch(`${baseURL}${path}`, {
    headers: {
      Accept: "application/json"
    }
  });

  if (!response.ok) {
    const errorText = await response.text().catch(() => "");
    throw new Error(
      errorText || `请求失败，状态码：${response.status}`
    );
  }

  return (await response.json()) as T;
}

export function listResearchTraces(
  researchId: string
): Promise<TraceListResponse> {
  return requestJson<TraceListResponse>(
    `/research/${encodeURIComponent(researchId)}/traces`
  );
}

export function getResearchTrace(
  researchId: string,
  traceId: string
): Promise<TraceDetailResponse> {
  return requestJson<TraceDetailResponse>(
    `/research/${encodeURIComponent(researchId)}/traces/${encodeURIComponent(
      traceId
    )}`
  );
}

export function listResearchEvidence(
  researchId: string
): Promise<EvidenceListResponse> {
  return requestJson<EvidenceListResponse>(
    `/research/${encodeURIComponent(researchId)}/evidence`
  );
}

export function getResearchEvidence(
  researchId: string,
  evidenceId: string
): Promise<EvidenceDetailResponse> {
  return requestJson<EvidenceDetailResponse>(
    `/research/${encodeURIComponent(researchId)}/evidence/${encodeURIComponent(
      evidenceId
    )}`
  );
}

export function listResearchClaims(
  researchId: string
): Promise<ClaimListResponse> {
  return requestJson<ClaimListResponse>(
    `/research/${encodeURIComponent(researchId)}/claims`
  );
}

export function getResearchClaim(
  researchId: string,
  claimId: string
): Promise<ClaimDetailResponse> {
  return requestJson<ClaimDetailResponse>(
    `/research/${encodeURIComponent(researchId)}/claims/${encodeURIComponent(
      claimId
    )}`
  );
}

export function getResearchTraceEvents(
  researchId: string,
  traceId: string
): Promise<TraceEventsResponse> {
  return requestJson<TraceEventsResponse>(
    `/research/${encodeURIComponent(researchId)}/traces/${encodeURIComponent(
      traceId
    )}/events`
  );
}


export interface ResearchReplayTaskResponse {
  task_id: number;
  title: string;
  intent: string;
  query: string;
  status: string;
  trace_ids: string[];
  claim_ids: string[];
  evidence_ids: string[];
}

export interface ResearchReplayEventResponse {
  timestamp: string | null;
  event_type: string;
  task_id: number | null;
  trace_id: string | null;
  reference_id: string | null;
  summary: string | null;
}

export interface ResearchReplayResponse {
  research_id: string;
  research_topic: string;
  task_count: number;
  trace_count: number;
  claim_count: number;
  evidence_count: number;
  tasks: ResearchReplayTaskResponse[];
  timeline: ResearchReplayEventResponse[];
}

export function getResearchReplay(
  researchId: string
): Promise<ResearchReplayResponse> {
  return requestJson<ResearchReplayResponse>(
    `/research/${encodeURIComponent(researchId)}/replay`
  );
}
