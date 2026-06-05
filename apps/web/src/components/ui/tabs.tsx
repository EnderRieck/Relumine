"use client";

import { createContext, useContext, useId, useState } from "react";
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
        "relative flex items-end gap-10 border-b border-line",
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
  return (
    <button
      type="button"
      role="tab"
      id={`${id}-trigger-${value}`}
      aria-selected={isActive}
      aria-controls={`${id}-panel-${value}`}
      onClick={() => setValue(value)}
      className={cn(
        "group relative -mb-px py-3 px-1 outline-none",
        "font-serif text-base tracking-[0.08em] transition-colors duration-200",
        isActive ? "text-ink" : "text-ink-mute hover:text-ink-soft",
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
            ? "border-accent bg-accent text-surface animate-stamp-in"
            : "border-accent/45 text-accent/75 group-hover:border-accent/80",
        )}
      >
        {ordinal}
      </span>
      <span>{label}</span>
      <span
        aria-hidden
        className={cn(
          "absolute left-0 right-0 -bottom-px h-px bg-accent origin-left transition-opacity duration-300",
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
