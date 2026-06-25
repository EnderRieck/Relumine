"use client";

import { useEffect, useMemo, useState } from "react";
import type { CSSProperties } from "react";
import { toast } from "sonner";
import { Gauge, Network, ScanText } from "lucide-react";

import { api, ApiError } from "@/lib/api";
import type { OcrResponse, ProofreadResult, ProofreadRisk } from "@/lib/types";
import { cn } from "@/lib/cn";
import { useRegisterSnapshot } from "@/lib/agent-bridge";

import { SectionMark } from "@/components/chinese/SectionMark";
import { GoldRule } from "@/components/chinese/GoldRule";
import { CornerBrackets } from "@/components/chinese/CornerBrackets";
import { IconScroll } from "@/components/chinese/BrushIcons";
import { UploadDropzone } from "@/components/shared/upload-dropzone";

type Mode = "trad" | "simp";

export function OcrPanel() {
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<OcrResponse | null>(null);
  const [simplifiedText, setSimplifiedText] = useState<string | null>(null);
  const [mode, setMode] = useState<Mode>("trad");
  const [pending, setPending] = useState(false);
  const [converting, setConverting] = useState(false);
  const [queueDepth, setQueueDepth] = useState<number | null>(null);

  // ----- 上下文校对（风险字框标注 + 候选建议，不改原文）-----
  const [proofing, setProofing] = useState(false);
  const [proof, setProof] = useState<ProofreadResult | null>(null);
  // 专家选定的替换：码点位置 -> 替换字。仅前端本地，不回写后端。
  const [corrections, setCorrections] = useState<Record<number, string>>({});
  // 已处理过的位置（采纳候选或保留原字），用于区分"待复核 / 已定夺"。
  const [decided, setDecided] = useState<Record<number, true>>({});
  const [openPos, setOpenPos] = useState<number | null>(null);
  const [showConfidence, setShowConfidence] = useState(false);

  const previewUrl = useMemo(
    () => (file ? URL.createObjectURL(file) : null),
    [file],
  );

  // 原文按「码点」拆分，与后端 Python 字符下标对齐（古籍含扩展区汉字时按 UTF-16 索引会错位）。
  const codepoints = useMemo(
    () => (result ? Array.from(result.text) : []),
    [result],
  );

  const charConfidences = result?.char_confidences ?? null;
  const hasConfidence =
    !!charConfidences && charConfidences.length === codepoints.length;

  // 采纳替换后的繁体文本（下游繁→简、送入史脉都用它）。
  const effectiveText = useMemo(() => {
    if (!result) return "";
    if (Object.keys(corrections).length === 0) return result.text;
    return codepoints.map((ch, i) => corrections[i] ?? ch).join("");
  }, [result, codepoints, corrections]);

  const risksByPos = useMemo(() => {
    const map = new Map<number, ProofreadRisk>();
    for (const r of proof?.risks ?? []) map.set(r.position, r);
    return map;
  }, [proof]);

  const decidedCount = useMemo(
    () => (proof?.risks ?? []).filter((r) => decided[r.position]).length,
    [proof, decided],
  );

  // ----- Agent bridge: expose OCR panel state (read-only) -----
  useRegisterSnapshot("ocr", () => ({
    fileName: file?.name ?? null,
    mode,
    ocrText: result?.text ?? null,
    proofedText: proof ? effectiveText : null,
    riskCount: proof?.risks.length ?? 0,
    simplifiedText,
    charCount: result?.char_count ?? 0,
    queueDepth,
  }));

  useEffect(
    () => () => {
      if (previewUrl) URL.revokeObjectURL(previewUrl);
    },
    [previewUrl],
  );

  // 等待时每 1s 轮询一次队列深度；显示"前面有 N 位"
  useEffect(() => {
    if (!pending) return;
    let cancelled = false;
    const poll = async () => {
      try {
        const q = await api.ocrQueue();
        if (!cancelled) setQueueDepth(q.depth);
      } catch {
        /* swallow — 网络抖动不打断主流程 */
      }
    };
    poll();
    const iv = setInterval(poll, 1000);
    return () => {
      cancelled = true;
      clearInterval(iv);
    };
  }, [pending]);

  function resetDerived() {
    setSimplifiedText(null);
    setMode("trad");
    setProof(null);
    setCorrections({});
    setDecided({});
    setOpenPos(null);
  }

  async function runOcr(f: File) {
    setFile(f);
    setResult(null);
    resetDerived();
    setQueueDepth(null);
    setPending(true);
    try {
      const res = await api.ocr(f);
      setResult(res);
      toast.success(`识读完成 · ${res.char_count} 字 · ${res.latency_ms}ms`);
    } catch (e) {
      const detail = e instanceof ApiError ? e.message : "识读失败";
      toast.error(detail);
    } finally {
      setPending(false);
      setQueueDepth(null);
    }
  }

  async function convertToSimp() {
    if (!result) return;
    if (simplifiedText) {
      setMode("simp");
      return;
    }
    setConverting(true);
    try {
      const r = await api.convert(effectiveText, "t2s");
      setSimplifiedText(r.result);
      setMode("simp");
    } catch (e) {
      const detail = e instanceof ApiError ? e.message : "转简失败";
      toast.error(detail);
    } finally {
      setConverting(false);
    }
  }

  async function runProofread() {
    if (!result) return;
    setMode("trad"); // 校对在繁体原文上做
    setProofing(true);
    setOpenPos(null);
    try {
      const res = await api.proofread(result.text, {
        char_confidences: result.char_confidences ?? null,
        ocr_candidates: result.alternatives ?? null,
      });
      setProof(res);
      setCorrections({});
      setDecided({});
      if (res.risks.length === 0) {
        toast(res.note ?? "校对完成 · 未发现低置信字");
      } else {
        toast.success(`校对完成 · 按置信度标出 ${res.risks.length} 处待校对字`);
      }
    } catch (e) {
      const detail = e instanceof ApiError ? e.message : "校对失败";
      toast.error(detail);
    } finally {
      setProofing(false);
    }
  }

  function applyCandidate(pos: number, ch: string) {
    setCorrections((prev) => ({ ...prev, [pos]: ch }));
    setDecided((prev) => ({ ...prev, [pos]: true }));
    setSimplifiedText(null); // 原文变了，简体缓存失效
    setOpenPos(null);
  }

  function keepOriginal(pos: number) {
    setCorrections((prev) => {
      if (!(pos in prev)) return prev;
      const next = { ...prev };
      delete next[pos];
      return next;
    });
    setDecided((prev) => ({ ...prev, [pos]: true }));
    setSimplifiedText(null);
    setOpenPos(null);
  }

  const displayedText =
    mode === "trad" ? effectiveText : simplifiedText ?? effectiveText;
  const showAnnotated = !!proof && mode === "trad" && !pending;
  const showHeat =
    !showAnnotated &&
    mode === "trad" &&
    showConfidence &&
    hasConfidence &&
    !pending;

  function sendToCulture() {
    const text = mode === "trad" ? effectiveText : displayedText;
    if (!text) return;
    localStorage.setItem("relumine:culture-source", text);
    window.dispatchEvent(
      new CustomEvent("relumine:culture-source", { detail: text }),
    );
    window.dispatchEvent(
      new CustomEvent("relumine:open-tab", { detail: "culture" }),
    );
    toast.success("识读文本已送入史脉");
  }

  return (
    <section className="tone-ocr chromatic-frame paper-surface relative rounded-[var(--radius)] border border-line p-8 md:p-12 animate-ink-rise">
      <CornerBrackets />
      <SectionMark icon={<IconScroll size={18} />} title="古籍识读" subtitle="本机OCR识读 · 上下文校对 · 繁简转换" />

      {!file ? (
        <div className="mt-8">
          <UploadDropzone onFile={runOcr} />
          <p className="mt-3 text-xs font-sans tracking-wider text-ink-mute">
            提示：推荐清晰的印刷体页面图，单页扫描效果最佳。
          </p>
        </div>
      ) : (
        <div className="mt-8 grid grid-cols-1 md:grid-cols-2 gap-px bg-line">
          <div className="bg-surface p-6 flex flex-col">
            <div className="flex items-center justify-between mb-3">
              <div className="text-xs font-sans tracking-[0.16em] uppercase text-ink-mute">
                原图
              </div>
              <button
                type="button"
                onClick={() => {
                  setFile(null);
                  setResult(null);
                  resetDerived();
                }}
                className="text-xs font-sans tracking-wider uppercase text-ink-mute hover:text-accent transition-colors"
              >
                · 重新选择
              </button>
            </div>
            {previewUrl ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={previewUrl}
                alt="上传的图片"
                className="w-full object-contain border border-line bg-bg"
                style={{ maxHeight: "60vh" }}
              />
            ) : null}
          </div>

          <div className="bg-surface p-6 flex flex-col">
            <div className="flex items-center justify-between mb-3 gap-3">
              <div className="text-xs font-sans tracking-[0.16em] uppercase text-ink-mute">
                识读 · {mode === "trad" ? "繁體" : "简体"}
              </div>
              <div className="flex items-center gap-3">
                {hasConfidence ? (
                  <button
                    type="button"
                    onClick={() => setShowConfidence((v) => !v)}
                    className={cn(
                      "group inline-flex items-center gap-1.5 px-2 py-1 font-serif text-sm transition-colors",
                      showConfidence ? "text-accent" : "text-ink hover:text-accent",
                    )}
                    title="按 OCR 逐字置信度给文本上色，越红表示模型识别时越没把握"
                  >
                    <Gauge className="h-4 w-4" aria-hidden />
                    <span>OCR 置信度</span>
                  </button>
                ) : null}
                <button
                  type="button"
                  onClick={runProofread}
                  disabled={!result || proofing || pending}
                  className={cn(
                    "group inline-flex items-center gap-1.5 px-2 py-1",
                    "font-serif text-sm text-ink hover:text-accent transition-colors",
                    (!result || proofing || pending) &&
                      "opacity-50 cursor-not-allowed",
                  )}
                  title="结合上下文与形近字，标出可疑识读并给候选；不改原文"
                >
                  <ScanText className="h-4 w-4" aria-hidden />
                  <span>{proofing ? "校对中…" : proof ? "重新校对" : "校对"}</span>
                </button>
                <button
                  type="button"
                  onClick={() => (mode === "trad" ? convertToSimp() : setMode("trad"))}
                  disabled={!result || converting}
                  className={cn(
                    "group flex items-center gap-2 px-2 py-1",
                    "font-serif text-sm text-ink hover:text-accent transition-colors",
                    (!result || converting) && "opacity-50 cursor-not-allowed",
                  )}
                >
                  <span>{mode === "trad" ? "轉爲簡體" : "回到繁體"}</span>
                  <GoldRule className="opacity-0 group-hover:opacity-80 transition-opacity duration-300" />
                </button>
              </div>
            </div>

            <div className="relative flex-1 min-h-[12rem]">
              {pending ? (
                <div className="absolute inset-0 flex flex-col items-center justify-center gap-3">
                  <div className="font-serif text-base text-ink-mute">
                    {queueDepth !== null && queueDepth > 1
                      ? `排队中 · 前面有 ${queueDepth - 1} 位`
                      : "识读中…"}
                  </div>
                  <ProgressLine />
                </div>
              ) : showAnnotated ? (
                <AnnotatedText
                  codepoints={codepoints}
                  corrections={corrections}
                  decided={decided}
                  risksByPos={risksByPos}
                  openPos={openPos}
                  onToggle={(pos) => setOpenPos((cur) => (cur === pos ? null : pos))}
                  onApply={applyCandidate}
                  onKeep={keepOriginal}
                />
              ) : showHeat ? (
                <ConfidenceText
                  codepoints={codepoints}
                  confidences={charConfidences ?? []}
                />
              ) : displayedText ? (
                <div className="font-serif text-base md:text-lg leading-[1.9] tracking-[0.04em] text-ink whitespace-pre-wrap break-words">
                  {displayedText}
                </div>
              ) : null}
            </div>

            {proof && !pending ? (
              <ProofSummary
                total={proof.risks.length}
                decided={decidedCount}
                applied={Object.keys(corrections).length}
                note={proof.note ?? null}
              />
            ) : null}

            {result && !pending ? (
              <div className="mt-4 pt-4 border-t border-line flex items-center justify-between gap-4">
                <div className="flex items-center gap-5 text-[10px] font-sans tracking-[0.16em] uppercase text-ink-mute">
                  <span>{result.char_count} chars</span>
                  <span>{result.latency_ms} ms</span>
                </div>
                <button
                  type="button"
                  onClick={sendToCulture}
                  className="inline-flex items-center gap-2 text-xs font-sans text-accent hover:text-ink transition-colors"
                >
                  <Network className="h-4 w-4" aria-hidden />
                  送入史脉
                </button>
              </div>
            ) : null}
          </div>
        </div>
      )}
    </section>
  );
}

