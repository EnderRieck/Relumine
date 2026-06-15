"use client";

import { useEffect, useRef, useState } from "react";

import { useAgentUI } from "@/components/agent/agent-shell";
import { cn } from "@/lib/cn";

type Popup = { x: number; y: number; above: boolean; text: string };

const MAX_LEN = 4000;

function inAgentUI(node: Node | null): boolean {
  const el = node instanceof Element ? node : (node?.parentElement ?? null);
  return !!el?.closest("[data-agent-ui]");
}

/**
 * Shows a "问问助手" bubble when the user selects page text. Clicking it opens
 * the assistant and drops the quoted selection into the composer. Selections
 * inside the assistant UI (or inside form fields, which yield no document
 * selection) are ignored.
 */
export function SelectionAsk() {
  const { setOpen } = useAgentUI();
  const [popup, setPopup] = useState<Popup | null>(null);
  const popupRef = useRef<HTMLButtonElement | null>(null);

  useEffect(() => {
    function compute() {
      const sel = window.getSelection();
      if (!sel || sel.isCollapsed || sel.rangeCount === 0) return setPopup(null);
      const text = sel.toString().trim();
      if (!text) return setPopup(null);
      if (inAgentUI(sel.anchorNode) || inAgentUI(sel.focusNode)) return setPopup(null);
      const rect = sel.getRangeAt(0).getBoundingClientRect();
      if (rect.width === 0 && rect.height === 0) return setPopup(null);
      const above = rect.top > 48;
      const x = Math.min(Math.max(rect.left + rect.width / 2, 70), window.innerWidth - 70);
      setPopup({ x, y: above ? rect.top - 8 : rect.bottom + 8, above, text: text.slice(0, MAX_LEN) });
    }

    function onMouseUp(e: MouseEvent) {
      if (popupRef.current?.contains(e.target as Node)) return;
      // let the browser finalize the selection first
      window.setTimeout(compute, 0);
    }
    function onMouseDown(e: MouseEvent) {
      if (popupRef.current?.contains(e.target as Node)) return;
      setPopup(null);
    }
    function onScroll() {
      setPopup(null);
    }

    document.addEventListener("mouseup", onMouseUp);
    document.addEventListener("mousedown", onMouseDown);
    document.addEventListener("scroll", onScroll, true);
    return () => {
      document.removeEventListener("mouseup", onMouseUp);
      document.removeEventListener("mousedown", onMouseDown);
      document.removeEventListener("scroll", onScroll, true);
    };
  }, []);

  if (!popup) return null;

  return (
    <button
      ref={popupRef}
      data-agent-ui
      type="button"
      // keep the text selection alive while clicking
      onMouseDown={(e) => e.preventDefault()}
      onClick={() => {
        setOpen(true);
        window.dispatchEvent(
          new CustomEvent("relumine:agent-ask", { detail: popup.text }),
        );
        setPopup(null);
      }}
      style={{
        position: "fixed",
        top: popup.y,
        left: popup.x,
        transform: popup.above ? "translate(-50%, -100%)" : "translate(-50%, 0)",
        zIndex: 50,
      }}
      className={cn(
        "flex items-center gap-1.5 rounded-[var(--radius)] border border-line bg-surface",
        "px-3 py-1.5 text-xs font-sans text-ink shadow-md whitespace-nowrap",
        "hover:text-accent hover:border-accent/50 transition-colors animate-ink-rise-soft",
      )}
    >
      <span className="inline-flex h-3.5 w-3.5 items-center justify-center bg-accent text-[9px] text-surface">
        智
      </span>
      问问助手
    </button>
  );
}
