"use client";

import { useEffect, useRef, useState } from "react";

import {
  streamChat,
  streamContinue,
  fetchAgentHealth,
  type AgentEvent,
  type AgentHealth,
  type ChatRequest,
} from "@/lib/agent-api";
import { usePageBridge } from "@/lib/agent-bridge";
import { Markdown } from "@/components/agent/markdown";
import { pickSuggestions, type Suggestion } from "@/lib/agent-suggestions";
import { cn } from "@/lib/cn";

type ToolStatus = "running" | "client" | "done";

type ChatItem =
  | { kind: "user"; text: string }
  | { kind: "assistant"; text: string }
  | { kind: "reasoning"; text: string }
  | { kind: "tool"; id: string; name: string; args: unknown; status: ToolStatus; result?: unknown }
  | { kind: "asset"; url: string }
  | { kind: "error"; text: string };

const TOOL_LABEL: Record<string, string> = {
  search_characters: "检索字库",
  get_character_detail: "查字详情",
  get_database_stats: "字库统计",
  get_cl_analysis: "计算语言学分析",
  convert_text: "繁简转换",
  list_culture_analyses: "列出史脉分析",
  get_culture_analysis: "读史脉分析",
  web_search: "联网搜索",
  browse_page: "浏览网页",
  get_page_context: "读取页面状态",
  switch_tab: "切换标签页",
  set_convert_input: "填写转换文本",
  run_convert: "执行转换",
  set_evolution_search: "填写检索词",
  select_character: "打开字详情",
  open_merge_dashboard: "打开合并疑难总览",
  analyze_corpus_coverage: "语料覆盖率分析",
  set_culture_text: "填写古籍原文",
  run_culture_analysis: "执行史脉分析",
  list_skills: "列出技能",
  run_skill: "加载技能",
};

function labelFor(name: string): string {
  return TOOL_LABEL[name] ?? name;
}