// ---- 风险等级配色（按置信度分级；已采纳=绿，已保留=淡灰）----
type MarkTone = { border: string; bg: string; color: string };

function riskTone(confidence: number): MarkTone {
  if (confidence >= 0.75)
    return { border: "#b23a2e", bg: "rgba(178,58,46,0.08)", color: "inherit" };
  if (confidence >= 0.5)
    return { border: "#b8860b", bg: "rgba(184,134,11,0.08)", color: "inherit" };
  return { border: "#9a8f80", bg: "rgba(154,143,128,0.06)", color: "inherit" };
}

function markStyle(
  pos: number,
  confidence: number,
  corrections: Record<number, string>,
  decided: Record<number, true>,
  open: boolean,
): CSSProperties {
  const changed = pos in corrections;
  const isDecided = decided[pos];
  let tone: MarkTone;
  if (changed) {
    tone = { border: "#3f7a52", bg: "rgba(63,122,82,0.10)", color: "#2f5d3f" };
  } else if (isDecided) {
    tone = { border: "#c9c0b2", bg: "transparent", color: "inherit" };
  } else {
    tone = riskTone(confidence);
  }
  return {
    borderBottom: `2px solid ${tone.border}`,
    background: open ? "rgba(178,58,46,0.14)" : tone.bg,
    color: tone.color,
    borderRadius: "2px",
    padding: "0 1px",
    cursor: "pointer",
    boxDecorationBreak: "clone",
    WebkitBoxDecorationBreak: "clone",
  };
}

