import type { ReactNode } from "react";
import { cn } from "@/lib/cn";

/**
 * 章节标记：左侧 2px 朱砂竖线（从顶部"拉下"） + 标题（淡入上移）。
 * 可选 icon：以当前色域的小型线描图标点题，强化"重点"指引。
 */
export function SectionMark({
  title,
  subtitle,
  icon,
  className,
}: {
  title: string;
  subtitle?: string;
  icon?: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("flex items-start gap-3", className)}>
      <span
        aria-hidden
        className="mt-1.5 block w-[2px] h-4 bg-accent origin-top animate-line-draw-y"
      />
      {icon ? (
        <span
          aria-hidden
          className="mt-0.5 inline-flex h-7 w-7 shrink-0 items-center justify-center border border-[var(--tone,var(--color-accent-gold))] text-[var(--tone,var(--color-accent))] animate-ink-rise-soft"
        >
          {icon}
        </span>
      ) : null}
      <div>
        <div className="font-serif text-lg tracking-[0.08em] text-ink animate-ink-rise-soft">
          {title}
        </div>
        {subtitle ? (
          <div
            className="mt-0.5 text-xs text-ink-mute font-sans tracking-wider uppercase animate-ink-rise-soft"
            style={{ animationDelay: "100ms" }}
          >
            {subtitle}
          </div>
        ) : null}
      </div>
    </div>
  );
}