export function AgentChat() {
  const bridge = usePageBridge();
  const [items, setItems] = useState<ChatItem[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [health, setHealth] = useState<AgentHealth | null>(null);
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);

  const sessionRef = useRef<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLTextAreaElement | null>(null);

  useEffect(() => {
    fetchAgentHealth().then(setHealth);
    queueMicrotask(() => setSuggestions(pickSuggestions(3)));
  }, []);

  // "问问助手" selection popup drops the quoted text into the composer.
  useEffect(() => {
    function onAsk(e: Event) {
      const text = (e as CustomEvent<string>).detail?.trim();
      if (!text) return;
      const quoted = `「${text}」`;
      setInput((prev) => (prev.trim() ? `${prev}\n${quoted}` : quoted));
      window.setTimeout(() => {
        const el = inputRef.current;
        if (el) {
          el.focus();
          el.setSelectionRange(el.value.length, el.value.length);
        }
      }, 60);
    }
    window.addEventListener("relumine:agent-ask", onAsk);
    return () => window.removeEventListener("relumine:agent-ask", onAsk);
  }, []);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
  }, [items]);

  // Stop wheel scrolling from chaining to the page behind the sidebar — both at
  // the scroll boundaries and when there's nothing to scroll. overscroll-contain
  // covers trackpads; this native (non-passive) guard covers mouse wheels too.
  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    function onWheel(e: WheelEvent) {
      const node = el!;
      const canScroll = node.scrollHeight > node.clientHeight;
      if (!canScroll) {
        e.preventDefault();
        return;
      }
      const atTop = node.scrollTop <= 0;
      const atBottom = node.scrollTop + node.clientHeight >= node.scrollHeight - 1;
      if ((atTop && e.deltaY < 0) || (atBottom && e.deltaY > 0)) {
        e.preventDefault();
      }
    }
    el.addEventListener("wheel", onWheel, { passive: false });
    return () => el.removeEventListener("wheel", onWheel);
  }, []);

  // ----- item updaters -----
  const push = (item: ChatItem) => setItems((prev) => [...prev, item]);

  const appendAssistantText = (text: string) =>
    setItems((prev) => {
      const last = prev[prev.length - 1];
      if (last && last.kind === "assistant") {
        return [...prev.slice(0, -1), { ...last, text: last.text + text }];
      }
      return [...prev, { kind: "assistant", text }];
    });

  const appendReasoningText = (text: string) =>
    setItems((prev) => {
      const last = prev[prev.length - 1];
      if (last && last.kind === "reasoning") {
        return [...prev.slice(0, -1), { ...last, text: last.text + text }];
      }
      return [...prev, { kind: "reasoning", text }];
    });

  const updateTool = (id: string, patch: Partial<Extract<ChatItem, { kind: "tool" }>>) =>
    setItems((prev) =>
      prev.map((it) => (it.kind === "tool" && it.id === id ? { ...it, ...patch } : it)),
    );

  // ----- conversation driver -----
  async function drive(firstBody: ChatRequest) {
    const ctrl = new AbortController();
    abortRef.current = ctrl;
    setBusy(true);
    let stream = streamChat(firstBody, ctrl.signal);
    try {
      while (true) {
        let pending: Extract<AgentEvent, { type: "client_tool_call" }> | null = null;
        for await (const ev of stream) {
          switch (ev.type) {
            case "session":
              sessionRef.current = ev.session_id;
              break;
            case "token":
              appendAssistantText(ev.text);
              break;
            case "reasoning":
              appendReasoningText(ev.text);
              break;
            case "tool_call":
              push({ kind: "tool", id: ev.id, name: ev.name, args: ev.args, status: "running" });
              break;
            case "tool_result":
              updateTool(ev.id, { status: "done", result: ev.result });
              break;
            case "asset":
              push({ kind: "asset", url: ev.url });
              break;
            case "client_tool_call":
              push({
                kind: "tool",
                id: ev.call_id,
                name: ev.name,
                args: ev.args,
                status: "client",
              });
              pending = ev;
              break;
            case "error":
              push({ kind: "error", text: ev.message });
              break;
            case "done":
              break;
          }
        }
        if (!pending || ctrl.signal.aborted) break;

        const raw = await bridge.runClientTool(pending.name, pending.args);
        let error: string | undefined;
        let result: unknown = raw;
        if (raw && typeof raw === "object" && "error" in raw) {
          error = String((raw as { error: unknown }).error);
          result = undefined;
        }
        updateTool(pending.call_id, { status: "done", result: error ? { error } : result });

        if (!sessionRef.current) break;
        stream = streamContinue(
          { session_id: sessionRef.current, call_id: pending.call_id, result, error },
          ctrl.signal,
        );
      }
    } finally {
      setBusy(false);
      abortRef.current = null;
    }
  }

  function submit(raw: string) {
    const text = raw.trim();
    if (!text || busy) return;
    setInput("");
    push({ kind: "user", text });
    const snapshot = bridge.collectSnapshot();
    void drive({ message: text, session_id: sessionRef.current, page_context: snapshot });
  }

  function send() {
    submit(input);
  }

  function stop() {
    abortRef.current?.abort();
    setBusy(false);
  }

  function reset() {
    abortRef.current?.abort();
    sessionRef.current = null;
    setItems([]);
    setBusy(false);
  }

  const notConfigured = health && !health.deepseek_configured;

  return (
    <div className="flex h-full flex-col">
      {notConfigured ? (
        <div className="border-b border-line bg-accent/5 px-4 py-2 text-xs text-accent font-sans">
          未配置 DeepSeek API Key（apps/api/.env 的 OCRFORGE_WEB_LLM_API_KEY），对话不可用。
        </div>
      ) : null}

      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto overscroll-contain px-4 py-4 space-y-3"
      >
        {items.length === 0 ? (
          <EmptyState
            suggestions={suggestions}
            onPick={submit}
            onReshuffle={() => setSuggestions(pickSuggestions(3))}
          />
        ) : (
          items.map((it, i) => <ChatItemView key={i} item={it} />)
        )}
      </div>

      <div className="border-t border-line p-3">
        <div className="flex items-end gap-2">
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                send();
              }
            }}
            rows={2}
            placeholder="问汉字、繁简、古籍，或让我操作页面…"
            className={cn(
              "flex-1 resize-none rounded-[var(--radius)] border border-line bg-bg",
              "px-3 py-2 text-sm text-ink outline-none placeholder:text-ink-mute/60",
              "focus:border-accent/50 font-serif leading-relaxed",
            )}
          />
          {busy ? (
            <button
              onClick={stop}
              className="shrink-0 rounded-[var(--radius)] border border-line px-3 py-2 text-xs text-ink-soft hover:text-accent"
            >
              停止
            </button>
          ) : (
            <button
              onClick={send}
              disabled={!input.trim()}
              className={cn(
                "shrink-0 rounded-[var(--radius)] bg-accent px-4 py-2 text-xs text-surface",
                "disabled:opacity-40 hover:bg-accent/90 transition-colors",
              )}
            >
              发送
            </button>
          )}
        </div>
        <div className="mt-2 flex items-center justify-between text-[10px] font-sans tracking-wider text-ink-mute">
          <span>{health ? `模型 ${health.model}` : "…"}</span>
          <button onClick={reset} className="hover:text-accent">
            清空对话
          </button>
        </div>
      </div>
    </div>
  );
}