function AnnotatedText(props: {
  codepoints: string[];
  corrections: Record<number, string>;
  decided: Record<number, true>;
  risksByPos: Map<number, ProofreadRisk>;
  openPos: number | null;
  onToggle: (pos: number) => void;
  onApply: (pos: number, ch: string) => void;
  onKeep: (pos: number) => void;
}) {
  const {
    codepoints,
    corrections,
    decided,
    risksByPos,
    openPos,
    onToggle,
    onApply,
    onKeep,
  } = props;

  return (
    <div className="relative font-serif text-base md:text-lg leading-[2.1] tracking-[0.04em] text-ink whitespace-pre-wrap break-words">
      {openPos !== null ? (
        // 点击空白处关闭弹层
        <div
          className="fixed inset-0 z-10"
          onClick={() => onToggle(openPos)}
          aria-hidden
        />
      ) : null}
      {codepoints.map((ch, i) => {
        const risk = risksByPos.get(i);
        if (!risk) return <span key={i}>{corrections[i] ?? ch}</span>;
        const shown = corrections[i] ?? ch;
        const open = openPos === i;
        return (
          <span key={i} className="relative inline-block">
            <span
              role="button"
              tabIndex={0}
              onClick={() => onToggle(i)}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  onToggle(i);
                }
              }}
              style={markStyle(i, risk.confidence, corrections, decided, open)}
              title={`${risk.category} · 把握 ${(risk.confidence * 100).toFixed(0)}%`}
            >
              {shown}
            </span>
            {open ? (
              <RiskPopover
                risk={risk}
                changedTo={corrections[i] ?? null}
                onApply={(c) => onApply(i, c)}
                onKeep={() => onKeep(i)}
              />
            ) : null}
          </span>
        );
      })}
    </div>
  );
}

