"use client";

import { useState } from "react";
import * as HoverCard from "@radix-ui/react-hover-card";
import { toast } from "sonner";

import { api, ApiError } from "@/lib/api";
import type { Collision, ConvertResponse, Direction } from "@/lib/types";
import { cn } from "@/lib/cn";
import { useRegisterSnapshot, useRegisterAction } from "@/lib/agent-bridge";

import { SectionMark } from "@/components/chinese/SectionMark";
import { GoldRule } from "@/components/chinese/GoldRule";
import { CornerBrackets } from "@/components/chinese/CornerBrackets";

const EXAMPLES: { label: string; text: string; dir: Direction }[] = [
  { label: "學而時習之，不亦說乎", text: "學而時習之，不亦說乎", dir: "t2s" },
  { label: "皇后與發財", text: "皇后與發財", dir: "t2s" },
  { label: "面對麵食的台北颱風", text: "面對麵食的台北颱風", dir: "t2s" },
];

export function ConvertPanel() {
  const [direction, setDirection] = useState<Direction>("t2s");
  const [input, setInput] = useState("");
  const [result, setResult] = useState<ConvertResponse | null>(null);
  const [pending, setPending] = useState(false);

  async function run(): Promise<ConvertResponse | undefined> {
    if (!input.trim()) {
      toast.message("先输入文字再转换");
      return undefined;
    }
    setPending(true);
    try {
      const res = await api.convert(input, direction);
      setResult(res);
      return res;
    } catch (e) {
      const detail = e instanceof ApiError ? e.message : "转换失败";
      toast.error(detail);
      return undefined;
    } finally {
      setPending(false);
    }
  }

  // ----- Agent bridge: let the assistant read & operate this panel -----
  useRegisterSnapshot("convert", () => ({
    direction,
    input,
    result: result?.result ?? null,
    collisionCount: result?.collisions.length ?? 0,
  }));
  useRegisterAction("set_convert_input", (args) => {
    const text = String(args.text ?? "");
    setInput(text);
    if (args.direction === "t2s" || args.direction === "s2t") {
      setDirection(args.direction);
    }
    setResult(null);
    return { ok: true, input: text };
  });
  useRegisterAction("run_convert", async () => {
    const res = await run();
    return res ? { ok: true, result: res.result } : { error: "无输入或转换失败" };
  });

  function loadExample(ex: (typeof EXAMPLES)[number]) {
    setDirection(ex.dir);
    setInput(ex.text);
    setResult(null);
  }

  const swap = () => {
    setDirection((d) => (d === "t2s" ? "s2t" : "t2s"));
    if (result) {
      setInput(result.result);
      setResult(null);
    }
  };

  return (
    <section className="rounded-[var(--radius)] border border-line bg-surface p-8 md:p-12 relative animate-ink-rise">
      <CornerBrackets />
      <header className="flex flex-col md:flex-row md:items-end md:justify-between gap-4">
        <SectionMark
          title={direction === "t2s" ? "繁体 → 简体" : "简体 → 繁体"}
          subtitle="繁-简汉字映射数据库"
        />
        <div className="flex items-center gap-3 text-xs font-sans tracking-wider uppercase text-ink-mute">
          {EXAMPLES.map((ex) => (
            <button
              key={ex.label}
              onClick={() => loadExample(ex)}
              className="hover:text-accent transition-colors duration-200"
            >
              · {ex.label}
            </button>
          ))}
        </div>
      </header>

      <div className="mt-8 grid grid-cols-1 md:grid-cols-[1fr_auto_1fr] gap-px bg-line">
        <div className="bg-surface p-6">
          <div className="text-xs font-sans tracking-[0.16em] uppercase text-ink-mute mb-3">
            输入 · {direction === "t2s" ? "繁體" : "简体"}
          </div>
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            rows={8}
            placeholder={
              direction === "t2s"
                ? "在此貼入繁體文字…"
                : "在此粘贴简体文字…"
            }
            className={cn(
              "w-full resize-none bg-transparent outline-none",
              "font-serif text-base md:text-lg leading-[1.9] tracking-[0.04em] text-ink",
              "placeholder:text-ink-mute/60",
            )}
          />
        </div>

        <div className="bg-surface flex md:flex-col items-center justify-center gap-2 p-4 md:px-6">
          <button
            type="button"
            onClick={run}
            disabled={pending}
            className={cn(
              "group flex flex-col items-center gap-1 px-3 py-2",
              "font-serif text-sm text-ink hover:text-accent transition-colors duration-200",
              pending && "opacity-50",
            )}
          >
            <span>转 →</span>
            <GoldRule className="opacity-0 group-hover:opacity-80 transition-opacity duration-300" />
          </button>
          <button
            type="button"
            onClick={swap}
            className="px-3 py-1 font-sans text-[10px] tracking-[0.16em] uppercase text-ink-mute hover:text-ink-soft"
          >
            {direction === "t2s" ? "↻ s2t" : "↻ t2s"}
          </button>
        </div>

        <div className="bg-surface p-6">
          <div className="text-xs font-sans tracking-[0.16em] uppercase text-ink-mute mb-3">
            输出 · {direction === "t2s" ? "简体" : "繁體"}
          </div>
          {result ? (
            <HighlightedResult
              text={result.result}
              collisions={result.collisions}
              isSimplifiedSide={
                (direction === "t2s") /* output is simplified */
              }
            />
          ) : (
            <div className="font-serif text-base md:text-lg leading-[1.9] tracking-[0.04em] text-ink-mute/60">
              {pending ? "转换中…" : "等待输入"}
            </div>
          )}
        </div>
      </div>

      {result && result.collisions.length > 0 ? (
        <p className="mt-4 text-xs font-sans tracking-wider text-ink-mute">
          虚线下划线表示多对一合并字，悬停可见来源繁体集合。
        </p>
      ) : null}
    </section>
  );
}

