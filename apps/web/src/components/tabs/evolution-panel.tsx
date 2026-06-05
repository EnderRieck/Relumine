"use client";

import { useEffect, useState } from "react";
import { toast } from "sonner";

import { api, ApiError } from "@/lib/api";
import type { CharRecord, CharSummary } from "@/lib/types";
import { cn } from "@/lib/cn";

import { SectionMark } from "@/components/chinese/SectionMark";
import { CornerBrackets } from "@/components/chinese/CornerBrackets";

export function EvolutionPanel() {
  const [list, setList] = useState<CharSummary[]>([]);
  const [active, setActive] = useState<string | null>(null);
  const [record, setRecord] = useState<CharRecord | null>(null);
  const [loadingList, setLoadingList] = useState(true);
  const [loadingRecord, setLoadingRecord] = useState(false);

  useEffect(() => {
    let cancelled = false;
    api.evolution
      .list()
      .then((l) => {
        if (cancelled) return;
        setList(l);
        if (l.length && active === null) {
          setActive(l[0].simplified);
        }
      })
      .catch((e) => {
        const detail = e instanceof ApiError ? e.message : "加载失败";
        toast.error(detail);
      })
      .finally(() => !cancelled && setLoadingList(false));
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!active) return;
    let cancelled = false;
    setLoadingRecord(true);
    api.evolution
      .get(active)
      .then((r) => !cancelled && setRecord(r))
      .catch((e) => {
        if (cancelled) return;
        const detail = e instanceof ApiError ? e.message : "加载失败";
        toast.error(detail);
      })
      .finally(() => !cancelled && setLoadingRecord(false));
    return () => {
      cancelled = true;
    };
  }, [active]);

  return (
    <section className="relative rounded-[var(--radius)] border border-line bg-surface p-8 md:p-12 animate-ink-rise">
      <CornerBrackets />
      <SectionMark title="形声流变" subtitle="一简 · 二简 · 多对一合并" />

      <div className="mt-8 grid grid-cols-1 lg:grid-cols-[260px_1fr] gap-10">
        <div>
          <div className="text-xs font-sans tracking-[0.16em] uppercase text-ink-mute mb-3">
            字 · {loadingList ? "…" : list.length}
          </div>
          <div className="grid grid-cols-5 lg:grid-cols-4 gap-px bg-line">
            {list.map((c, idx) => {
              const isActive = c.simplified === active;
              return (
                <button
                  key={c.simplified}
                  onClick={() => setActive(c.simplified)}
                  className={cn(
                    "relative aspect-square bg-surface flex items-center justify-center",
                    "font-serif text-2xl text-ink transition-colors duration-200",
                    "hover:bg-bg animate-ink-rise-soft",
                    isActive && "bg-bg",
                  )}
                  style={{ animationDelay: `${idx * 60}ms` }}
                >
                  {c.simplified}
                  <span
                    aria-hidden
                    className={cn(
                      "absolute bottom-1.5 left-1.5 h-1 w-1 transition-opacity duration-200",
                      isActive ? "bg-accent opacity-100" : "opacity-0",
                    )}
                  />
                </button>
              );
            })}
          </div>
        </div>

        <div>
          {!record ? (
            <div className="text-sm text-ink-mute">{loadingRecord ? "加载中…" : "选择一个字"}</div>
          ) : (
            <RecordView record={record} />
          )}
        </div>
      </div>
    </section>
  );
}

function RecordView({ record }: { record: CharRecord }) {
  return (
    <article key={record.simplified}>
      <header className="flex items-baseline gap-6 mb-8">
        <div
          className="font-serif text-6xl tracking-[0.04em] text-ink animate-ink-rise"
        >
          {record.simplified}
        </div>
        <div
          className="text-ink-mute font-serif text-3xl animate-ink-rise-soft"
          style={{ animationDelay: "120ms" }}
        >
          ←
        </div>
        <div
          className="font-serif text-5xl tracking-[0.04em] text-ink-soft animate-ink-rise"
          style={{ animationDelay: "200ms" }}
        >
          {record.traditional}
        </div>
        {record.pinyin ? (
          <div className="ml-2 text-sm font-sans tracking-wider text-ink-mute lowercase">
            {record.pinyin}
          </div>
        ) : null}
      </header>

      {record.merges.length > 0 ? (
        <div className="mb-6 inline-flex items-center gap-3 px-3 py-1.5 border border-accent/40 text-xs font-sans tracking-[0.16em] uppercase text-accent">
          多对一合并：{record.merges.join(" / ")} → {record.simplified}
        </div>
      ) : null}

      <div className="relative pb-6">
        {/* 时间轴竖线：从首个 bullet 顶部延伸到底部箭头 */}
        <div
          aria-hidden
          className="absolute left-3 top-2 bottom-3 w-px bg-line origin-top animate-line-draw-y"
          style={{ animationDelay: "240ms", animationDuration: "700ms" }}
        />
        {/* 流转箭头：竖线收尾，▼ 表演化方向 */}
        <svg
          aria-hidden
          viewBox="0 0 12 10"
          className="absolute left-3 -translate-x-1/2 bottom-0 w-3 h-2.5 text-accent-gold/60 animate-fade-in"
          style={{ animationDelay: "900ms" }}
        >
          <path d="M 0 0 L 6 10 L 12 0 Z" fill="currentColor" />
        </svg>

        <ol className="relative">
          {record.stages.map((s, i) => (
            <li
              key={i}
              className="relative pl-12 pb-8 last:pb-0 animate-ink-rise-soft"
              style={{ animationDelay: `${280 + i * 90}ms` }}
            >
              <span
                aria-hidden
                className="absolute left-2 top-2.5 block w-2 h-2 rounded-full bg-accent-gold ring-2 ring-bg animate-stamp-in"
                style={{ animationDelay: `${320 + i * 90}ms` }}
              />
              <div className="grid grid-cols-1 md:grid-cols-[120px_1fr] gap-x-6 gap-y-1">
                <div>
                  <div className="font-serif text-base text-ink">{s.era}</div>
                </div>
                <div>
                  <div className="font-serif text-4xl tracking-[0.08em] text-ink leading-none">
                    {s.form}
                  </div>
                  {s.note ? (
                    <div className="mt-2 text-sm font-serif leading-[1.9] text-ink-soft">
                      {s.note}
                    </div>
                  ) : null}
                </div>
            </div>
          </li>
        ))}
      </ol>
      </div>

      {record.notes ? (
        <footer className="mt-8 pt-6 border-t border-line">
          <div className="text-xs font-sans tracking-[0.16em] uppercase text-ink-mute mb-2">
            注
          </div>
          <p className="font-serif text-sm leading-[1.9] text-ink-soft">{record.notes}</p>
        </footer>
      ) : null}
    </article>
  );
}