function EmptyState({
  suggestions,
  onPick,
  onReshuffle,
}: {
  suggestions: Suggestion[];
  onPick: (prompt: string) => void;
  onReshuffle: () => void;
}) {
  return (
    <div className="mt-8 text-center text-sm text-ink-mute font-sans leading-relaxed">
      <p className="text-ink-soft">古籍重光 · 智能助手</p>

      {suggestions.length > 0 ? (
        <div className="mt-5">
          <div className="flex items-center justify-center gap-2 text-xs text-ink-mute">
            <span>试试这些</span>
            <button
              onClick={onReshuffle}
              className="text-ink-mute hover:text-accent transition-colors"
              title="换一批"
            >
              ↻ 换一批
            </button>
          </div>
          <div className="mt-3 flex flex-col gap-2">
            {suggestions.map((s) => (
              <button
                key={s.label}
                onClick={() => onPick(s.prompt)}
                className={cn(
                  "mx-auto w-full max-w-[280px] rounded-[var(--radius)] border border-line bg-bg/60",
                  "px-3 py-2 text-left text-xs text-ink-soft transition-colors",
                  "hover:border-accent/50 hover:text-accent",
                )}
              >
                {s.label}
              </button>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  );
}

function ChatItemView({ item }: { item: ChatItem }) {
  if (item.kind === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[85%] rounded-[var(--radius)] bg-accent/10 px-3 py-2 text-sm text-ink whitespace-pre-wrap break-words">
          {item.text}
        </div>
      </div>
    );
  }
  if (item.kind === "assistant") {
    return <Markdown>{item.text}</Markdown>;
  }
  if (item.kind === "reasoning") {
    return (
      <details className="rounded-[var(--radius)] bg-bg/40 px-3 py-1.5 text-xs font-sans text-ink-mute">
        <summary className="cursor-pointer list-none select-none hover:text-ink-soft">
          思考过程
        </summary>
        <div className="mt-1 whitespace-pre-wrap break-words leading-relaxed opacity-80">
          {item.text}
        </div>
      </details>
    );
  }
  if (item.kind === "error") {
    return (
      <div className="rounded-[var(--radius)] border border-accent/30 bg-accent/5 px-3 py-2 text-xs text-accent">
        {item.text}
      </div>
    );
  }
  if (item.kind === "asset") {
    return (
      // Agent screenshots use runtime blob/data URLs that next/image cannot optimize.
      // eslint-disable-next-line @next/next/no-img-element
      <img
        src={item.url}
        alt="agent screenshot"
        className="rounded-[var(--radius)] border border-line"
      />
    );
  }
  return <ToolCard item={item} />;
}

function ToolCard({ item }: { item: Extract<ChatItem, { kind: "tool" }> }) {
  const running = item.status !== "done";
  return (
    <details className="rounded-[var(--radius)] border border-line bg-bg/60 px-3 py-2 text-xs font-sans">
      <summary className="cursor-pointer list-none flex items-center gap-2 text-ink-soft">
        <span
          className={cn(
            "inline-block h-1.5 w-1.5 rounded-full",
            running ? "bg-accent-gold animate-pulse" : "bg-ink-mute/50",
          )}
        />
        <span className="text-ink">
          {item.status === "client" ? "操作页面 · " : ""}
          {labelFor(item.name)}
        </span>
        <span className="text-ink-mute">{running ? "…" : "✓"}</span>
      </summary>
      <div className="mt-2 space-y-1 text-ink-mute">
        {Object.keys((item.args as object) ?? {}).length > 0 ? (
          <pre className="overflow-x-auto whitespace-pre-wrap break-words">
            {JSON.stringify(item.args, null, 2)}
          </pre>
        ) : null}
        {item.result !== undefined ? (
          <pre className="overflow-x-auto whitespace-pre-wrap break-words border-t border-line pt-1">
            {typeof item.result === "string"
              ? item.result
              : JSON.stringify(item.result, null, 2)}
          </pre>
        ) : null}
      </div>
    </details>
  );
}
