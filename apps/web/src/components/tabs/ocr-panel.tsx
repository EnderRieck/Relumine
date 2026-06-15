"use client";

import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { Network } from "lucide-react";

import { api, ApiError } from "@/lib/api";
import type { OcrResponse } from "@/lib/types";
import { cn } from "@/lib/cn";

import { SectionMark } from "@/components/chinese/SectionMark";
import { GoldRule } from "@/components/chinese/GoldRule";
import { CornerBrackets } from "@/components/chinese/CornerBrackets";
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

  const previewUrl = useMemo(
    () => (file ? URL.createObjectURL(file) : null),
    [file],
  );

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

  async function runOcr(f: File) {
    setFile(f);
    setResult(null);
    setSimplifiedText(null);
    setMode("trad");
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
      const r = await api.convert(result.text, "t2s");
      setSimplifiedText(r.result);
      setMode("simp");
    } catch (e) {
      const detail = e instanceof ApiError ? e.message : "转简失败";
      toast.error(detail);
    } finally {
      setConverting(false);
    }
  }

  const displayedText = mode === "trad" ? result?.text : simplifiedText ?? result?.text;

  function sendToCulture() {
    if (!displayedText) return;
    localStorage.setItem("relumine:culture-source", displayedText);
    window.dispatchEvent(
      new CustomEvent("relumine:culture-source", { detail: displayedText }),
    );
    window.dispatchEvent(
      new CustomEvent("relumine:open-tab", { detail: "culture" }),
    );
    toast.success("识读文本已送入史脉");
  }

  return (
    <section className="relative rounded-[var(--radius)] border border-line bg-surface p-8 md:p-12 animate-ink-rise">
      <CornerBrackets />
      <SectionMark title="古籍识读" subtitle="本机OCR识读 · 繁简转换" />

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
                  setSimplifiedText(null);
                  setMode("trad");
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
            <div className="flex items-center justify-between mb-3">
              <div className="text-xs font-sans tracking-[0.16em] uppercase text-ink-mute">
                识读 · {mode === "trad" ? "繁體" : "简体"}
              </div>
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
              ) : displayedText ? (
                <div className="font-serif text-base md:text-lg leading-[1.9] tracking-[0.04em] text-ink whitespace-pre-wrap break-words">
                  {displayedText}
                </div>
              ) : null}
            </div>

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
