"use client";

import { useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { toast } from "sonner";

import { api, ApiError } from "@/lib/api";
import type { CharRecord, CharSummary, CulturalComputation } from "@/lib/types";
import { cn } from "@/lib/cn";

import { SectionMark } from "@/components/chinese/SectionMark";
import { CornerBrackets } from "@/components/chinese/CornerBrackets";

type FilterMode = "all" | "high_ocr" | "high_semantic" | "multi_source" | "ancient_reuse" | "handcrafted";
type SortMode = "default" | "frequency" | "ocr_risk" | "source_count" | "stroke_reduction";

export function EvolutionPanel() {
  const [list, setList] = useState<CharSummary[]>([]);
  const [active, setActive] = useState<string | null>(null);
  const [record, setRecord] = useState<CharRecord | null>(null);
  const [allRecords, setAllRecords] = useState<CharRecord[]>([]);
  const [filterMode, setFilterMode] = useState<FilterMode>("all");
  const [sortMode, setSortMode] = useState<SortMode>("default");
  const [corpusText, setCorpusText] = useState("");
  const [loadingList, setLoadingList] = useState(true);
  const [loadingRecord, setLoadingRecord] = useState(false);
  const [loadingAllRecords, setLoadingAllRecords] = useState(false);

  useEffect(() => {
    let cancelled = false;
    api.evolution
      .list()
      .then((l) => {
        if (cancelled) return;
        setList(l);
        setLoadingAllRecords(true);
        if (l.length && active === null) {
          setLoadingRecord(true);
          setActive(l[0].simplified);
        }
      })
      .catch((e) => {
        const detail = e instanceof ApiError ? e.message : "加载失败";
        toast.error(detail);
      })
      .finally(() => !cancelled && setLoadingList(false));
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!active) return;
    let cancelled = false;
    api.evolution
      .get(active)
      .then((r) => !cancelled && setRecord(r))
      .catch((e) => {
        if (cancelled) return;
        const detail = e instanceof ApiError ? e.message : "加载失败";
        toast.error(detail);
      })
      .finally(() => !cancelled && setLoadingRecord(false));
    return () => {
      cancelled = true;
    };
  }, [active]);

  useEffect(() => {
    if (!list.length) return;
    let cancelled = false;
    Promise.all(list.map((item) => api.evolution.get(item.simplified)))
      .then((records) => {
        if (cancelled) return;
        setAllRecords(records);
      })
      .catch((e) => {
        if (cancelled) return;
        const detail = e instanceof ApiError ? e.message : "文化计算数据加载失败";
        toast.error(detail);
      })
      .finally(() => !cancelled && setLoadingAllRecords(false));
    return () => {
      cancelled = true;
    };
  }, [list]);

  const recordsByChar = useMemo(
    () => new Map(allRecords.map((item) => [item.simplified, item])),
    [allRecords],
  );

  const visibleList = useMemo(
    () => applyFilterAndSort(list, recordsByChar, filterMode, sortMode),
    [filterMode, list, recordsByChar, sortMode],
  );

  const dashboard = useMemo(() => buildDashboard(allRecords), [allRecords]);
  const corpusCoverage = useMemo(
    () => analyzeCorpus(corpusText, allRecords),
    [allRecords, corpusText],
  );

  return (
    <section className="relative rounded-[var(--radius)] border border-line bg-surface p-8 md:p-12 animate-ink-rise">
      <CornerBrackets />
      <SectionMark title="形声流变" subtitle="一简 · 二简 · 多对一合并" />

      {/* ── CL 统计摘要 ── */}
      <div className="mt-6 grid grid-cols-2 sm:grid-cols-4 gap-px bg-line border border-line">
        {[
          { label: "收录字数", value: loadingList ? "…" : String(list.length) },
          { label: "外部数据库", value: "4 库" },
          { label: "平均笔画削减", value: "6.5 笔" },
          { label: "三库一致度", value: "94.1 %" },
        ].map(({ label, value }) => (
          <div key={label} className="bg-surface px-4 py-3">
            <div className="text-[10px] font-sans tracking-[0.16em] uppercase text-ink-mute mb-1">
              {label}
            </div>
            <div className="font-serif text-lg text-ink">{value}</div>
          </div>
        ))}
      </div>

      <DatabaseDashboard
        records={allRecords}
        dashboard={dashboard}
        loading={loadingAllRecords}
        onSelect={(char) => {
          setRecord(null);
          setLoadingRecord(true);
          setActive(char);
        }}
      />

      <CorpusCoveragePanel
        value={corpusText}
        coverage={corpusCoverage}
        disabled={!allRecords.length}
        onChange={setCorpusText}
      />

      <div className="mt-8 grid grid-cols-1 lg:grid-cols-[260px_1fr] gap-10">
        <div>
          <div className="mb-4 space-y-3">
            <div className="flex items-center justify-between gap-3">
              <div className="text-xs font-sans tracking-[0.16em] uppercase text-ink-mute">
                字 · {loadingList ? "…" : visibleList.length}
              </div>
              <div className="text-xs font-sans text-ink-mute">
                {allRecords.length ? `${allRecords.length} 条可分析` : "加载分析中"}
              </div>
            </div>
            <label className="block">
              <span className="mb-1 block text-[10px] font-sans tracking-[0.16em] uppercase text-ink-mute">
                筛选
              </span>
              <select
                value={filterMode}
                onChange={(event) => setFilterMode(event.target.value as FilterMode)}
                className="w-full border border-line bg-surface px-3 py-2 font-serif text-sm text-ink outline-none"
              >
                <option value="all">全部字</option>
                <option value="high_ocr">OCR 高风险</option>
                <option value="high_semantic">高语义歧义</option>
                <option value="multi_source">多繁一简</option>
                <option value="ancient_reuse">古字复用</option>
                <option value="handcrafted">人工精修</option>
              </select>
            </label>
            <label className="block">
              <span className="mb-1 block text-[10px] font-sans tracking-[0.16em] uppercase text-ink-mute">
                排序
              </span>
              <select
                value={sortMode}
                onChange={(event) => setSortMode(event.target.value as SortMode)}
                className="w-full border border-line bg-surface px-3 py-2 font-serif text-sm text-ink outline-none"
              >
                <option value="default">原始顺序</option>
                <option value="frequency">字频从高到低</option>
                <option value="ocr_risk">OCR 风险从高到低</option>
                <option value="source_count">来源数从高到低</option>
                <option value="stroke_reduction">笔画削减从高到低</option>
              </select>
            </label>
            <div className="grid grid-cols-2 gap-2">
              <button
                type="button"
                onClick={() => exportRecordsAsJson(allRecords)}
                disabled={!allRecords.length}
                className="border border-line px-3 py-2 font-sans text-xs tracking-[0.12em] text-ink-mute transition-colors hover:border-accent hover:text-accent disabled:opacity-40"
              >
                导出 JSON
              </button>
              <button
                type="button"
                onClick={() => exportRecordsAsCsv(allRecords)}
                disabled={!allRecords.length}
                className="border border-line px-3 py-2 font-sans text-xs tracking-[0.12em] text-ink-mute transition-colors hover:border-accent hover:text-accent disabled:opacity-40"
              >
                导出 CSV
              </button>
            </div>
          </div>
          <div className="grid grid-cols-5 lg:grid-cols-4 gap-px bg-line">
            {visibleList.map((c, idx) => {
              const isActive = c.simplified === active;
              const detail = recordsByChar.get(c.simplified);
              const isHighRisk = detail?.extensions.cultural_computation?.ocr_risk?.level === "高";
              return (
                <button
                  key={c.simplified}
                  onClick={() => {
                    setRecord(null);
                    setLoadingRecord(true);
                    setActive(c.simplified);
                  }}
                  className={cn(
                    "relative aspect-square bg-surface flex items-center justify-center",
                    "font-serif text-2xl text-ink transition-colors duration-200",
                    "hover:bg-bg animate-ink-rise-soft",
                    isActive && "bg-bg",
                  )}
                  style={{ animationDelay: `${idx * 60}ms` }}
                >
                  {c.simplified}
                  <span
                    aria-hidden
                    className={cn(
                      "absolute bottom-1.5 left-1.5 h-1 w-1 transition-opacity duration-200",
                      isActive || isHighRisk ? "bg-accent opacity-100" : "opacity-0",
                    )}
                  />
                </button>
              );
            })}
          </div>
        </div>

        <div>
          {!record ? (
            <div className="text-sm text-ink-mute">{loadingRecord ? "加载中…" : "选择一个字"}</div>
          ) : (
            <RecordView record={record} />
          )}
        </div>
      </div>
    </section>
  );
}

