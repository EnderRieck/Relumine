"use client";

import {
  createContext,
  useContext,
  useEffect,
  useState,
  type CSSProperties,
  type ReactNode,
} from "react";

import { AgentSidebar, AGENT_WIDTH } from "@/components/agent/agent-sidebar";
import { SelectionAsk } from "@/components/agent/selection-ask";
import { cn } from "@/lib/cn";

const STORAGE_KEY = "relumine:agent-open";

type AgentUI = {
  open: boolean;
  setOpen: (v: boolean) => void;
  toggle: () => void;
};

const AgentUICtx = createContext<AgentUI | null>(null);

export function useAgentUI(): AgentUI {
  const ctx = useContext(AgentUICtx);
  if (!ctx) throw new Error("useAgentUI must be used within AgentShell");
  return ctx;
}

/**
 * Class + style for a full-screen (portal) overlay so that, while the sidebar is
 * open, the overlay/backdrop stops at the sidebar's left edge (md+) instead of
 * covering it. Apply to the overlay's outer fixed element.
 */
export function useOverlayGutter(): { className: string; style: CSSProperties } {
  const { open } = useAgentUI();
  return {
    className: open ? "md:right-[var(--agent-w)]" : "",
    style: { ["--agent-w" as string]: AGENT_WIDTH } as CSSProperties,
  };
}

/**
 * Wraps the whole app. When the assistant is open, the shell gains right padding
 * so the header/content/footer reflow into the narrower space (VSCode-style push)
 * while the fixed sidebar occupies the freed gutter.
 */
export function AgentShell({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    setOpen(window.localStorage.getItem(STORAGE_KEY) === "1");
  }, []);

  useEffect(() => {
    if (mounted) window.localStorage.setItem(STORAGE_KEY, open ? "1" : "0");
  }, [open, mounted]);

  const ui: AgentUI = { open, setOpen, toggle: () => setOpen((v) => !v) };

  return (
    <AgentUICtx.Provider value={ui}>
      <div
        className={cn(
          "transition-[padding] duration-300 ease-[var(--ease-ink)]",
          // Push only on md+; on small screens the drawer overlays full-width.
          open && "md:pr-[var(--agent-w)]",
        )}
        style={{ ["--agent-w" as string]: AGENT_WIDTH }}
      >
        {children}
      </div>
      <AgentSidebar />
      <SelectionAsk />
    </AgentUICtx.Provider>
  );
}
