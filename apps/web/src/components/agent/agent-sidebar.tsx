"use client";

import { AgentChat } from "@/components/agent/agent-chat";
import { useAgentUI } from "@/components/agent/agent-shell";
import { cn } from "@/lib/cn";

// Sidebar width (also consumed by AgentShell for the push padding).
export const AGENT_WIDTH = "360px";

export function AgentSidebar() {
  const { open, setOpen, toggle } = useAgentUI();

  return (
    <>
      {/* edge toggle — always visible, rides the sidebar's left edge */}
      <button
        type="button"
        data-agent-ui
        aria-label={open ? "收起助手" : "展开助手"}
        onClick={toggle}
        className={cn(
          "fixed top-1/2 z-40 -translate-y-1/2 rounded-l-[var(--radius)]",
          "border border-r-0 border-line bg-surface px-2 py-4 shadow-sm",
          "text-[11px] font-sans tracking-[0.2em] text-ink-soft hover:text-accent",
          "[writing-mode:vertical-rl] transition-[right] duration-300 ease-[var(--ease-ink)]",
          "right-0",
          open && "md:right-[var(--agent-w)]",
        )}
        style={{ ["--agent-w" as string]: AGENT_WIDTH }}
      >
        {open ? "收起 ›" : "‹ 助手"}
      </button>

      {/* drawer — fixed, sits in the gutter freed by the shell's padding */}
      <aside
        data-agent-ui
        aria-hidden={!open}
        style={{ ["--agent-w" as string]: AGENT_WIDTH }}
        className={cn(
          "fixed right-0 top-0 z-30 h-screen w-full max-w-[var(--agent-w)]",
          "border-l border-line bg-surface",
          "flex flex-col transition-transform duration-300 ease-[var(--ease-ink)]",
          open ? "translate-x-0" : "translate-x-full",
        )}
      >
        <header className="flex items-center justify-between border-b border-line px-4 h-14 shrink-0">
          <div className="flex items-center gap-2">
            <span className="inline-flex h-5 w-5 items-center justify-center border border-accent bg-accent text-[11px] text-surface">
              智
            </span>
            <span className="font-serif text-sm tracking-[0.12em] text-ink">智能助手</span>
          </div>
          <button
            onClick={() => setOpen(false)}
            aria-label="关闭"
            className="text-ink-mute hover:text-accent text-lg leading-none"
          >
            ×
          </button>
        </header>

        <div className="flex-1 min-h-0">
          <AgentChat />
        </div>
      </aside>
    </>
  );
}