function HighlightedResult({
  text,
  collisions,
  isSimplifiedSide,
}: {
  text: string;
  collisions: Collision[];
  isSimplifiedSide: boolean;
}) {
  const map = new Map<number, Collision>();
  for (const c of collisions) map.set(c.position, c);

  // collisions positions are in the simplified-side string. We only highlight
  // when the displayed text *is* the simplified side.
  return (
    <div className="font-serif text-base md:text-lg leading-[1.9] tracking-[0.04em] text-ink whitespace-pre-wrap break-words">
      {Array.from(text).map((ch, i) => {
        const hit = isSimplifiedSide ? map.get(i) : undefined;
        if (!hit) return <span key={i}>{ch}</span>;
        return (
          <HoverCard.Root key={i} openDelay={120} closeDelay={80}>
            <HoverCard.Trigger asChild>
              <span
                className={cn(
                  "text-accent border-b border-dashed border-accent/70",
                  "cursor-help",
                )}
              >
                {ch}
              </span>
            </HoverCard.Trigger>
            <HoverCard.Portal>
              <HoverCard.Content
                side="top"
                align="center"
                sideOffset={6}
                className={cn(
                  "z-50 bg-surface border border-line rounded-[var(--radius)]",
                  "px-4 py-3 shadow-[0_1px_0_0_var(--color-line)]",
                  "font-serif text-sm text-ink",
                  "data-[state=open]:animate-ink-rise-soft",
                )}
              >
                <div className="text-xs font-sans tracking-wider uppercase text-ink-mute mb-1">
                  多对一 · 源繁体
                </div>
                <div className="text-2xl tracking-[0.08em]">
                  {hit.source_traditionals.join(" / ")}
                </div>
                <HoverCard.Arrow className="fill-line" />
              </HoverCard.Content>
            </HoverCard.Portal>
          </HoverCard.Root>
        );
      })}
    </div>
  );
}
