"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import type { ReactNode } from "react";
import { toast } from "sonner";

import { api, ApiError } from "@/lib/api";
import type { CharRecord, CharSummary, CulturalComputation, EvolutionStats } from "@/lib/types";
import { cn } from "@/lib/cn";

import { SectionMark } from "@/components/chinese/SectionMark";
import { CornerBrackets } from "@/components/chinese/CornerBrackets";

type FilterMode = "all" | "high_ocr" | "high_semantic" | "multi_source" | "handcrafted";
type SortMode = "default" | "frequency" | "ocr_risk" | "source_count" | "stroke_reduction";
type Hall = "merge" | "grid";
type GroupAxis = "radical" | "reduction" | "frequency";

export function EvolutionPanel() {
  const [summaries, setSummaries] = useState<CharSummary[]>([]);
  const [stats, setStats] = useState<EvolutionStats | null>(null);
  const [hall, setHall] = useState<Hall>("merge");
  const [active, setActive] = useState<string | null>(null);
  const [record, setRecord] = useState<CharRecord | null>(null);
  const [filterMode, setFilterMode] = useState<FilterMode>("all");
  const [sortMode, setSortMode] = useState<SortMode>("default");
  const [groupAxis, setGroupAxis] = useState<GroupAxis>("radical");
  const [showArchive, setShowArchive] = useState(false);
  const [search, setSearch] = useState("");
  const [corpusText, setCorpusText] = useState("");
  const [showInfo, setShowInfo] = useState(false);
  const [loadingList, setLoadingList] = useState(true);
  const [loadingRecord, setLoadingRecord] = useState(false);

  const recordCache = useRef(new Map<string, CharRecord>());
  const activeRef = useRef<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    Promise.all([api.evolution.list(), api.evolution.stats()])
      .then(([list, statsData]) => {
        if (cancelled) return;
        setSummaries(list);
        setStats(statsData);
        const firstMerge = list.find((item) => item.record_type === "merge") ?? list[0];
        if (firstMerge) selectChar(firstMerge.simplified);
      })
      .catch((e) => {
        const detail = e instanceof ApiError ? e.message : "字库加载失败";
        toast.error(detail);
      })
      .finally(() => !cancelled && setLoadingList(false));
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function prefetchChar(char: string) {
    if (recordCache.current.has(char)) return;
    api.evolution
      .get(char)
      .then((r) => recordCache.current.set(char, r))
      .catch(() => undefined);
  }

  function selectChar(char: string) {
    activeRef.current = char;
    setActive(char);
    const cached = recordCache.current.get(char);
    if (cached) {
      setRecord(cached);
      return;
    }
    setRecord(null);
    setLoadingRecord(true);
    api.evolution
      .get(char)
      .then((r) => {
        recordCache.current.set(char, r);
        if (activeRef.current === char) setRecord(r);
      })
      .catch((e) => {
        const detail = e instanceof ApiError ? e.message : "加载失败";
        toast.error(detail);
      })
      .finally(() => {
        if (activeRef.current === char) setLoadingRecord(false);
      });
  }

  const mergeList = useMemo(
    () => summaries.filter((item) => item.record_type === "merge" && item.curation_level !== "auto_slim"),
    [summaries],
  );
  const slimMergeCount = useMemo(
    () => summaries.filter((item) => item.record_type === "merge" && item.curation_level === "auto_slim").length,
    [summaries],
  );
  const gridList = useMemo(
    () => summaries.filter((item) => (showArchive ? true : item.display_tier === "grid")),
    [showArchive, summaries],
  );

  const visibleMergeList = useMemo(
    () => applyFilterAndSort(mergeList, filterMode, sortMode),
    [filterMode, mergeList, sortMode],
  );

  const searchHits = useMemo(() => searchSummaries(summaries, search), [search, summaries]);
  const dashboard = useMemo(() => buildDashboard(mergeList), [mergeList]);
  const corpusCoverage = useMemo(
    () => analyzeCorpus(corpusText, summaries),
    [corpusText, summaries],
  );

  return (
    <section className="relative rounded-[var(--radius)] border border-line bg-surface p-8 md:p-12 animate-ink-rise">
      <CornerBrackets />
      <div className="flex items-start justify-between gap-4">
        <SectionMark title="形声流变" subtitle="一简 · 多对一合并 · 全量通检" />
        <button
          type="button"
          aria-label="数据来源说明"
          onClick={() => setShowInfo(true)}
          className="mt-1 flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-line font-serif text-sm text-ink-mute transition-colors hover:border-accent hover:text-accent"
        >
          ⓘ
        </button>
      </div>

      {/* ── 规模与统计摘要 ── */}
      <div className="mt-6 grid grid-cols-2 sm:grid-cols-4 gap-px bg-line border border-line">
        {[
          { label: "收录字数", value: loadingList ? "…" : String(stats?.total ?? summaries.length) },
          { label: "多源合并", value: loadingList ? "…" : String(stats?.merge_count ?? 0) },
          { label: "人工精修", value: loadingList ? "…" : String(stats?.handcrafted_count ?? 0) },
          {
            label: "平均笔画削减",
            value: stats?.avg_stroke_reduction != null ? `${stats.avg_stroke_reduction} 笔` : "…",
          },
        ].map(({ label, value }) => (
          <div key={label} className="bg-surface px-4 py-3">
            <div className="text-[10px] font-sans tracking-[0.16em] uppercase text-ink-mute mb-1">
              {label}
            </div>
            <div className="font-serif text-lg text-ink">{value}</div>
          </div>
        ))}
      </div>

      {/* ── 全局检索 ── */}
      <div className="mt-6">
        <input
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder="检索单字（繁简皆可，如：发 / 發 / 髮）"
          className="w-full border border-line bg-surface px-4 py-2.5 font-serif text-sm text-ink outline-none placeholder:text-ink-mute/70"
        />
        {search.trim() ? (
          <div className="mt-3 flex flex-wrap gap-2">
            {searchHits.length === 0 ? (
              <span className="font-serif text-sm text-ink-mute">未检索到匹配字</span>
            ) : (
              searchHits.map((item) => (
                <button
                  key={item.simplified}
                  type="button"
                  onMouseEnter={() => prefetchChar(item.simplified)}
                  onClick={() => selectChar(item.simplified)}
                  className={cn(
                    "flex items-center gap-2 border border-line px-3 py-1.5 font-serif text-sm transition-colors hover:border-accent hover:text-accent",
                    item.simplified === active ? "border-accent text-accent" : "text-ink-soft",
                  )}
                >
                  <span className="text-lg leading-none">{item.simplified}</span>
                  <span className="text-ink-mute">{item.traditional}</span>
                  {item.record_type === "merge" ? (
                    <span className="border border-accent/50 px-1.5 py-0.5 text-[10px] font-sans tracking-[0.1em] text-accent">
                      多源合并
                    </span>
                  ) : null}
                </button>
              ))
            )}
          </div>
        ) : null}
      </div>

      {/* ── 双馆切换 ── */}
      <div className="mt-8 flex border-b border-line">
        {(
          [
            { key: "merge" as const, label: "壹 · 合并疑难", hint: `${mergeList.length} 字深度解析` },
            { key: "grid" as const, label: "貳 · 通检", hint: `全库 ${stats?.total ?? 0} 字` },
          ]
        ).map(({ key, label, hint }) => (
          <button
            key={key}
            type="button"
            onClick={() => setHall(key)}
            className={cn(
              "relative px-5 py-3 font-serif text-sm tracking-[0.08em] transition-colors",
              hall === key ? "text-ink" : "text-ink-mute hover:text-ink-soft",
            )}
          >
            {label}
            <span className="ml-2 font-sans text-[10px] text-ink-mute">{hint}</span>
            {hall === key ? (
              <span aria-hidden className="absolute inset-x-3 bottom-0 h-0.5 bg-accent" />
            ) : null}
          </button>
        ))}
      </div>
      <p className="mt-2 font-sans text-[11px] leading-relaxed text-ink-mute">
        通检收录全部 {stats?.total ?? 0} 字（常用 {stats?.grid_count ?? 0} + 异体生僻{" "}
        {stats?.archive_count ?? 0}）；合并疑难是其中 {mergeList.length}{" "}
        个多对一合并字的深度解析子集，含 {stats?.handcrafted_count ?? 0} 个人工精修字，两馆字目有重叠。
      </p>

      {hall === "merge" ? (
        <>
          <DatabaseDashboard
            dashboard={dashboard}
            mergeCount={mergeList.length}
            slimMergeCount={slimMergeCount}
            loading={loadingList}
            onSelect={selectChar}
          />

          <CorpusCoveragePanel
            value={corpusText}
            coverage={corpusCoverage}
            disabled={!summaries.length}
            onChange={setCorpusText}
          />

          <div className="mt-8 grid grid-cols-1 lg:grid-cols-[260px_1fr] gap-10">
            <div>
              <div className="mb-4 space-y-3">
                <div className="flex items-center justify-between gap-3">
                  <div className="text-xs font-sans tracking-[0.16em] uppercase text-ink-mute">
                    字 · {loadingList ? "…" : visibleMergeList.length}
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
                    <option value="multi_source">来源 ≥ 3</option>
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
                    onClick={() => exportSummariesAsJson(summaries)}
                    disabled={!summaries.length}
                    className="border border-line px-3 py-2 font-sans text-xs tracking-[0.12em] text-ink-mute transition-colors hover:border-accent hover:text-accent disabled:opacity-40"
                  >
                    导出 JSON
                  </button>
                  <button
                    type="button"
                    onClick={() => exportSummariesAsCsv(summaries)}
                    disabled={!summaries.length}
                    className="border border-line px-3 py-2 font-sans text-xs tracking-[0.12em] text-ink-mute transition-colors hover:border-accent hover:text-accent disabled:opacity-40"
                  >
                    导出 CSV
                  </button>
                </div>
              </div>
              <div className="max-h-[60vh] overflow-y-auto overscroll-contain border border-line">
              <div className="grid grid-cols-5 lg:grid-cols-4 gap-px bg-line">
                {visibleMergeList.map((c, idx) => {
                  const isActive = c.simplified === active;
                  const isHighRisk = c.ocr_risk_level === "高";
                  return (
                    <button
                      key={c.simplified}
                      onMouseEnter={() => prefetchChar(c.simplified)}
                      onClick={() => selectChar(c.simplified)}
                      className={cn(
                        "relative aspect-square bg-surface flex items-center justify-center",
                        "font-serif text-2xl text-ink transition-colors duration-200",
                        "hover:bg-bg animate-ink-rise-soft",
                        isActive && "bg-bg",
                      )}
                      style={{ animationDelay: `${Math.min(idx, 40) * 30}ms` }}
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
            </div>

            <div className="lg:sticky lg:top-4 lg:self-start lg:max-h-[85vh] lg:overflow-y-auto lg:overscroll-contain lg:pr-2">
              <DetailColumn record={record} loading={loadingRecord} />
            </div>
          </div>
        </>
      ) : (
        <CharGridHall
          list={gridList}
          stats={stats}
          active={active}
          groupAxis={groupAxis}
          showArchive={showArchive}
          onGroupAxis={setGroupAxis}
          onShowArchive={setShowArchive}
          onHover={prefetchChar}
          onSelect={selectChar}
          record={record}
          loadingRecord={loadingRecord}
        />
      )}

      {showInfo ? <DataSourceModal onClose={() => setShowInfo(false)} /> : null}
    </section>
  );
}

function DetailColumn({ record, loading }: { record: CharRecord | null; loading: boolean }) {
  if (!record) {
    return loading ? <RecordSkeleton /> : <div className="text-sm text-ink-mute">选择一个字</div>;
  }
  return <RecordView record={record} />;
}

function RecordSkeleton() {
  return (
    <div className="animate-pulse" aria-hidden>
      <div className="flex items-baseline gap-6">
        <div className="h-16 w-16 bg-line/60" />
        <div className="h-12 w-12 bg-line/50" />
        <div className="h-4 w-20 bg-line/40" />
      </div>
      <div className="mt-8 h-4 w-3/4 bg-line/40" />
      <div className="mt-3 h-4 w-2/3 bg-line/40" />
      <div className="mt-8 h-24 w-full bg-line/30" />
    </div>
  );
}

/* ── 通检馆：高密度字阵 ── */

type GridGroup = { key: string; label: string; items: CharSummary[] };

function CharGridHall({
  list,
  stats,
  active,
  groupAxis,
  showArchive,
  onGroupAxis,
  onShowArchive,
  onHover,
  onSelect,
  record,
  loadingRecord,
}: {
  list: CharSummary[];
  stats: EvolutionStats | null;
  active: string | null;
  groupAxis: GroupAxis;
  showArchive: boolean;
  onGroupAxis: (axis: GroupAxis) => void;
  onShowArchive: (value: boolean) => void;
  onHover: (char: string) => void;
  onSelect: (char: string) => void;
  record: CharRecord | null;
  loadingRecord: boolean;
}) {
  const groups = useMemo(() => buildGridGroups(list, groupAxis), [groupAxis, list]);
  const scrollRef = useRef<HTMLDivElement | null>(null);

  return (
    <div className="mt-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-1 border border-line p-0.5">
          {(
            [
              { key: "radical" as const, label: "按部首" },
              { key: "reduction" as const, label: "按笔画削减" },
              { key: "frequency" as const, label: "按字频" },
            ]
          ).map(({ key, label }) => (
            <button
              key={key}
              type="button"
              onClick={() => onGroupAxis(key)}
              className={cn(
                "px-3 py-1.5 font-sans text-xs tracking-[0.12em] transition-colors",
                groupAxis === key ? "bg-bg text-ink" : "text-ink-mute hover:text-ink-soft",
              )}
            >
              {label}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-4">
          <span className="font-sans text-xs text-ink-mute">当前显示 {list.length} 字</span>
          <label className="flex cursor-pointer items-center gap-2 font-sans text-xs text-ink-mute">
            <input
              type="checkbox"
              checked={showArchive}
              onChange={(event) => onShowArchive(event.target.checked)}
              className="accent-[var(--accent,#a33)]"
            />
            含异体 / 生僻字（+{stats?.archive_count ?? 0}）
          </label>
        </div>
      </div>

      {/* 分组锚点 */}
      <div className="mt-4 flex flex-wrap gap-1.5">
        {groups.map((group) => (
          <button
            key={group.key}
            type="button"
            onClick={() =>
              scrollRef.current
                ?.querySelector(`#grid-group-${group.key}`)
                ?.scrollIntoView({ block: "start", behavior: "smooth" })
            }
            className="border border-line px-2 py-1 font-serif text-xs text-ink-mute transition-colors hover:border-accent hover:text-accent"
          >
            {group.label.split(" ")[0]}
            <span className="ml-1 font-sans text-[10px]">{group.items.length}</span>
          </button>
        ))}
      </div>

      <div className="mt-5 grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_400px] gap-8">
        {/* 字阵：容器内滚动 */}
        <div
          ref={scrollRef}
          className="max-h-[72vh] overflow-y-auto overscroll-contain border border-line bg-surface pr-1"
        >
          {groups.map((group) => (
            <div key={group.key} id={`grid-group-${group.key}`} className="px-3 pb-2 pt-4 scroll-mt-2">
              <div className="mb-2 flex items-baseline gap-3 border-b border-line pb-1.5">
                <span className="font-serif text-base text-ink">{group.label}</span>
                <span className="font-sans text-xs text-ink-mute">{group.items.length} 字</span>
              </div>
              <div
                className="grid gap-px bg-line"
                style={{
                  gridTemplateColumns: "repeat(auto-fill, minmax(2.6rem, 1fr))",
                  contentVisibility: "auto",
                  containIntrinsicSize: `${Math.ceil(group.items.length / 18) * 2.7}rem`,
                }}
              >
                {group.items.map((item) => (
                  <button
                    key={item.simplified}
                    type="button"
                    onMouseEnter={() => onHover(item.simplified)}
                    onClick={() => onSelect(item.simplified)}
                    title={`${item.simplified}${item.pinyin ? ` · ${item.pinyin}` : ""}${item.record_type === "merge" ? " · 多源合并" : ""}`}
                    className={cn(
                      "group relative aspect-square bg-surface flex items-center justify-center font-serif text-xl transition-colors hover:bg-bg",
                      item.simplified === active ? "bg-bg text-accent" : "text-ink",
                    )}
                  >
                    {item.traditional}
                    {item.record_type === "merge" ? (
                      <span aria-hidden className="absolute right-1 top-1 h-1 w-1 bg-accent" />
                    ) : null}
                  </button>
                ))}
              </div>
            </div>
          ))}
        </div>

        {/* 详情：吸顶侧栏，自身滚动 */}
        <div className="xl:sticky xl:top-4 xl:self-start xl:max-h-[72vh] xl:overflow-y-auto xl:overscroll-contain border-t xl:border-t-0 border-line pt-6 xl:pt-0 xl:pl-2">
          <DetailColumn record={record} loading={loadingRecord} />
        </div>
      </div>
    </div>
  );
}

function buildGridGroups(list: CharSummary[], axis: GroupAxis): GridGroup[] {
  if (axis === "radical") {
    const byRadical = new Map<string, CharSummary[]>();
    for (const item of list) {
      const key = item.radical || "未知";
      const bucket = byRadical.get(key);
      if (bucket) bucket.push(item);
      else byRadical.set(key, [item]);
    }
    return Array.from(byRadical.entries())
      .sort(([a], [b]) => {
        if (a === "未知") return 1;
        if (b === "未知") return -1;
        return a.codePointAt(0)! - b.codePointAt(0)!;
      })
      .map(([radical, items]) => ({
        key: `r-${radical.codePointAt(0)?.toString(16) ?? "x"}`,
        label: `${radical} 部`,
        items: items.toSorted(
          (a, b) => (a.simp_strokes ?? 99) - (b.simp_strokes ?? 99),
        ),
      }));
  }

  if (axis === "reduction") {
    const buckets: Array<{ key: string; label: string; match: (v: number | null | undefined) => boolean }> = [
      { key: "ge10", label: "削减 ≥10 笔", match: (v) => v != null && v >= 10 },
      { key: "7to9", label: "削减 7–9 笔", match: (v) => v != null && v >= 7 && v <= 9 },
      { key: "4to6", label: "削减 4–6 笔", match: (v) => v != null && v >= 4 && v <= 6 },
      { key: "1to3", label: "削减 1–3 笔", match: (v) => v != null && v >= 1 && v <= 3 },
      { key: "le0", label: "无削减 / 反增", match: (v) => v != null && v <= 0 },
      { key: "unknown", label: "笔画未知", match: (v) => v == null },
    ];
    return buckets
      .map(({ key, label, match }) => ({
        key,
        label,
        items: list
          .filter((item) => match(item.stroke_reduction))
          .toSorted((a, b) => (b.stroke_reduction ?? -99) - (a.stroke_reduction ?? -99)),
      }))
      .filter((group) => group.items.length > 0);
  }

  const tiers = ["高频", "中频", "低频"];
  return tiers
    .map((tier) => ({
      key: `f-${tier}`,
      label: `${tier}用字`,
      items: list
        .filter((item) => (item.frequency_tier ?? "低频") === tier)
        .toSorted((a, b) => (b.frequency ?? 0) - (a.frequency ?? 0)),
    }))
    .filter((group) => group.items.length > 0);
}

/* ── 数据来源弹窗 ── */

const DATA_SOURCES = [
  {
    name: "Relumine 字库",
    org: "本项目自建",
    logo: "重",
    accent: true,
    scale: "4,941 字 · 211 组繁简来源对",
    description:
      "在下面四个外部数据库之上整合而成。除了记录“繁体 X 对应简体 Y”，还标注每个字是怎么简化的（草书楷化、古字复用、多对一合并等）、合并造成了哪些语义混淆，并为每个字算出 OCR 风险、语义歧义度等指标。其中 10 个典型字带人工考据的演化时间轴。",
    license: "项目内部",
  },
  {
    name: "Unihan",
    org: "Unicode Consortium",
    logo: "U",
    accent: false,
    scale: "102,998 字",
    description:
      "Unicode 官方的汉字属性数据库，收录了几乎所有能编码的汉字。我们从中取每个字的笔画数、部首、普通话读音、英文释义，以及官方标注的繁简变体关系，作为最权威的基础属性来源。",
    license: "Unicode License",
  },
  {
    name: "OpenCC",
    org: "开源项目（BYVoid）",
    logo: "OC",
    accent: false,
    scale: "8,130 条单字映射",
    description:
      "目前最常用的开源繁简转换工具，其词典是社区多年人工维护的成果。我们用它的简↔繁单字映射表确定全量字库的收录范围——哪些字算繁简对应、一个简体字对应几个繁体，都以它为基准。",
    license: "Apache-2.0",
  },
  {
    name: "CC-CEDICT",
    org: "社区维护词典",
    logo: "CC",
    accent: false,
    scale: "125,002 个词条",
    description:
      "开放的中英词典，每个词条同时给出繁体、简体写法和英文释义。我们把它当作“真实用词”的证据库：一对繁简映射在多少个词里出现过，既用来验证映射是否可靠，也作为字频的代理指标。",
    license: "CC BY-SA 4.0",
  },
  {
    name: "CHISE IDS",
    org: "CHISE 项目（京都大学）",
    logo: "IDS",
    accent: false,
    scale: "97,431 字的结构分解",
    description:
      "把每个汉字拆解成部件组合的结构数据库（如“湖 = 氵 + 胡”）。我们用它对比简化前后的部件变化——哪些部件被省掉、哪些被替换，是计算字形差异和 OCR 混淆风险的依据。",
    license: "GPL-2.0+",
  },
];

function DataSourceModal({ onClose }: { onClose: () => void }) {
  // Portal to body: ancestors use transform animations, which would otherwise
  // turn them into the containing block for this fixed-position overlay.
  return createPortal(
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      role="dialog"
      aria-modal="true"
      aria-label="数据来源说明"
      onClick={onClose}
    >
      <div
        className="relative max-h-[85vh] w-full max-w-3xl overflow-y-auto overscroll-contain border border-line bg-surface p-8"
        onClick={(event) => event.stopPropagation()}
      >
        <CornerBrackets />
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="font-serif text-xl text-ink">数据来源</div>
            <p className="mt-2 max-w-lg font-serif text-sm leading-[1.9] text-ink-soft">
              本字库由四个公开数据库整合而成，各取所长，再加上项目自己的标注和计算。
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="关闭"
            className="border border-line px-2.5 py-1 font-sans text-xs text-ink-mute transition-colors hover:border-accent hover:text-accent"
          >
            ✕
          </button>
        </div>
        <div className="mt-6 grid grid-cols-1 sm:grid-cols-2 gap-4">
          {DATA_SOURCES.map((source) => (
            <div
              key={source.name}
              className={cn(
                "border p-4",
                source.accent ? "border-accent/50 sm:col-span-2" : "border-line",
              )}
            >
              <div className="flex items-center gap-3">
                <span
                  aria-hidden
                  className={cn(
                    "flex h-10 w-10 shrink-0 items-center justify-center border font-serif text-base",
                    source.accent
                      ? "border-accent bg-accent/10 text-accent"
                      : "border-line bg-bg text-ink-soft",
                  )}
                >
                  {source.logo}
                </span>
                <div className="min-w-0">
                  <div className="font-serif text-base leading-tight text-ink">{source.name}</div>
                  <div className="mt-0.5 font-sans text-[11px] text-ink-mute">{source.org}</div>
                </div>
              </div>
              <div className="mt-3 font-sans text-xs text-ink-mute">{source.scale}</div>
              <p className="mt-2 font-serif text-sm leading-[1.8] text-ink-soft">
                {source.description}
              </p>
              <div className="mt-2 font-sans text-[10px] tracking-[0.12em] uppercase text-ink-mute">
                {source.license}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>,
    document.body,
  );
}

/* ── 合并疑难馆：仪表盘 / 语料覆盖 ── */

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
  dashboard,
  mergeCount,
  slimMergeCount,
  loading,
  onSelect,
}: {
  dashboard: DashboardData;
  mergeCount: number;
  slimMergeCount: number;
  loading: boolean;
  onSelect: (char: string) => void;
}) {
  return (
    <div className="mt-8 border-y border-line py-6">
      <div className="mb-4 flex flex-wrap items-baseline justify-between gap-3">
        <div className="text-xs font-sans tracking-[0.16em] uppercase text-ink-mute">
          合并疑难总览
        </div>
        <div className="font-serif text-sm text-ink-mute">
          {loading
            ? "分析指标加载中…"
            : `${mergeCount} 字精览 · 另有 ${slimMergeCount} 个合并字收录于通检`}
        </div>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-px bg-line border border-line">
        <SummaryCell label="OCR 高风险" value={String(dashboard.highOcrCount)} />
        <SummaryCell label="高语义歧义" value={String(dashboard.highSemanticCount)} />
        <SummaryCell label="来源 ≥ 3" value={String(dashboard.multiSourceCount)} />
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

/* ── 单字详情（覆盖度分档降级） ── */

function coverageCount(record: CharRecord): number {
  const coverage = record.extensions.coverage ?? {};
  return Object.values(coverage).filter(Boolean).length;
}

function RecordView({ record }: { record: CharRecord }) {
  const extensions = record.extensions ?? {};
  const external = extensions.external_profile;
  const unihan = external?.unihan;
  const sources = extensions.traditional_sources ?? [];
  const types = extensions.simplification_types ?? [];
  const curation = extensions.curation_level;
  const isAuto = curation === "auto_external";
  const isSlim = curation === "auto_slim";
  const covered = coverageCount(record);
  const sparse = covered <= 1 || (isSlim && !record.pinyin);
  const partial = !sparse && isSlim && covered <= 2;
  const strokeReduction = getStrokeReduction(record);
  const cultural = extensions.cultural_computation;
  const variantWording = !record.pinyin ? "异体字" : "罕用字";

  return (
    <article key={record.simplified}>
      <header className="mb-8">
        <div className="flex flex-wrap items-baseline gap-x-6 gap-y-3">
          <div className="font-serif text-6xl tracking-[0.04em] text-ink animate-ink-rise">
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
          <MetaPill>
            {curation === "handcrafted" ? "人工精修" : isAuto ? "外部证据扩展" : "全量收录"}
          </MetaPill>
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

      {sparse ? (
        <div className="border-l-2 border-line pl-4 font-serif text-sm leading-[1.9] text-ink-soft">
          本字为{variantWording}，目前仅录得繁简对应关系
          {record.merges.length > 0 ? `（${record.merges.join(" / ")} → ${record.simplified}）` : ""}
          ，详细考据待补。
        </div>
      ) : (
        <>
          {isAuto ? (
            <div className="mb-6 border-l-2 border-accent-gold pl-4 font-serif text-sm leading-[1.9] text-ink-soft">
              该字已接入外部数据库证据，历史演化时间线仍待人工考据补写。
            </div>
          ) : null}

          {external ? (
            <div className="mb-8 grid grid-cols-1 md:grid-cols-3 gap-4 border-y border-line py-5">
              <EvidenceStat label="Unihan" value={unihan?.mandarin || record.pinyin || "已收录"} />
              {external.chise_ids ? (
                <EvidenceStat label="CHISE IDS" value={external.chise_ids} />
              ) : null}
              <EvidenceStat
                label="OpenCC"
                value={(external.opencc_simplified_to_traditional ?? []).join(" / ") || "已映射"}
              />
            </div>
          ) : null}

          {cultural ? <CulturalComputationView computation={cultural} /> : null}

          {sources.length > 0 && !isSlim ? (
            <div className="mb-8">
              <div className="text-xs font-sans tracking-[0.16em] uppercase text-ink-mute mb-3">
                来源字证据
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-x-8 gap-y-5">
                {sources.map((source) => (
                  <SourceEvidence key={`${record.simplified}-${source.char}`} source={source} />
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
              <div
                aria-hidden
                className="absolute left-3 top-2 bottom-3 w-px bg-line origin-top animate-line-draw-y"
                style={{ animationDelay: "240ms", animationDuration: "700ms" }}
              />
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

          {partial ? (
            <div className="mt-2 font-serif text-xs leading-[1.8] text-ink-mute">
              本字在现代语料中用例较少，部分分析维度暂缺。
            </div>
          ) : null}
        </>
      )}

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
          {examples.slice(0, 2).map((example, index) => (
            <div
              key={`${source.char}-${example.traditional}-${example.simplified}-${index}`}
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

/* ── 摘要层工具函数 ── */

function sourceCount(item: CharSummary) {
  if (!item.merges) return 0;
  return item.merges.split(" ").filter(Boolean).length;
}

function searchSummaries(summaries: CharSummary[], query: string): CharSummary[] {
  const q = query.trim();
  if (!q) return [];
  const chars = Array.from(q).filter(isHanChar);
  if (!chars.length) return [];
  const charSet = new Set(chars);
  return summaries
    .filter(
      (item) =>
        charSet.has(item.simplified) ||
        Array.from(item.traditional).some((ch) => charSet.has(ch)) ||
        (item.merges ?? "").split(" ").some((ch) => charSet.has(ch)),
    )
    .slice(0, 30);
}

function applyFilterAndSort(list: CharSummary[], filterMode: FilterMode, sortMode: SortMode) {
  const filtered = list.filter((item) => {
    if (filterMode === "all") return true;
    if (filterMode === "high_ocr") return item.ocr_risk_level === "高";
    if (filterMode === "high_semantic") return item.semantic_level === "高";
    if (filterMode === "multi_source") return sourceCount(item) >= 3;
    if (filterMode === "handcrafted") return item.curation_level === "handcrafted";
    return true;
  });

  return [...filtered].sort((a, b) => {
    if (sortMode === "default") return 0;
    if (sortMode === "frequency") return (b.frequency ?? 0) - (a.frequency ?? 0);
    if (sortMode === "ocr_risk") return (b.ocr_risk_score ?? 0) - (a.ocr_risk_score ?? 0);
    if (sortMode === "source_count") return sourceCount(b) - sourceCount(a);
    if (sortMode === "stroke_reduction")
      return (b.avg_stroke_reduction ?? 0) - (a.avg_stroke_reduction ?? 0);
    return 0;
  });
}

function buildDashboard(list: CharSummary[]): DashboardData {
  return {
    highOcrCount: list.filter((item) => item.ocr_risk_level === "高").length,
    highSemanticCount: list.filter((item) => item.semantic_level === "高").length,
    multiSourceCount: list.filter((item) => sourceCount(item) >= 3).length,
    highFrequencyCount: list.filter((item) => item.frequency_tier === "高频").length,
    ocrTop: list
      .toSorted((a, b) => (b.ocr_risk_score ?? 0) - (a.ocr_risk_score ?? 0))
      .slice(0, 10)
      .map((item) => ({
        simplified: item.simplified,
        title: item.simplified,
        detail: `${item.traditional} · ${item.ocr_risk_level ?? "待算"}风险`,
        value: `${item.ocr_risk_score ?? 0}分`,
      })),
    semanticTop: list
      .toSorted((a, b) => sourceCount(b) - sourceCount(a))
      .slice(0, 10)
      .map((item) => ({
        simplified: item.simplified,
        title: item.simplified,
        detail: `${item.traditional} · ${sourceCount(item)}个来源`,
        value: item.semantic_level ?? "待算",
      })),
    strokeTop: list
      .toSorted((a, b) => (b.avg_stroke_reduction ?? 0) - (a.avg_stroke_reduction ?? 0))
      .slice(0, 10)
      .map((item) => ({
        simplified: item.simplified,
        title: item.simplified,
        detail: `${item.traditional} · ${sourceCount(item)}个来源`,
        value: `${item.avg_stroke_reduction ?? 0}笔`,
      })),
    frequencyTop: list
      .toSorted((a, b) => (b.frequency ?? 0) - (a.frequency ?? 0))
      .slice(0, 10)
      .map((item) => ({
        simplified: item.simplified,
        title: item.simplified,
        detail: `${item.traditional} · ${item.frequency_tier ?? "待算"}`,
        value: String(item.frequency ?? 0),
      })),
  };
}

function analyzeCorpus(text: string, summaries: CharSummary[]): CorpusCoverage {
  const hanChars = Array.from(text).filter(isHanChar);
  if (!text || !summaries.length) {
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

  const hits = summaries
    .map((item) => {
      const chars = new Set([
        item.simplified,
        ...Array.from(item.traditional),
        ...(item.merges ?? "").split(" ").filter(Boolean),
      ]);
      const count = Array.from(chars).reduce((sum, ch) => sum + (charCounts.get(ch) ?? 0), 0);
      return { item, count };
    })
    .filter((entry) => entry.count > 0)
    .sort((a, b) => b.count - a.count);

  const highRiskHits = hits.filter(({ item }) => item.ocr_risk_level === "高").length;

  return {
    totalHan: hanChars.length,
    matchedRecords: hits.length,
    hitEvents: hits.reduce((sum, entry) => sum + entry.count, 0),
    highRiskHits,
    coveragePct: summaries.length ? (hits.length / summaries.length) * 100 : 0,
    topHits: hits.slice(0, 10).map(({ item, count }) => ({
      simplified: item.simplified,
      title: item.simplified,
      detail: item.traditional,
      value: `${count}次`,
    })),
  };
}

function exportSummariesAsJson(summaries: CharSummary[]) {
  if (!summaries.length) return;
  downloadText(
    "relumine_char_db_frontend_export.json",
    JSON.stringify(summaries, null, 2),
    "application/json;charset=utf-8",
  );
}

function exportSummariesAsCsv(summaries: CharSummary[]) {
  if (!summaries.length) return;
  const header = [
    "simplified",
    "traditional",
    "pinyin",
    "record_type",
    "curation_level",
    "radical",
    "stroke_reduction",
    "frequency",
    "frequency_tier",
    "ocr_risk_level",
    "ocr_risk_score",
    "semantic_level",
    "merges",
  ];
  const rows = summaries.map((item) => [
    item.simplified,
    item.traditional,
    item.pinyin ?? "",
    item.record_type ?? "",
    item.curation_level ?? "",
    item.radical ?? "",
    item.stroke_reduction ?? "",
    item.frequency ?? 0,
    item.frequency_tier ?? "",
    item.ocr_risk_level ?? "",
    item.ocr_risk_score ?? "",
    item.semantic_level ?? "",
    item.merges ?? "",
  ]);
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

function isHanChar(ch: string) {
  return /[㐀-鿿豈-﫿]/.test(ch);
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