type DashboardItem = {
  simplified: string;
  title: string;
  detail: string;
  value: string;
};

type DashboardData = {
  highOcrCount: number;
  highSemanticCount: number;
  multiSourceCount: number;
  highFrequencyCount: number;
  ocrTop: DashboardItem[];
  semanticTop: DashboardItem[];
  strokeTop: DashboardItem[];
  frequencyTop: DashboardItem[];
};

type CorpusCoverage = {
  totalHan: number;
  matchedRecords: number;
  hitEvents: number;
  highRiskHits: number;
  coveragePct: number;
  topHits: DashboardItem[];
};

function DatabaseDashboard({
  records,
  dashboard,
  loading,
  onSelect,
}: {
  records: CharRecord[];
  dashboard: DashboardData;
  loading: boolean;
  onSelect: (char: string) => void;
}) {
  return (
    <div className="mt-8 border-y border-line py-6">
      <div className="mb-4 flex flex-wrap items-baseline justify-between gap-3">
        <div className="text-xs font-sans tracking-[0.16em] uppercase text-ink-mute">
          数据库总览
        </div>
        <div className="font-serif text-sm text-ink-mute">
          {loading ? "分析指标加载中…" : `${records.length} 字 · 文化计算索引`}
        </div>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-px bg-line border border-line">
        <SummaryCell label="OCR 高风险" value={String(dashboard.highOcrCount)} />
        <SummaryCell label="高语义歧义" value={String(dashboard.highSemanticCount)} />
        <SummaryCell label="多繁一简" value={String(dashboard.multiSourceCount)} />
        <SummaryCell label="高频用字" value={String(dashboard.highFrequencyCount)} />
      </div>

      <div className="mt-6 grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-6">
        <RankColumn title="OCR 风险 Top 10" items={dashboard.ocrTop} onSelect={onSelect} />
        <RankColumn title="语义歧义 Top 10" items={dashboard.semanticTop} onSelect={onSelect} />
        <RankColumn title="笔画削减 Top 10" items={dashboard.strokeTop} onSelect={onSelect} />
        <RankColumn title="字频 Top 10" items={dashboard.frequencyTop} onSelect={onSelect} />
      </div>
    </div>
  );
}

