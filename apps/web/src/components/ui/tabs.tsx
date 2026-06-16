"use client";

import { createContext, useContext, useEffect, useId, useState } from "react";
import { cn } from "@/lib/cn";

type TabsContextValue = {
  value: string;
  setValue: (v: string) => void;
  id: string;
};
const TabsCtx = createContext<TabsContextValue | null>(null);

function useTabsCtx() {
  const ctx = useContext(TabsCtx);
  if (!ctx) throw new Error("Tabs.* must be used inside <Tabs>");
  return ctx;
}

export function Tabs({
  defaultValue,
  children,
  className,
}: {
  defaultValue: string;
  children: React.ReactNode;
  className?: string;
}) {
  const [value, setValue] = useState(defaultValue);
  const id = useId();
  useEffect(() => {
    const openTab = (event: Event) => {
      const next = (event as CustomEvent<string>).detail;
      if (next) setValue(next);
    };
    window.addEventListener("relumine:open-tab", openTab);
    return () => window.removeEventListener("relumine:open-tab", openTab);
  }, []);
  return (
    <TabsCtx.Provider value={{ value, setValue, id }}>
      <div className={className}>{children}</div>
    </TabsCtx.Provider>
  );
}

export function TabsList({
  children,
  className,
  style,
}: {
  children: React.ReactNode;
  className?: string;
  style?: React.CSSProperties;
}) {
  return (
    <div
      role="tablist"
      style={style}
      className={cn(
        "relative flex flex-wrap items-end gap-3 border-b border-line/80 pb-3",
        className,
      )}
    >
      {children}
    </div>
  );
}

export function TabsTrigger({
  value,
  ordinal,
  label,
}: {
  value: string;
  ordinal: string;
  label: string;
}) {
  const { value: active, setValue, id } = useTabsCtx();
  const isActive = active === value;
  const tone =
    value === "convert"
      ? "tone-convert"
      : value === "ocr"
        ? "tone-ocr"
        : value === "evolution"
          ? "tone-evolution"
          : "tone-culture";
  return (
    <button
      type="button"
      role="tab"
      id={`${id}-trigger-${value}`}
      aria-selected={isActive}
      aria-controls={`${id}-panel-${value}`}
      onClick={() => setValue(value)}
      className={cn(
        tone,
        "group relative min-w-[8.5rem] border px-3.5 py-3 outline-none",
        "font-serif text-base tracking-[0.08em] transition-all duration-300",
        isActive
          ? "border-[var(--tone)] bg-[var(--tone-soft)] text-ink shadow-[0_12px_28px_rgba(57,37,18,0.08)]"
          : "border-line bg-surface/70 text-ink-mute hover:border-[var(--tone)] hover:text-ink-soft",
      )}
    >
      <span
        aria-hidden
        key={isActive ? "active" : "idle"}
        className={cn(
          "inline-flex items-center justify-center align-middle mr-2.5",
          "w-5 h-5 border font-serif text-[12px] leading-none tracking-normal",
          "transition-colors duration-300",
          isActive
            ? "border-[var(--tone)] bg-[var(--tone)] text-surface animate-stamp-in"
            : "border-[var(--tone)] text-[var(--tone)] group-hover:bg-[var(--tone-soft)]",
        )}
      >
        {ordinal}
      </span>
      <span>{label}</span>
      <span
        aria-hidden
        className={cn(
          "absolute left-3 right-3 -bottom-[13px] h-0.5 bg-[var(--tone)] origin-left transition-opacity duration-300",
          isActive ? "opacity-100 animate-line-draw-x" : "opacity-0",
        )}
      />
    </button>
  );
}

export function TabsContent({
  value,
  children,
  className,
}: {
  value: string;
  children: React.ReactNode;
  className?: string;
}) {
  const { value: active, id } = useTabsCtx();
  if (active !== value) return null;
  return (
    <div
      role="tabpanel"
      id={`${id}-panel-${value}`}
      aria-labelledby={`${id}-trigger-${value}`}
      className={className}
    >
      {children}
    </div>
  );
}