function ConfidenceText(props: { codepoints: string[]; confidences: number[] }) {
  const { codepoints, confidences } = props;
  return (
    <div>
      <div className="mb-2 text-[10px] font-sans tracking-[0.12em] uppercase text-ink-mute">
        OCR 置信度热度 · 越红表示模型识别时越没把握（仅提示，不改字）
      </div>
      <div className="font-serif text-base md:text-lg leading-[2.1] tracking-[0.04em] text-ink whitespace-pre-wrap break-words">
        {codepoints.map((ch, i) => {
          const c = confidences[i];
          if (c == null || c >= 0.92) return <span key={i}>{ch}</span>;
          const intensity = Math.min(1, (0.92 - c) / 0.6);
          return (
            <span
              key={i}
              title={`OCR 把握 ${(c * 100).toFixed(0)}%`}
              style={{
                borderBottom: `2px solid rgba(178,58,46,${(0.25 + 0.55 * intensity).toFixed(2)})`,
                background: `rgba(178,58,46,${(0.04 + 0.1 * intensity).toFixed(2)})`,
                borderRadius: "2px",
                padding: "0 1px",
              }}
            >
              {ch}
            </span>
          );
        })}
      </div>
    </div>
  );
}

const CATEGORY_LABEL: Record<string, string> = {
  形近: "形近误识",
  文义: "文义不合",
  缺漏: "疑有缺字",
  衍文: "疑为衍文",
  低置信: "OCR 低置信",
  其他: "存疑",
};

const SOURCE_TAG: Record<string, { label: string; title: string }> = {
  confusable: { label: "形", title: "部件形近字" },
  ocr: { label: "OCR", title: "OCR 模型次优读法" },
  context: { label: "", title: "上下文建议" },
};

