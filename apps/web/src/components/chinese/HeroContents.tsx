"use client";

import type { ComponentType } from "react";
import {
  IconConvert,
  IconScroll,
  IconBranch,
  IconMeridian,
} from "@/components/chinese/BrushIcons";

type Item = {
  value: string;
  ordinal: string;
  label: string;
  desc: string;
  tone: string;
  Icon: ComponentType<{ size?: number; className?: string }>;
};

const ITEMS: Item[] = [
  { value: "convert", ordinal: "壹", label: "繁简通译", desc: "多对一冲突提示", tone: "tone-convert", Icon: IconConvert },
  { value: "ocr", ordinal: "貳", label: "古籍识读", desc: "刻本图像到文本", tone: "tone-ocr", Icon: IconScroll },
  { value: "evolution", ordinal: "參", label: "形声流变", desc: "四库证据分析", tone: "tone-evolution", Icon: IconBranch },
  { value: "culture", ordinal: "肆", label: "史脉", desc: "人物地点关系", tone: "tone-culture", Icon: IconMeridian },
];

/**
 * 目録 —— 以书页目录的形制呈现四目所能，连点引线、卷次序号。
 * 点击即翻至对应卷（触发 Tabs 监听的 relumine:open-tab）。
 */
export function HeroContents() {
  const open = (value: string) => {
    window.dispatchEvent(new CustomEvent("relumine:open-tab", { detail: value }));
    if (typeof window !== "undefined") {
      window.scrollTo({ top: 0, behavior: "smooth" });
    }
  };

  return (
    <nav aria-label="功能目録" className="w-full">
      <div className="mb-3 flex items-center gap-3">
        <span className="eyebrow">目 録 · Contents</span>
        <span aria-hidden className="h-px flex-1 bg-line" />
      </div>
      <ul className="divide-y divide-line/60 border-y border-line/60">
        {ITEMS.map((it, i) => (
          <li key={it.value} className={it.tone}>
            <button
              type="button"
              onClick={() => open(it.value)}
              className="group flex w-full items-baseline gap-3 px-1 py-3.5 text-left outline-none transition-colors duration-200 hover:bg-[var(--tone-soft)] animate-ink-rise-soft"
              style={{ animationDelay: `${300 + i * 80}ms` }}
            >
              <span className="w-6 shrink-0 text-center font-serif text-lg leading-none text-[var(--tone)]">
                {it.ordinal}
              </span>
              <span className="shrink-0 font-serif text-base tracking-[0.04em] text-ink transition-colors group-hover:text-[var(--tone)]">
                {it.label}
              </span>
              <span aria-hidden className="leader" />
              <span className="shrink-0 font-sans text-[11px] tracking-[0.06em] text-ink-mute">
                {it.desc}
              </span>
              <it.Icon
                size={16}
                className="shrink-0 -translate-x-1 text-[var(--tone)] opacity-0 transition-all duration-200 group-hover:translate-x-0 group-hover:opacity-100"
              />
            </button>
          </li>
        ))}
      </ul>
    </nav>
  );
}
