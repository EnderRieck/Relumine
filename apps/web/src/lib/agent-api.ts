// SSE client for the Agent harness. Next 16's EventSource can't POST, so we
// read the text/event-stream body manually from a fetch ReadableStream.

export type AgentEvent =
  | { type: "session"; session_id: string }
  | { type: "token"; text: string }
  | { type: "reasoning"; text: string }
  | { type: "tool_call"; id: string; name: string; args: unknown }
  | { type: "tool_result"; id: string; name: string; result: unknown }
  | { type: "client_tool_call"; call_id: string; name: string; args: Record<string, unknown> }
  | { type: "asset"; url: string }
  | { type: "done"; reason?: string }
  | { type: "error"; message: string };

export type SkillInfo = {
  name: string;
  description: string;
  tools: string[];
};

export type AgentHealth = {
  deepseek_configured: boolean;
  model: string;
  brave_configured: boolean;
  browser_enabled: boolean;
  skills: string[];
  tools: string[];
};

export type ChatRequest = {
  message: string;
  session_id?: string | null;
  page_context?: unknown;
};

export type ContinueRequest = {
  session_id: string;
  call_id: string;
  result?: unknown;
  error?: string | null;
};

async function* readSSE(
  res: Response,
  signal?: AbortSignal,
): AsyncGenerator<AgentEvent> {
  if (!res.body) {
    yield { type: "error", message: `没有响应体 (HTTP ${res.status})` };
    return;
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  try {
    while (true) {
      if (signal?.aborted) break;
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let sep: number;
      while ((sep = buffer.indexOf("\n\n")) >= 0) {
        const chunk = buffer.slice(0, sep);
        buffer = buffer.slice(sep + 2);
        const dataLine = chunk
          .split("\n")
          .find((line) => line.startsWith("data:"));
        if (!dataLine) continue;
        const json = dataLine.slice(5).trim();
        if (!json) continue;
        try {
          yield JSON.parse(json) as AgentEvent;
        } catch {
          // ignore malformed frame
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
}

async function* postStream(
  url: string,
  body: unknown,
  signal?: AbortSignal,
): AsyncGenerator<AgentEvent> {
  let res: Response;
  try {
    res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal,
    });
  } catch (e) {
    if ((e as Error).name === "AbortError") return;
    yield { type: "error", message: `请求失败：${(e as Error).message}` };
    return;
  }
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const data = await res.json();
      if (data?.detail) detail = String(data.detail);
    } catch {
      /* keep status */
    }
    yield { type: "error", message: detail };
    return;
  }
  yield* readSSE(res, signal);
}

export function streamChat(
  body: ChatRequest,
  signal?: AbortSignal,
): AsyncGenerator<AgentEvent> {
  return postStream("/api/agent/chat", body, signal);
}

export function streamContinue(
  body: ContinueRequest,
  signal?: AbortSignal,
): AsyncGenerator<AgentEvent> {
  return postStream("/api/agent/continue", body, signal);
}

export async function fetchAgentHealth(): Promise<AgentHealth | null> {
  try {
    const res = await fetch("/api/agent/health", { cache: "no-store" });
    if (!res.ok) return null;
    return (await res.json()) as AgentHealth;
  } catch {
    return null;
  }
}