function RiskPopover(props: {
  risk: ProofreadRisk;
  changedTo: string | null;
  onApply: (ch: string) => void;
  onKeep: () => void;
}) {
  const { risk, changedTo, onApply, onKeep } = props;
  return (
    <div
      className="absolute left-1/2 top-full z-20 mt-1.5 w-64 -translate-x-1/2 rounded-[var(--radius)] border border-line bg-surface p-3 text-left shadow-lg"
      onClick={(e) => e.stopPropagation()}
    >
      <div className="flex items-center justify-between gap-2 mb-2">
        <span className="text-[11px] font-sans tracking-[0.12em] uppercase text-accent">
          {CATEGORY_LABEL[risk.category] ?? risk.category}
        </span>
        <span className="text-[10px] font-sans text-ink-mute">
          {risk.category === "低置信" ? "可疑度" : "把握"}{" "}
          {(risk.confidence * 100).toFixed(0)}%
        </span>
      </div>

      <div className="mb-2 flex items-baseline justify-between gap-2 font-serif text-sm text-ink-mute">
        <span>
          原字{" "}
          <span className="text-ink font-medium" style={{ fontSize: "1.05em" }}>
            {risk.original}
          </span>
        </span>
        {risk.ocr_confidence != null ? (
          <span className="text-[10px] font-sans text-ink-mute">
            OCR 把握 {(risk.ocr_confidence * 100).toFixed(0)}%
          </span>
        ) : null}
      </div>

      {risk.reason ? (
        <p className="mb-2.5 text-xs font-sans leading-relaxed text-ink-mute">
          {risk.reason}
        </p>
      ) : null}

      <div className="text-[10px] font-sans tracking-[0.12em] uppercase text-ink-mute mb-1.5">
        候选字
      </div>
      {risk.candidates.length === 0 ? (
        <p className="text-xs font-sans text-ink-mute">
          无明确候选，请对照原图核对。
        </p>
      ) : (
        <div className="flex flex-wrap gap-1.5">
          {risk.candidates.map((c) => {
            const active = changedTo === c.char;
            const tag = SOURCE_TAG[c.source] ?? SOURCE_TAG.context;
            return (
              <button
                key={c.char}
                type="button"
                onClick={() => onApply(c.char)}
                className={cn(
                  "inline-flex items-center gap-1 rounded border px-2 py-1 font-serif text-base transition-colors",
                  active
                    ? "border-accent bg-accent/10 text-accent"
                    : "border-line text-ink hover:border-accent hover:text-accent",
                )}
                title={tag.title}
              >
                <span>{c.char}</span>
                {tag.label ? (
                  <span className="text-[9px] text-ink-mute">{tag.label}</span>
                ) : null}
              </button>
            );
          })}
        </div>
      )}

      <div className="mt-2.5 flex items-center justify-between border-t border-line pt-2">
        <button
          type="button"
          onClick={onKeep}
          className="text-xs font-sans text-ink-mute hover:text-ink transition-colors"
        >
          保留原字「{risk.original}」
        </button>
        {changedTo ? (
          <span className="text-[10px] font-sans text-[#3f7a52]">已采纳 {changedTo}</span>
        ) : null}
      </div>
    </div>
  );
}

function ProofSummary(props: {
  total: number;
  decided: number;
  applied: number;
  note: string | null;
}) {
  const { total, decided, applied, note } = props;
  if (total === 0) {
    return (
      <div className="mt-3 text-xs font-sans text-ink-mute">
        {note ?? "校对完成 · 未发现低置信字"}
      </div>
    );
  }
  return (
    <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs font-sans text-ink-mute">
      <span>
        待校对 <span className="text-ink font-medium">{total}</span> 处
      </span>
      <span>
        已复核 <span className="text-ink font-medium">{decided}</span>/{total}
      </span>
      {applied > 0 ? (
        <span style={{ color: "#3f7a52" }}>已采纳 {applied} 处替换</span>
      ) : null}
      <span className="text-ink-mute/70">按 OCR 置信度选字 · 点高亮字看候选 · 仅建议不自动改</span>
    </div>
  );
}

function ProgressLine() {
  return (
    <div className="relative h-px w-40 overflow-hidden bg-line">
      <div
        className="absolute inset-y-0 left-0 w-1/3 bg-accent"
        style={{
          animation: "ocr-sweep 1.4s ease-in-out infinite",
        }}
      />
      <style jsx>{`
        @keyframes ocr-sweep {
          0%   { transform: translateX(-100%); }
          50%  { transform: translateX(180%); }
          100% { transform: translateX(380%); }
        }
      `}</style>
    </div>
  );
}
