"use client";

// PageBridge lets the Agent both READ (snapshots) and OPERATE (actions) the
// page. Panels register a snapshot getter and named action handlers while they
// are mounted; the sidebar collects snapshots and dispatches client tools.

import {
  createContext,
  useContext,
  useEffect,
  useRef,
  type ReactNode,
} from "react";

type SnapshotFn = () => unknown;
type ActionFn = (args: Record<string, unknown>) => unknown | Promise<unknown>;

type BridgeValue = {
  registerSnapshot: (id: string, fn: SnapshotFn) => () => void;
  registerAction: (name: string, fn: ActionFn) => () => void;
  collectSnapshot: () => Record<string, unknown>;
  runClientTool: (name: string, args: Record<string, unknown>) => Promise<unknown>;
};

const BridgeCtx = createContext<BridgeValue | null>(null);

// Which tab each panel-scoped action belongs to (for auto-switching).
const ACTION_TAB: Record<string, string> = {
  set_convert_input: "convert",
  run_convert: "convert",
  set_evolution_search: "evolution",
  select_character: "evolution",
  open_merge_dashboard: "evolution",
  analyze_corpus_coverage: "evolution",
  set_culture_text: "culture",
  run_culture_analysis: "culture",
};

function openTab(tab: string) {
  window.dispatchEvent(new CustomEvent("relumine:open-tab", { detail: tab }));
}

const delay = (ms: number) => new Promise((r) => setTimeout(r, ms));

export function PageBridgeProvider({ children }: { children: ReactNode }) {
  const snapshots = useRef(new Map<string, SnapshotFn>());
  const actions = useRef(new Map<string, ActionFn>());

  const value: BridgeValue = {
    registerSnapshot(id, fn) {
      snapshots.current.set(id, fn);
      return () => {
        snapshots.current.delete(id);
      };
    },
    registerAction(name, fn) {
      actions.current.set(name, fn);
      return () => {
        // Only delete if still pointing at this fn (avoid clobbering a remount).
        if (actions.current.get(name) === fn) actions.current.delete(name);
      };
    },
    collectSnapshot() {
      // Inactive tab panels unmount, so the registered ids reveal the active
      // tab and only expose state the user can actually see.
      const panels: Record<string, unknown> = {};
      for (const [id, fn] of snapshots.current) {
        try {
          panels[id] = fn();
        } catch {
          panels[id] = { error: "snapshot failed" };
        }
      }
      const activeTab = Object.keys(panels)[0] ?? null;
      return { activeTab, panels };
    },
    async runClientTool(name, args) {
      if (name === "switch_tab") {
        const tab = String(args.tab ?? "");
        openTab(tab);
        return { ok: true, tab };
      }
      let fn = actions.current.get(name);
      // If the target panel isn't mounted, switch to its tab and retry.
      if (!fn && ACTION_TAB[name]) {
        openTab(ACTION_TAB[name]);
        for (let i = 0; i < 6 && !fn; i++) {
          await delay(120);
          fn = actions.current.get(name);
        }
      }
      if (!fn) {
        return { error: `当前页面无法执行 ${name}（对应面板未挂载）` };
      }
      try {
        const result = await fn(args);
        return result ?? { ok: true };
      } catch (e) {
        return { error: (e as Error).message };
      }
    },
  };

  return <BridgeCtx.Provider value={value}>{children}</BridgeCtx.Provider>;
}

export function usePageBridge(): BridgeValue {
  const ctx = useContext(BridgeCtx);
  if (!ctx) throw new Error("usePageBridge must be used within PageBridgeProvider");
  return ctx;
}

// Panels call these to expose their state and operations to the Agent.
export function useRegisterSnapshot(id: string, fn: SnapshotFn) {
  const ctx = useContext(BridgeCtx);
  const fnRef = useRef(fn);
  fnRef.current = fn;
  useEffect(() => {
    if (!ctx) return;
    return ctx.registerSnapshot(id, () => fnRef.current());
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ctx, id]);
}

export function useRegisterAction(name: string, fn: ActionFn) {
  const ctx = useContext(BridgeCtx);
  const fnRef = useRef(fn);
  fnRef.current = fn;
  useEffect(() => {
    if (!ctx) return;
    return ctx.registerAction(name, (args) => fnRef.current(args));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ctx, name]);
}