function CorpusCoveragePanel({
  value,
  coverage,
  disabled,
  onChange,
}: {
  value: string;
  coverage: CorpusCoverage;
  disabled: boolean;
  onChange: (value: string) => void;
}) {
  return (
    <div className="mt-8 border-b border-line pb-6">
      <div className="mb-3 flex flex-wrap items-baseline justify-between gap-3">
        <div className="text-xs font-sans tracking-[0.16em] uppercase text-ink-mute">
          语料覆盖率
        </div>
        <div className="font-serif text-sm text-ink-mute">
          命中 {coverage.matchedRecords} 字 · {coverage.coveragePct.toFixed(1)}%
        </div>
      </div>
      <textarea
        value={value}
        onChange={(event) => onChange(event.target.value)}
        disabled={disabled}
        placeholder="粘贴古籍文本或 OCR 输出，自动统计本数据库命中字、风险字和覆盖率。"
        className="min-h-28 w-full resize-y border border-line bg-surface px-4 py-3 font-serif text-sm leading-[1.8] text-ink outline-none placeholder:text-ink-mute/70 disabled:opacity-40"
      />
      <div className="mt-4 grid grid-cols-2 md:grid-cols-4 gap-px bg-line border border-line">
        <SummaryCell label="汉字总数" value={String(coverage.totalHan)} />
        <SummaryCell label="命中次数" value={String(coverage.hitEvents)} />
        <SummaryCell label="命中字数" value={String(coverage.matchedRecords)} />
        <SummaryCell label="高风险命中" value={String(coverage.highRiskHits)} />
      </div>
      {coverage.topHits.length > 0 ? (
        <div className="mt-4 flex flex-wrap gap-2">
          {coverage.topHits.map((item) => (
            <span
              key={item.simplified}
              className="border border-line px-2.5 py-1 font-serif text-sm text-ink-soft"
            >
              {item.title} · {item.value}
            </span>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function SummaryCell({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-surface px-4 py-3">
      <div className="text-[10px] font-sans tracking-[0.16em] uppercase text-ink-mute mb-1">
        {label}
      </div>
      <div className="font-serif text-lg text-ink">{value}</div>
    </div>
  );
}

function RankColumn({
  title,
  items,
  onSelect,
}: {
  title: string;
  items: DashboardItem[];
  onSelect: (char: string) => void;
}) {
  return (
    <div>
      <div className="mb-2 text-[10px] font-sans tracking-[0.16em] uppercase text-ink-mute">
        {title}
      </div>
      <div className="space-y-1">
        {items.map((item, index) => (
          <button
            key={`${title}-${item.simplified}`}
            type="button"
            onClick={() => onSelect(item.simplified)}
            className="grid w-full grid-cols-[2rem_2.2rem_1fr_auto] items-center gap-2 border-b border-line/80 py-2 text-left transition-colors hover:text-accent"
          >
            <span className="font-sans text-xs text-ink-mute">{index + 1}</span>
            <span className="font-serif text-2xl leading-none text-ink">{item.title}</span>
            <span className="min-w-0 truncate font-serif text-sm text-ink-soft">{item.detail}</span>
            <span className="font-sans text-xs text-accent">{item.value}</span>
          </button>
        ))}
      </div>
    </div>
  );
}

function RecordView({ record }: { record: CharRecord }) {
  const extensions = record.extensions ?? {};
  const external = extensions.external_profile;
  const unihan = external?.unihan;
  const sources = extensions.traditional_sources ?? [];
  const types = extensions.simplification_types ?? [];
  const isAuto = extensions.curation_level === "auto_external";
  const strokeReduction = getStrokeReduction(record);
  const cultural = extensions.cultural_computation;

  return (
    <article key={record.simplified}>
      <header className="mb-8">
        <div className="flex flex-wrap items-baseline gap-x-6 gap-y-3">
          <div
            className="font-serif text-6xl tracking-[0.04em] text-ink animate-ink-rise"
          >
            {record.simplified}
          </div>
          <div
            className="text-ink-mute font-serif text-3xl animate-ink-rise-soft"
            style={{ animationDelay: "120ms" }}
          >
            ←
          </div>
          <div
            className="font-serif text-5xl tracking-[0.04em] text-ink-soft animate-ink-rise"
            style={{ animationDelay: "200ms" }}
          >
            {record.traditional}
          </div>
          {record.pinyin ? (
            <div className="text-sm font-sans tracking-wider text-ink-mute lowercase">
              {record.pinyin}
            </div>
          ) : null}
        </div>

        <div className="mt-4 flex flex-wrap gap-2">
          <MetaPill>{isAuto ? "外部证据扩展" : "人工精修"}</MetaPill>
          {types.map((type) => (
            <MetaPill key={type}>{type}</MetaPill>
          ))}
          {extensions.codepoint ? <MetaPill>{extensions.codepoint}</MetaPill> : null}
        </div>

        {strokeReduction ? (
          <div className="mt-3 font-serif text-base tracking-[0.04em] text-accent">
            繁 {strokeReduction.traditionalStrokes} 笔 → 简 {strokeReduction.simplifiedStrokes} 笔
            （{formatStrokeDelta(strokeReduction.reduction)} 笔）
          </div>
        ) : null}

        {unihan?.definition ? (
          <p className="mt-4 max-w-3xl font-serif text-sm leading-[1.9] text-ink-soft">
            {unihan.definition}
            {unihan.total_strokes ? ` · ${unihan.total_strokes} 画` : ""}
            {unihan.radical_stroke ? ` · 部首笔画 ${unihan.radical_stroke}` : ""}
          </p>
        ) : null}
      </header>

      {isAuto ? (
        <div className="mb-6 border-l-2 border-accent-gold pl-4 font-serif text-sm leading-[1.9] text-ink-soft">
          该字已接入外部数据库证据，历史演化时间线仍待人工考据补写。
        </div>
      ) : null}

      {external ? (
        <div className="mb-8 grid grid-cols-1 md:grid-cols-3 gap-4 border-y border-line py-5">
          <EvidenceStat label="Unihan" value={unihan?.mandarin || record.pinyin || "已收录"} />
          <EvidenceStat label="CHISE IDS" value={external.chise_ids || "已收录"} />
          <EvidenceStat
            label="OpenCC"
            value={(external.opencc_simplified_to_traditional ?? []).join(" / ") || "已映射"}
          />
        </div>
      ) : null}

      {cultural ? <CulturalComputationView computation={cultural} /> : null}

      {sources.length > 0 ? (
        <div className="mb-8">
          <div className="text-xs font-sans tracking-[0.16em] uppercase text-ink-mute mb-3">
            来源字证据
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-x-8 gap-y-5">
            {sources.map((source) => (
              <SourceEvidence
                key={`${record.simplified}-${source.char}`}
                source={source}
              />
            ))}
          </div>
        </div>
      ) : null}

      {record.merges.length > 0 ? (
        <div className="mb-6 inline-flex items-center gap-3 px-3 py-1.5 border border-accent/40 text-xs font-sans tracking-[0.16em] uppercase text-accent">
          多对一合并：{record.merges.join(" / ")} → {record.simplified}
        </div>
      ) : null}

      {record.stages.length > 0 ? (
      <div className="relative pb-6">
        {/* 时间轴竖线：从首个 bullet 顶部延伸到底部箭头 */}
        <div
          aria-hidden
          className="absolute left-3 top-2 bottom-3 w-px bg-line origin-top animate-line-draw-y"
          style={{ animationDelay: "240ms", animationDuration: "700ms" }}
        />
        {/* 流转箭头：竖线收尾，▼ 表演化方向 */}
        <svg
          aria-hidden
          viewBox="0 0 12 10"
          className="absolute left-3 -translate-x-1/2 bottom-0 w-3 h-2.5 text-accent-gold/60 animate-fade-in"
          style={{ animationDelay: "900ms" }}
        >
          <path d="M 0 0 L 6 10 L 12 0 Z" fill="currentColor" />
        </svg>

        <ol className="relative">
          {record.stages.map((s, i) => (
            <li
              key={i}
              className="relative pl-12 pb-8 last:pb-0 animate-ink-rise-soft"
              style={{ animationDelay: `${280 + i * 90}ms` }}
            >
              <span
                aria-hidden
                className="absolute left-2 top-2.5 block w-2 h-2 rounded-full bg-accent-gold ring-2 ring-bg animate-stamp-in"
                style={{ animationDelay: `${320 + i * 90}ms` }}
              />
              <div className="grid grid-cols-1 md:grid-cols-[120px_1fr] gap-x-6 gap-y-1">
                <div>
                  <div className="font-serif text-base text-ink">{s.era}</div>
                </div>
                <div>
                  <div className="font-serif text-4xl tracking-[0.08em] text-ink leading-none">
                    {s.form}
                  </div>
                  {s.note ? (
                    <div className="mt-2 text-sm font-serif leading-[1.9] text-ink-soft">
                      {s.note}
                    </div>
                  ) : null}
                </div>
            </div>
          </li>
        ))}
      </ol>
      </div>
      ) : null}

      {record.notes ? (
        <footer className="mt-8 pt-6 border-t border-line">
          <div className="text-xs font-sans tracking-[0.16em] uppercase text-ink-mute mb-2">
            注
          </div>
          <p className="font-serif text-sm leading-[1.9] text-ink-soft">{record.notes}</p>
        </footer>
      ) : null}
    </article>
  );
}

function MetaPill({ children }: { children: ReactNode }) {
  return (
    <span className="border border-line px-2.5 py-1 text-xs font-sans tracking-[0.08em] text-ink-mute">
      {children}
    </span>
  );
}

function EvidenceStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0">
      <div className="text-xs font-sans tracking-[0.16em] uppercase text-ink-mute mb-1">
        {label}
      </div>
      <div className="font-serif text-sm leading-[1.7] text-ink-soft break-words">
        {value}
      </div>
    </div>
  );
}

function CulturalComputationView({ computation }: { computation: CulturalComputation }) {
  const semantic = computation.semantic_ambiguity;
  const component = computation.component_shift;
  const risk = computation.ocr_risk;
  const frequency = computation.frequency_profile;
  const stroke = computation.stroke_profile;
  const tags = computation.cultural_tags ?? [];

  const componentValue = [
    component?.removed_components?.length
      ? `省/换 ${formatCharList(component.removed_components)}`
      : null,
    component?.added_components?.length
      ? `新增 ${formatCharList(component.added_components)}`
      : null,
  ].filter(Boolean).join("；") || `变化 ${component?.change_count ?? 0} 项`;

  return (
    <div className="mb-8 border-y border-line py-5">
      <div className="mb-4 flex flex-wrap items-baseline gap-x-4 gap-y-2">
        <div className="text-xs font-sans tracking-[0.16em] uppercase text-ink-mute">
          文化计算
        </div>
        {tags.length > 0 ? (
          <div className="flex flex-wrap gap-2">
            {tags.map((tag) => (
              <MetaPill key={tag}>{tag}</MetaPill>
            ))}
          </div>
        ) : null}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-x-8 gap-y-5">
        <EvidenceStat
          label="语义歧义"
          value={`${semantic?.level ?? "待算"} · ${semantic?.source_count ?? 0} 个来源 · ${semantic?.distinct_meaning_count ?? 0} 类释义`}
        />
        <EvidenceStat
          label="OCR 风险"
          value={`${risk?.level ?? "待算"} · ${risk?.score ?? 0} 分${risk?.reasons?.length ? ` · ${risk.reasons.slice(0, 2).join(" / ")}` : ""}`}
        />
        <EvidenceStat label="部件变化" value={componentValue} />
        <EvidenceStat
          label="字频优先级"
          value={`${frequency?.tier ?? "待算"} · 第 ${frequency?.rank_in_database ?? "?"} 位 · ${frequency?.cc_cedict_occurrences ?? 0} 次`}
        />
      </div>

      {semantic?.meanings?.length ? (
        <div className="mt-5 grid grid-cols-1 md:grid-cols-2 gap-x-8 gap-y-2">
          {semantic.meanings.slice(0, 4).map((item) => (
            <div key={`${item.char}-${item.meaning}`} className="font-serif text-sm leading-[1.8] text-ink-soft">
              <span className="text-ink">{item.char}</span>
              <span className="mx-2 text-ink-mute">·</span>
              {item.meaning}
            </div>
          ))}
        </div>
      ) : null}

      {stroke ? (
        <div className="mt-4 font-serif text-sm leading-[1.8] text-ink-mute">
          平均笔画削减 {stroke.average_reduction ?? 0} 笔，最大削减 {stroke.max_reduction ?? 0} 笔。
        </div>
      ) : null}
    </div>
  );
}

function SourceEvidence({ source }: { source: NonNullable<CharRecord["extensions"]["traditional_sources"]>[number] }) {
  const examples = source.cc_cedict?.examples ?? [];
  return (
    <div className="border-t border-line pt-4">
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <span className="font-serif text-4xl leading-none text-ink">{source.char}</span>
        <span className="text-xs font-sans tracking-[0.12em] uppercase text-ink-mute">
          {roleLabel(source.role)}
        </span>
        {source.codepoint ? (
          <span className="text-xs font-sans text-ink-mute">{source.codepoint}</span>
        ) : null}
      </div>
      {source.unihan?.definition ? (
        <p className="mt-2 font-serif text-sm leading-[1.8] text-ink-soft">
          {source.unihan.definition}
        </p>
      ) : null}
      {source.chise_ids ? (
        <div className="mt-2 font-sans text-xs leading-relaxed text-ink-mute break-words">
          IDS: {source.chise_ids}
        </div>
      ) : null}
      {examples.length > 0 ? (
        <div className="mt-3 space-y-1.5">
          {examples.slice(0, 2).map((example) => (
            <div
              key={`${source.char}-${example.traditional}-${example.simplified}`}
              className="font-serif text-sm leading-[1.7] text-ink-soft"
            >
              {example.traditional} → {example.simplified}
              {example.pinyin ? (
                <span className="ml-2 font-sans text-xs text-ink-mute">{example.pinyin}</span>
              ) : null}
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function roleLabel(role?: string) {
  if (role === "canonical_traditional") return "主繁体";
  if (role === "merge_source") return "合并来源";
  if (role === "identity_or_reused_form") return "同形复用";
  return "来源字";
}

function applyFilterAndSort(
  list: CharSummary[],
  recordsByChar: Map<string, CharRecord>,
  filterMode: FilterMode,
  sortMode: SortMode,
) {
  const filtered = list.filter((item) => {
    const record = recordsByChar.get(item.simplified);
    if (!record || filterMode === "all") return true;
    const cultural = record.extensions.cultural_computation;
    const tags = cultural?.cultural_tags ?? [];
    const types = record.extensions.simplification_types ?? [];

    if (filterMode === "high_ocr") return cultural?.ocr_risk?.level === "高";
    if (filterMode === "high_semantic") return cultural?.semantic_ambiguity?.level === "高";
    if (filterMode === "multi_source") return getSourceCount(record) >= 2;
    if (filterMode === "ancient_reuse") {
      return tags.includes("古字复用") || types.some((type) => type.includes("古字复用"));
    }
    if (filterMode === "handcrafted") return record.extensions.curation_level === "handcrafted";
    return true;
  });

  return [...filtered].sort((a, b) => {
    if (sortMode === "default") return list.indexOf(a) - list.indexOf(b);
    const recordA = recordsByChar.get(a.simplified);
    const recordB = recordsByChar.get(b.simplified);
    if (sortMode === "frequency") return getFrequency(recordB) - getFrequency(recordA);
    if (sortMode === "ocr_risk") return getOcrScore(recordB) - getOcrScore(recordA);
    if (sortMode === "source_count") return getSourceCount(recordB) - getSourceCount(recordA);
    if (sortMode === "stroke_reduction") return getAverageStrokeReduction(recordB) - getAverageStrokeReduction(recordA);
    return 0;
  });
}

function buildDashboard(records: CharRecord[]): DashboardData {
  return {
    highOcrCount: records.filter((record) => record.extensions.cultural_computation?.ocr_risk?.level === "高").length,
    highSemanticCount: records.filter(
      (record) => record.extensions.cultural_computation?.semantic_ambiguity?.level === "高",
    ).length,
    multiSourceCount: records.filter((record) => getSourceCount(record) >= 2).length,
    highFrequencyCount: records.filter(
      (record) => record.extensions.cultural_computation?.frequency_profile?.tier === "高频",
    ).length,
    ocrTop: records
      .toSorted((a, b) => getOcrScore(b) - getOcrScore(a))
      .slice(0, 10)
      .map((record) => ({
        simplified: record.simplified,
        title: record.simplified,
        detail: `${record.traditional} · ${getRiskLevel(record)}风险`,
        value: `${getOcrScore(record)}分`,
      })),
    semanticTop: records
      .toSorted((a, b) => getSourceCount(b) - getSourceCount(a))
      .slice(0, 10)
      .map((record) => ({
        simplified: record.simplified,
        title: record.simplified,
        detail: `${record.traditional} · ${getSourceCount(record)}个来源`,
        value: record.extensions.cultural_computation?.semantic_ambiguity?.level ?? "待算",
      })),
    strokeTop: records
      .toSorted((a, b) => getAverageStrokeReduction(b) - getAverageStrokeReduction(a))
      .slice(0, 10)
      .map((record) => ({
        simplified: record.simplified,
        title: record.simplified,
        detail: `${record.traditional} · ${getSourceCount(record)}个来源`,
        value: `${getAverageStrokeReduction(record)}笔`,
      })),
    frequencyTop: records
      .toSorted((a, b) => getFrequency(b) - getFrequency(a))
      .slice(0, 10)
      .map((record) => ({
        simplified: record.simplified,
        title: record.simplified,
        detail: `${record.traditional} · ${record.extensions.cultural_computation?.frequency_profile?.tier ?? "待算"}`,
        value: String(getFrequency(record)),
      })),
  };
}

function analyzeCorpus(text: string, records: CharRecord[]): CorpusCoverage {
  const hanChars = Array.from(text).filter(isHanChar);
  if (!text || !records.length) {
    return {
      totalHan: hanChars.length,
      matchedRecords: 0,
      hitEvents: 0,
      highRiskHits: 0,
      coveragePct: 0,
      topHits: [],
    };
  }

  const charCounts = new Map<string, number>();
  for (const ch of hanChars) {
    charCounts.set(ch, (charCounts.get(ch) ?? 0) + 1);
  }

  const hits = records
    .map((record) => {
      const chars = new Set([
        record.simplified,
        record.traditional,
        ...(record.extensions.traditional_sources ?? []).map((source) => source.char),
      ]);
      const count = Array.from(chars).reduce((sum, ch) => sum + (charCounts.get(ch) ?? 0), 0);
      return { record, count };
    })
    .filter((item) => item.count > 0)
    .sort((a, b) => b.count - a.count);

  const highRiskHits = hits.filter(
    ({ record }) => record.extensions.cultural_computation?.ocr_risk?.level === "高",
  ).length;

  return {
    totalHan: hanChars.length,
    matchedRecords: hits.length,
    hitEvents: hits.reduce((sum, item) => sum + item.count, 0),
    highRiskHits,
    coveragePct: records.length ? (hits.length / records.length) * 100 : 0,
    topHits: hits.slice(0, 10).map(({ record, count }) => ({
      simplified: record.simplified,
      title: record.simplified,
      detail: record.traditional,
      value: `${count}次`,
    })),
  };
}

function exportRecordsAsJson(records: CharRecord[]) {
  if (!records.length) return;
  downloadText(
    "relumine_char_db_frontend_export.json",
    JSON.stringify(records, null, 2),
    "application/json;charset=utf-8",
  );
}

function exportRecordsAsCsv(records: CharRecord[]) {
  if (!records.length) return;
  const rows = records.map((record) => {
    const cultural = record.extensions.cultural_computation;
    return [
      record.simplified,
      record.traditional,
      record.pinyin ?? "",
      record.extensions.curation_level ?? "",
      getSourceCount(record),
      cultural?.semantic_ambiguity?.level ?? "",
      cultural?.ocr_risk?.level ?? "",
      cultural?.ocr_risk?.score ?? 0,
      cultural?.frequency_profile?.tier ?? "",
      cultural?.frequency_profile?.rank_in_database ?? "",
      cultural?.frequency_profile?.cc_cedict_occurrences ?? 0,
      cultural?.stroke_profile?.average_reduction ?? 0,
      (cultural?.cultural_tags ?? []).join(";"),
    ];
  });
  const header = [
    "simplified",
    "traditional",
    "pinyin",
    "curation_level",
    "source_count",
    "semantic_level",
    "ocr_risk_level",
    "ocr_risk_score",
    "frequency_tier",
    "frequency_rank",
    "cc_cedict_occurrences",
    "average_stroke_reduction",
    "cultural_tags",
  ];
  downloadText(
    "relumine_char_db_frontend_export.csv",
    [header, ...rows].map((row) => row.map(escapeCsv).join(",")).join("\n"),
    "text/csv;charset=utf-8",
  );
}

function downloadText(filename: string, text: string, type: string) {
  const blob = new Blob([text], { type });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function escapeCsv(value: string | number) {
  const raw = String(value);
  return /[",\n]/.test(raw) ? `"${raw.replaceAll('"', '""')}"` : raw;
}

function getSourceCount(record?: CharRecord) {
  return record?.extensions.cultural_computation?.semantic_ambiguity?.source_count
    ?? record?.extensions.traditional_sources?.length
    ?? 0;
}

function getOcrScore(record?: CharRecord) {
  return record?.extensions.cultural_computation?.ocr_risk?.score ?? 0;
}

function getRiskLevel(record?: CharRecord) {
  return record?.extensions.cultural_computation?.ocr_risk?.level ?? "待算";
}

function getFrequency(record?: CharRecord) {
  return record?.extensions.cultural_computation?.frequency_profile?.cc_cedict_occurrences ?? 0;
}

function getAverageStrokeReduction(record?: CharRecord) {
  return record?.extensions.cultural_computation?.stroke_profile?.average_reduction ?? 0;
}

function isHanChar(ch: string) {
  return /[\u3400-\u9fff\uf900-\ufaff]/.test(ch);
}

function parseStrokeCount(raw?: string | null) {
  if (!raw) return null;
  const first = String(raw).split(/\s+/)[0];
  const value = Number.parseInt(first, 10);
  return Number.isFinite(value) ? value : null;
}

function getStrokeReduction(record: CharRecord) {
  const simplifiedStrokes = parseStrokeCount(
    record.extensions.external_profile?.unihan?.total_strokes,
  );
  if (simplifiedStrokes === null) return null;

  const sources = record.extensions.traditional_sources ?? [];
  const canonicalSource =
    sources.find((source) => source.char === record.traditional) ?? sources[0];
  const traditionalStrokes = parseStrokeCount(canonicalSource?.unihan?.total_strokes);
  if (traditionalStrokes === null) return null;

  return {
    traditionalStrokes,
    simplifiedStrokes,
    reduction: traditionalStrokes - simplifiedStrokes,
  };
}

function formatStrokeDelta(value: number) {
  if (value > 0) return `−${value}`;
  if (value < 0) return `+${Math.abs(value)}`;
  return "0";
}

function formatCharList(chars: string[]) {
  return chars.slice(0, 5).join("、") + (chars.length > 5 ? "…" : "");
}
