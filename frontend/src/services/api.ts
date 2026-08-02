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

      return event.type === "error" || event.type === "done";
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
