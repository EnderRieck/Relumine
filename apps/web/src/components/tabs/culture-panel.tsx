"use client";

import { useEffect, useMemo, useState } from "react";
import {
  Check,
  ChevronRight,
  Clock3,
  Database,
  ExternalLink,
  FileSearch,
  LoaderCircle,
  MapPin,
  Network,
  RefreshCw,
  RotateCcw,
  Sparkles,
  X,
} from "lucide-react";
import { toast } from "sonner";

import { CornerBrackets } from "@/components/chinese/CornerBrackets";
import { SectionMark } from "@/components/chinese/SectionMark";
import { IconMeridian } from "@/components/chinese/BrushIcons";
import { api, ApiError } from "@/lib/api";
import { cn } from "@/lib/cn";
import { useRegisterSnapshot, useRegisterAction } from "@/lib/agent-bridge";
import type {
  CulturalEntity,
  CulturalRelation,
  CultureAnalysis,
  CultureAnalysisSummary,
  CultureStatus,
  EntityType,
  NameConversion,
  ReviewStatus,
} from "@/lib/types";

const SAMPLE_TEXT =
  "王安石，字介甫，临川人。庆历二年登进士第。知鄞县，起堤堰，决陂塘，为水陆之利。熙宁二年，拜参知政事，明年拜相。";

const ENTITY_LABELS: Record<EntityType, string> = {
  person: "人物",
  place: "地点",
  office: "官职",
  time: "时间",
  event: "事件",
  work: "作品",
  organization: "组织",
  other: "其他",
};

const ENTITY_COLORS: Record<EntityType, string> = {
  person: "#9a2a1f",
  place: "#356859",
  office: "#7b5a2f",
  time: "#6d6486",
  event: "#3f6684",
  work: "#95633b",
  organization: "#536b3f",
  other: "#77736d",
};

export function CulturePanel() {
  const [text, setText] = useState(SAMPLE_TEXT);
  const [title, setTitle] = useState("");
  const [analysis, setAnalysis] = useState<CultureAnalysis | null>(null);
  const [history, setHistory] = useState<CultureAnalysisSummary[]>([]);
  const [service, setService] = useState<CultureStatus | null>(null);
  const [pending, setPending] = useState(false);
  const [selectedRelation, setSelectedRelation] =
    useState<CulturalRelation | null>(null);
  const [selectedEntity, setSelectedEntity] = useState<CulturalEntity | null>(
    null,
  );

  useEffect(() => {
    const stored = localStorage.getItem("relumine:culture-source");
    if (stored) queueMicrotask(() => setText(stored));
    const receiveText = (event: Event) => {
      const incoming = (event as CustomEvent<string>).detail;
      if (incoming) setText(incoming);
    };
    window.addEventListener("relumine:culture-source", receiveText);
    return () =>
      window.removeEventListener("relumine:culture-source", receiveText);
  }, []);

  useEffect(() => {
    Promise.all([api.culture.status(), api.culture.list()])
      .then(([nextStatus, items]) => {
        setService(nextStatus);
        setHistory(items);
      })
      .catch(() =>
        setService({
          configured: false,
          model: "DeepSeek",
          cbdb_available: false,
          chgis_available: false,
        }),
      );
  }, []);

  async function runAnalysis() {
    const source = text.trim();
    if (source.length < 2) {
      toast.error("请先输入古籍原文");
      return;
    }
    setPending(true);
    setSelectedEntity(null);
    setSelectedRelation(null);
    try {
      const result = await api.culture.analyze(source, title.trim());
      setAnalysis(result);
      setHistory((current) => [
        {
          id: result.id,
          title: result.title,
          summary: result.summary,
          entity_count: result.entities.length,
          relation_count: result.relations.length,
          created_at: result.created_at,
        },
        ...current.filter((item) => item.id !== result.id),
      ]);
      toast.success(
        `抽取完成 · ${result.entities.length} 个实体 · ${result.relations.length} 条关系`,
      );
    } catch (error) {
      toast.error(error instanceof ApiError ? error.message : "文化关系分析失败");
    } finally {
      setPending(false);
    }
  }

  // ----- Agent bridge: read & operate the culture (史脉) panel -----
  useRegisterSnapshot("culture", () => ({
    text,
    title,
    hasAnalysis: !!analysis,
    entityCount: analysis?.entities.length ?? 0,
    relationCount: analysis?.relations.length ?? 0,
  }));
  useRegisterAction("set_culture_text", (args) => {
    const next = String(args.text ?? "");
    setText(next);
    if (typeof args.title === "string") setTitle(args.title);
    return { ok: true };
  });
  useRegisterAction("run_culture_analysis", async () => {
    await runAnalysis();
    return { ok: true };
  });

  async function openHistory(id: string) {
    try {
      const result = await api.culture.get(id);
      setAnalysis(result);
      setText(result.source_text);
      setTitle(result.title);
      setSelectedEntity(null);
      setSelectedRelation(null);
    } catch (error) {
      toast.error(error instanceof ApiError ? error.message : "读取分析失败");
    }
  }

  async function review(
    kind: "entity" | "relation",
    id: string,
    status: ReviewStatus,
  ) {
    if (!analysis) return;
    try {
      const updated = await api.culture.review(
        analysis.id,
        kind === "entity"
          ? { entity_statuses: { [id]: status } }
          : { relation_statuses: { [id]: status } },
      );
      setAnalysis(updated);
      if (kind === "entity") {
        setSelectedEntity(updated.entities.find((item) => item.id === id) ?? null);
      } else {
        setSelectedRelation(
          updated.relations.find((item) => item.id === id) ?? null,
        );
      }
      toast.success(status === "confirmed" ? "已确认为可信条目" : "已标记为驳回");
    } catch (error) {
      toast.error(error instanceof ApiError ? error.message : "审校保存失败");
    }
  }

  async function linkAuthorities() {
    if (!analysis) return;
    setPending(true);
    try {
      const updated = await api.culture.linkAuthorities(analysis.id);
      setAnalysis(updated);
      setSelectedEntity((current) =>
        current
          ? updated.entities.find((entity) => entity.id === current.id) ?? null
          : null,
      );
      const matched = updated.entities.filter(
        (entity) => entity.authority_matches.length > 0,
      ).length;
      toast.success(`权威库对齐完成 · ${matched} 个实体命中`);
    } catch (error) {
      toast.error(error instanceof ApiError ? error.message : "权威库对齐失败");
    } finally {
      setPending(false);
    }
  }

  const confirmed = analysis
    ? [...analysis.entities, ...analysis.relations].filter(
        (item) => item.status === "confirmed",
      ).length
    : 0;

  return (
    <section className="tone-culture chromatic-frame paper-surface relative rounded-[var(--radius)] border border-line p-6 md:p-10 animate-ink-rise">
      <CornerBrackets />
      <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
        <SectionMark
          icon={<IconMeridian size={18} />}
          title="史脉"
          subtitle="古籍实体抽取 · 人物关系 · 证据审校"
        />
        <div className="flex flex-wrap items-center gap-3 text-xs font-sans text-ink-mute">
          <ServiceBadge
            ready={Boolean(service?.configured)}
            label={service?.configured ? service.model : "DeepSeek"}
          />
          <ServiceBadge ready={Boolean(service?.cbdb_available)} label="CBDB" />
          <ServiceBadge ready={Boolean(service?.chgis_available)} label="CHGIS" />
        </div>
      </div>

      <div className="mt-8 grid gap-6 lg:grid-cols-[320px_minmax(0,1fr)] xl:grid-cols-[340px_minmax(0,1fr)]">
        <div className="border border-line bg-bg/40 p-5">
          <label className="text-xs font-sans tracking-[0.16em] text-ink-mute">
            篇名
          </label>
          <input
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            placeholder="可选，由模型自动判断"
            className="mt-2 h-10 w-full border-b border-line bg-transparent font-serif text-sm outline-none focus:border-accent"
          />
          <label className="mt-5 block text-xs font-sans tracking-[0.16em] text-ink-mute">
            古籍原文
          </label>
          <textarea
            value={text}
            onChange={(event) => setText(event.target.value)}
            maxLength={12000}
            className="mt-2 min-h-64 w-full resize-y border border-line bg-surface p-4 font-serif text-base leading-8 outline-none focus:border-accent"
            placeholder="粘贴古籍文本，或从古籍识读页送入 OCR 结果"
          />
          <div className="mt-3 flex items-center justify-between gap-3">
            <span className="text-[10px] font-sans tracking-wider text-ink-mute">
              {text.length} / 12000
            </span>
            <button
              type="button"
              onClick={runAnalysis}
              disabled={pending || !service?.configured}
              className={cn(
                "inline-flex h-10 items-center gap-2 bg-accent px-4 font-sans text-sm text-white transition-opacity",
                (pending || !service?.configured) &&
                  "cursor-not-allowed opacity-45",
              )}
            >
              {pending ? (
                <LoaderCircle className="h-4 w-4 animate-spin" aria-hidden />
              ) : (
                <Sparkles className="h-4 w-4" aria-hidden />
              )}
              {pending ? "分析中" : "抽取史脉"}
            </button>
          </div>

          {history.length > 0 ? (
            <div className="mt-7 border-t border-line pt-5">
              <div className="mb-3 flex items-center gap-2 text-xs font-sans tracking-wider text-ink-mute">
                <Clock3 className="h-3.5 w-3.5" aria-hidden />
                最近分析
              </div>
              <div className="space-y-1">
                {history.slice(0, 5).map((item) => (
                  <button
                    type="button"
                    key={item.id}
                    onClick={() => openHistory(item.id)}
                    className="group flex w-full items-center justify-between gap-3 border-b border-line/70 py-2 text-left"
                  >
                    <span className="min-w-0 truncate text-sm text-ink-soft group-hover:text-accent">
                      {item.title}
                    </span>
                    <span className="shrink-0 text-[10px] font-sans text-ink-mute">
                      {item.entity_count} 实体
                    </span>
                  </button>
                ))}
              </div>
            </div>
          ) : null}
        </div>

        <div className="min-w-0 border border-line">
          {analysis ? (
            <>
              <div className="flex flex-wrap items-start justify-between gap-5 border-b border-line p-5">
                <div className="min-w-[240px] flex-1">
                  <h2 className="font-serif text-xl text-ink">{analysis.title}</h2>
                  <p className="mt-2 max-w-2xl text-sm leading-7 text-ink-soft">
                    {analysis.summary}
                  </p>
                </div>
                <div className="flex flex-wrap items-center justify-end gap-5">
                  <div className="flex gap-5 font-sans text-xs text-ink-mute">
                    <Metric value={analysis.entities.length} label="实体" />
                    <Metric value={analysis.relations.length} label="关系" />
                    <Metric
                      value={
                        analysis.entities.filter(
                          (entity) => entity.authority_matches.length > 0,
                        ).length
                      }
                      label="权威命中"
                    />
                    <Metric value={confirmed} label="审校确认" />
                  </div>
                  <button
                    type="button"
                    onClick={linkAuthorities}
                    disabled={pending}
                    className="inline-flex h-9 items-center gap-2 border border-line px-3 font-sans text-xs text-ink-soft hover:border-accent hover:text-accent disabled:opacity-50"
                  >
                    <RefreshCw
                      className={cn("h-3.5 w-3.5", pending && "animate-spin")}
                      aria-hidden
                    />
                    重新对齐
                  </button>
                </div>
              </div>

              <div className="min-h-[620px]">
                <RelationGraph
                  analysis={analysis}
                  selectedEntity={selectedEntity}
                  selectedRelation={selectedRelation}
                  onEntity={(entity) => {
                    setSelectedEntity(entity);
                    setSelectedRelation(null);
                  }}
                  onRelation={(relation) => {
                    setSelectedRelation(relation);
                    setSelectedEntity(null);
                  }}
                />
                <EvidencePanel
                  analysis={analysis}
                  entity={selectedEntity}
                  relation={selectedRelation}
                  onReview={review}
                />
              </div>
              <AuthorityOverview analysis={analysis} />
            </>
          ) : (
            <div className="flex min-h-[540px] flex-col items-center justify-center px-8 text-center">
              <Network className="h-9 w-9 text-accent-gold" aria-hidden />
              <div className="mt-4 font-serif text-lg text-ink">尚无关系图谱</div>
              <p className="mt-2 max-w-md text-sm leading-7 text-ink-mute">
                输入原文后，系统将抽取人物、地点、官职、时间和事件，并保留每条关系的原文证据。
              </p>
            </div>
          )}
        </div>
      </div>

      {analysis ? (
        <div className="mt-6 grid gap-px bg-line md:grid-cols-2">
          <TextReading
            title="今译"
            icon={<FileSearch className="h-4 w-4" aria-hidden />}
            text={analysis.modern_translation}
          />
          <Timeline analysis={analysis} />
        </div>
      ) : null}
    </section>
  );
}

function Metric({ value, label }: { value: number; label: string }) {
  return (
    <div className="text-center">
      <div className="font-serif text-lg text-ink">{value}</div>
      <div className="mt-1 text-[10px] tracking-wider">{label}</div>
    </div>
  );
}

function ServiceBadge({ ready, label }: { ready: boolean; label: string }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className={cn("h-2 w-2", ready ? "bg-[#356859]" : "bg-accent")} />
      {label} {ready ? "已接入" : "未安装"}
    </span>
  );
}

function RelationGraph({
  analysis,
  selectedEntity,
  selectedRelation,
  onEntity,
  onRelation,
}: {
  analysis: CultureAnalysis;
  selectedEntity: CulturalEntity | null;
  selectedRelation: CulturalRelation | null;
  onEntity: (entity: CulturalEntity) => void;
  onRelation: (relation: CulturalRelation) => void;
}) {
  const graph = useMemo(() => {
    const degree = new Map(analysis.entities.map((entity) => [entity.id, 0]));
    analysis.relations.forEach((relation) => {
      degree.set(relation.source, (degree.get(relation.source) ?? 0) + 1);
      degree.set(relation.target, (degree.get(relation.target) ?? 0) + 1);
    });

    const sorted = [...analysis.entities].sort((left, right) => {
      const degreeDiff = (degree.get(right.id) ?? 0) - (degree.get(left.id) ?? 0);
      if (degreeDiff !== 0) return degreeDiff;
      return left.type === "person" ? -1 : right.type === "person" ? 1 : 0;
    });
    const positions = new Map<string, { x: number; y: number; ring: number }>();
    const center = { x: 480, y: 320 };
    if (sorted[0]) positions.set(sorted[0].id, { ...center, ring: 0 });

    const remaining = sorted.slice(1);
    const innerCount = Math.min(remaining.length, 8);
    remaining.forEach((entity, index) => {
      const inner = index < innerCount;
      const ringIndex = inner ? index : index - innerCount;
      const ringTotal = inner ? innerCount : Math.max(remaining.length - innerCount, 1);
      const angle =
        (ringIndex / ringTotal) * Math.PI * 2 -
        Math.PI / 2 +
        (inner ? 0 : Math.PI / Math.max(ringTotal, 2));
      const radiusX = inner ? 205 : 355;
      const radiusY = inner ? 170 : 250;
      positions.set(entity.id, {
        x: center.x + Math.cos(angle) * radiusX,
        y: center.y + Math.sin(angle) * radiusY,
        ring: inner ? 1 : 2,
      });
    });

    return { positions, degree, hubId: sorted[0]?.id };
  }, [analysis.entities, analysis.relations]);

  return (
    <div className="relative min-h-[620px] overflow-x-auto overflow-y-hidden bg-[#fbfaf7]">
      <div className="absolute left-5 top-5 z-10 flex flex-wrap gap-x-4 gap-y-2 bg-[#fbfaf7]/90 py-1 pr-2">
        {(["person", "place", "office", "time", "event"] as EntityType[]).map(
          (type) => (
            <span
              key={type}
              className="inline-flex items-center gap-1.5 text-[10px] font-sans text-ink-mute"
            >
              <span
                className="h-2.5 w-2.5"
                style={{ backgroundColor: ENTITY_COLORS[type] }}
              />
              {ENTITY_LABELS[type]}
            </span>
          ),
        )}
      </div>
      <svg
        viewBox="0 0 960 640"
        className="h-[620px] min-w-[780px] w-full xl:min-w-0"
        role="img"
        aria-label={`${analysis.title}实体关系图`}
      >
        <defs>
          <pattern id="culture-grid" width="40" height="40" patternUnits="userSpaceOnUse">
            <path
              d="M 40 0 L 0 0 0 40"
              fill="none"
              stroke="#ddd8cf"
              strokeWidth="0.7"
              opacity="0.32"
            />
          </pattern>
          <filter id="culture-node-shadow" x="-40%" y="-40%" width="180%" height="180%">
            <feDropShadow
              dx="0"
              dy="3"
              stdDeviation="5"
              floodColor="#6d6254"
              floodOpacity="0.13"
            />
          </filter>
          <marker
            id="culture-arrow"
            viewBox="0 0 10 10"
            refX="9"
            refY="5"
            markerWidth="7"
            markerHeight="7"
            orient="auto-start-reverse"
          >
            <path d="M 0 0 L 10 5 L 0 10 z" fill="#aaa49a" />
          </marker>
        </defs>
        <rect width="960" height="640" fill="url(#culture-grid)" />
        <ellipse
          cx="480"
          cy="320"
          rx="205"
          ry="170"
          fill="none"
          stroke="#d8d2c8"
          strokeWidth="1"
          strokeDasharray="3 8"
        />
        <ellipse
          cx="480"
          cy="320"
          rx="355"
          ry="250"
          fill="none"
          stroke="#e5e0d7"
          strokeWidth="1"
          strokeDasharray="3 10"
        />
        {analysis.relations.map((relation, relationIndex) => {
          const source = graph.positions.get(relation.source);
          const target = graph.positions.get(relation.target);
          if (!source || !target) return null;
          const active = selectedRelation?.id === relation.id;
          const rejected = relation.status === "rejected";
          const color =
            relation.status === "confirmed" ? "#356859" : active ? "#9a2a1f" : "#aaa49a";
          const dx = target.x - source.x;
          const dy = target.y - source.y;
          const length = Math.max(Math.hypot(dx, dy), 1);
          const curve = ((relationIndex % 3) - 1) * 18;
          const control = {
            x: (source.x + target.x) / 2 - (dy / length) * curve,
            y: (source.y + target.y) / 2 + (dx / length) * curve,
          };
          const label = {
            x: source.x * 0.25 + control.x * 0.5 + target.x * 0.25,
            y: source.y * 0.25 + control.y * 0.5 + target.y * 0.25,
          };
          const path = `M ${source.x} ${source.y} Q ${control.x} ${control.y} ${target.x} ${target.y}`;
          return (
            <g
              key={relation.id}
              onClick={() => onRelation(relation)}
              className="cursor-pointer"
              opacity={rejected ? 0.3 : 1}
            >
              <path
                d={path}
                fill="none"
                stroke="transparent"
                strokeWidth="20"
              />
              <path
                d={path}
                fill="none"
                stroke={color}
                strokeWidth={active ? 2.8 : relation.status === "confirmed" ? 2 : 1.35}
                strokeDasharray={
                  relation.status === "proposed" ? "6 5" : undefined
                }
                markerEnd="url(#culture-arrow)"
              />
              <rect
                x={label.x - relation.type.length * 7 - 7}
                y={label.y - 13}
                width={relation.type.length * 14 + 14}
                height="24"
                rx="2"
                fill="#fbfaf7"
                stroke={active ? "#9a2a1f" : "#ded9d0"}
                strokeWidth={active ? 1.2 : 0.7}
              />
              <text
                x={label.x}
                y={label.y + 3}
                textAnchor="middle"
                fill={active ? "#9a2a1f" : "#77736d"}
                fontSize="12"
              >
                {relation.type}
              </text>
            </g>
          );
        })}
        {analysis.entities.map((entity) => {
          const point = graph.positions.get(entity.id);
          if (!point) return null;
          const active = selectedEntity?.id === entity.id;
          const hub = graph.hubId === entity.id;
          const radius = hub ? 48 : point.ring === 1 ? 38 : 34;
          const confirmed = entity.status === "confirmed";
          return (
            <g
              key={entity.id}
              transform={`translate(${point.x} ${point.y})`}
              onClick={() => onEntity(entity)}
              className="cursor-pointer"
              opacity={entity.status === "rejected" ? 0.35 : 1}
              filter="url(#culture-node-shadow)"
            >
              {(active || confirmed) && (
                <circle
                  r={radius + 7}
                  fill="none"
                  stroke={active ? "#9a2a1f" : "#356859"}
                  strokeWidth="1.5"
                  strokeDasharray={active ? undefined : "3 3"}
                  opacity="0.55"
                />
              )}
              <circle
                r={radius}
                fill="#fffdf9"
                stroke={ENTITY_COLORS[entity.type]}
                strokeWidth={active ? 3 : confirmed ? 2.5 : hub ? 2.2 : 1.6}
              />
              {entity.authority_matches.length > 0 ? (
                <g transform={`translate(${radius - 5} ${-radius + 5})`}>
                  <circle r="8" fill="#356859" stroke="#fffdf9" strokeWidth="2" />
                  <path
                    d="M -3 0 L -1 3 L 4 -3"
                    fill="none"
                    stroke="white"
                    strokeWidth="1.8"
                  />
                </g>
              ) : null}
              <circle
                cy={-radius + 8}
                r="3.5"
                fill={ENTITY_COLORS[entity.type]}
              />
              <text
                textAnchor="middle"
                dominantBaseline="middle"
                fill="#1a1a1a"
                fontSize={entity.name.length > 4 ? "11" : hub ? "15" : "13"}
                fontWeight={hub ? "600" : "400"}
              >
                {entity.name.slice(0, 7)}
              </text>
              <text
                y={radius + 18}
                textAnchor="middle"
                fill="#8a8680"
                fontSize="10"
              >
                {ENTITY_LABELS[entity.type]} · {graph.degree.get(entity.id) ?? 0} 关联
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}

function EvidencePanel({
  analysis,
  entity,
  relation,
  onReview,
}: {
  analysis: CultureAnalysis;
  entity: CulturalEntity | null;
  relation: CulturalRelation | null;
  onReview: (
    kind: "entity" | "relation",
    id: string,
    status: ReviewStatus,
  ) => void;
}) {
  const item = relation ?? entity;
  if (!item) {
    return (
      <aside className="border-t border-line bg-surface p-5">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <div className="text-xs font-sans tracking-wider text-ink-mute">
            证据审校
          </div>
          <p className="text-sm leading-7 text-ink-mute">
            点击图中的实体或关系，查看原文证据并进行人工确认。
          </p>
        </div>
        <div className="mt-4 grid gap-x-6 sm:grid-cols-2 xl:grid-cols-4">
          {analysis.relations.slice(0, 8).map((candidate) => (
            <div
              key={candidate.id}
              className="flex items-center justify-between border-b border-line/70 py-2 text-xs"
            >
              <span>{candidate.type}</span>
              <StatusMark status={candidate.status} />
            </div>
          ))}
        </div>
      </aside>
    );
  }

  const isRelation = Boolean(relation);
  const source = relation
    ? analysis.entities.find((candidate) => candidate.id === relation.source)
    : null;
  const target = relation
    ? analysis.entities.find((candidate) => candidate.id === relation.target)
    : null;

  return (
    <aside className="border-t border-line bg-surface p-5">
      <div className="grid gap-6 lg:grid-cols-[minmax(220px,0.8fr)_minmax(280px,1.3fr)_220px]">
        <div>
          <div className="flex items-center justify-between gap-3">
            <div className="text-xs font-sans tracking-wider text-ink-mute">
              {isRelation ? "关系证据" : "实体证据"}
            </div>
            <StatusMark status={item.status} />
          </div>
          <div className="mt-4 font-serif text-lg text-ink">
            {relation
              ? `${source?.name ?? relation.source} · ${relation.type} · ${target?.name ?? relation.target}`
              : entity?.name}
          </div>
          {entity?.description || relation?.interpretation ? (
            <p className="mt-2 text-sm leading-6 text-ink-soft">
              {entity?.description ?? relation?.interpretation}
            </p>
          ) : null}
          {entity?.authority_matches.length ? (
            <div className="mt-4 space-y-2">
              {entity.authority_matches.map((match) => {
                const simplified =
                  match.canonical_name_simplified ?? match.canonical_name;
                const showTraditional = simplified !== match.canonical_name;
                return (
                  <div key={`${match.source}-${match.authority_id}`}>
                    <a
                      href={match.source_url}
                      target="_blank"
                      rel="noreferrer"
                      className="block border border-line bg-bg/40 p-3 outline-none hover:border-accent-gold focus-visible:border-[#356859] focus-visible:ring-1 focus-visible:ring-[#356859]"
                    >
                      <div className="flex items-center justify-between gap-3">
                        <span className="inline-flex items-center gap-1.5 text-xs font-sans text-[#356859]">
                          <Database className="h-3.5 w-3.5" aria-hidden />
                          {match.source} · {match.authority_id}
                        </span>
                        <ExternalLink className="h-3.5 w-3.5 text-ink-mute" aria-hidden />
                      </div>
                      <div className="mt-2 flex flex-wrap items-baseline gap-x-2 gap-y-1 text-sm text-ink">
                        <span>
                          {simplified}
                          {match.feature_type ? ` · ${match.feature_type}` : ""}
                        </span>
                        {showTraditional ? (
                          <span className="text-xs text-ink-mute">繁 {match.canonical_name}</span>
                        ) : null}
                        {match.name_conversion ? (
                          <ConversionBadge conv={match.name_conversion} />
                        ) : null}
                      </div>
                      <div className="mt-1 text-[11px] font-sans text-ink-mute">
                        {[match.years, match.parent_name].filter(Boolean).join(" · ") ||
                          `${Math.round(match.confidence * 100)}% 匹配`}
                      </div>
                    </a>
                    {match.name_conversion ? (
                      <ConversionEvidence conv={match.name_conversion} />
                    ) : null}
                  </div>
                );
              })}
            </div>
          ) : entity && (entity.type === "person" || entity.type === "place") ? (
            <div className="mt-4 text-xs font-sans text-ink-mute">
              未在 {entity.type === "person" ? "CBDB" : "CHGIS"} 中找到可确认记录
            </div>
          ) : null}
        </div>
        <div className="border-l-2 border-accent-gold pl-4">
          <div className="text-[10px] font-sans tracking-wider text-ink-mute">
            原文依据
          </div>
          <blockquote className="mt-2 font-serif text-sm leading-7 text-ink">
            {item.evidence || "模型未返回可核验的直接证据"}
          </blockquote>
        </div>
        <div>
          <div className="space-y-2 text-xs font-sans text-ink-mute">
            <div className="flex justify-between">
              <span>证据置信度</span>
              <span>{Math.round(item.confidence * 100)}%</span>
            </div>
            {relation?.time ? (
              <div className="flex justify-between gap-3">
                <span>时间</span>
                <span className="text-right text-ink-soft">{relation.time}</span>
              </div>
            ) : null}
            {relation?.place ? (
              <div className="flex justify-between gap-3">
                <span>地点</span>
                <span className="text-right text-ink-soft">{relation.place}</span>
              </div>
            ) : null}
          </div>
          <div className="mt-5 grid grid-cols-2 gap-2">
            <button
              type="button"
              onClick={() =>
                onReview(isRelation ? "relation" : "entity", item.id, "confirmed")
              }
              className="inline-flex h-9 items-center justify-center gap-1.5 border border-[#356859] font-sans text-xs text-[#356859] hover:bg-[#356859] hover:text-white"
            >
              <Check className="h-3.5 w-3.5" aria-hidden />
              确认
            </button>
            <button
              type="button"
              onClick={() =>
                onReview(isRelation ? "relation" : "entity", item.id, "rejected")
              }
              className="inline-flex h-9 items-center justify-center gap-1.5 border border-accent font-sans text-xs text-accent hover:bg-accent hover:text-white"
            >
              <X className="h-3.5 w-3.5" aria-hidden />
              驳回
            </button>
          </div>
        </div>
      </div>
    </aside>
  );
}

const CONV_METHOD_LABEL: Record<string, string> = {
  word: "整词",
  char: "逐字",
  mixed: "混合",
  identity: "原形",
};
const CONV_SOURCE_LABEL: Record<string, string> = {
  "cc-cedict": "CC-CEDICT",
  opencc: "OpenCC",
  unihan: "Unihan",
  chise: "CHISE",
};

function conversionHasConflict(conv: NameConversion): boolean {
  return conv.segments.some((seg) => seg.conflict);
}

// Small badge: 繁→简 method + confidence; amber when sources disagree.
function ConversionBadge({
  conv,
  className,
}: {
  conv: NameConversion;
  className?: string;
}) {
  const conflict = conversionHasConflict(conv);
  return (
    <span
      title={conflict ? "不同字库给出不同简体，存在分歧" : "多源字库一致"}
      className={cn(
        "inline-flex items-center rounded-sm px-1.5 py-px text-[10px] font-sans",
        conflict ? "bg-accent/10 text-accent" : "bg-[#356859]/12 text-[#356859]",
        className,
      )}
    >
      {CONV_METHOD_LABEL[conv.method] ?? conv.method} ·{" "}
      {Math.round(conv.confidence * 100)}%{conflict ? " · 存疑" : ""}
    </span>
  );
}

// Per-segment multi-source evidence (collapsible). MUST live outside any <a>.
function ConversionEvidence({ conv }: { conv: NameConversion }) {
  const segments = conv.segments.filter(
    (seg) => seg.method !== "identity" || seg.conflict,
  );
  if (!segments.length) return null;
  return (
    <details className="mt-1.5">
      <summary className="cursor-pointer text-[10px] font-sans text-ink-mute hover:text-accent">
        多源转换依据
      </summary>
      <div className="mt-1 space-y-1 border-l border-line/70 pl-2">
        {segments.map((seg, index) => (
          <div key={`${seg.traditional}-${index}`} className="text-[10px] font-sans leading-5">
            <span className="text-ink">
              {seg.traditional} → {seg.simplified}
            </span>
            <span className="text-ink-mute">
              {" · "}
              {seg.sources.map((s) => CONV_SOURCE_LABEL[s] ?? s).join(" + ") || "—"}
            </span>
            {seg.conflict && seg.alternatives.length ? (
              <span className="text-accent">
                {" · 候选 "}
                {seg.alternatives.join(" / ")}
              </span>
            ) : null}
          </div>
        ))}
      </div>
    </details>
  );
}

function AuthorityOverview({ analysis }: { analysis: CultureAnalysis }) {
  const matched = analysis.entities.filter(
    (entity) => entity.authority_matches.length > 0,
  );
  const places = matched.flatMap((entity) =>
    entity.authority_matches
      .filter(
        (match) =>
          match.source === "CHGIS" &&
          match.longitude != null &&
          match.latitude != null,
      )
      .slice(0, 1)
      .map((match) => ({ entity, match })),
  );
  if (!matched.length) return null;

  return (
    <div className="grid gap-px border-t border-line bg-line lg:grid-cols-[0.9fr_1.1fr]">
      <article className="bg-surface p-6">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2 text-xs font-sans tracking-wider text-ink-mute">
            <Database className="h-4 w-4" aria-hidden />
            权威库对齐
          </div>
          <span className="text-[10px] font-sans text-ink-mute">
            {matched.length} / {analysis.entities.length} 实体命中
          </span>
        </div>
        <div className="mt-4 divide-y divide-line/70 border-y border-line/70">
          {matched.map((entity) => {
            const match = entity.authority_matches[0];
            return (
              <a
                key={entity.id}
                href={match.source_url}
                target="_blank"
                rel="noreferrer"
                className="grid grid-cols-[minmax(76px,0.7fr)_minmax(110px,1fr)_auto] items-center gap-3 py-3 outline-none hover:text-accent focus-visible:bg-bg"
              >
                <span className="min-w-0">
                  <span className="block truncate text-sm text-ink">
                    {entity.name}
                  </span>
                  {match.canonical_name !== entity.name ? (
                    <span className="mt-0.5 block truncate text-[10px] font-sans text-ink-mute">
                      规范名 {match.canonical_name_simplified ?? match.canonical_name}
                      {match.canonical_name_simplified &&
                      match.canonical_name_simplified !== match.canonical_name
                        ? ` · 繁 ${match.canonical_name}`
                        : ""}
                    </span>
                  ) : null}
                </span>
                <span className="min-w-0 text-[10px] font-sans text-ink-mute">
                  <span className="block truncate">
                    {match.years ?? match.parent_name ?? "年代未载"}
                  </span>
                  <span className="mt-0.5 block truncate">
                    {match.match_type === "exact" ? "精确匹配" : "异名匹配"} ·{" "}
                    {Math.round(match.confidence * 100)}%
                  </span>
                </span>
                <span className="inline-flex items-center gap-1 text-[10px] font-sans text-[#356859]">
                  {match.source} {match.authority_id}
                  <ExternalLink className="h-3 w-3" aria-hidden />
                </span>
              </a>
            );
          })}
        </div>
      </article>
      <article className="bg-surface p-6">
        <div className="flex items-center gap-2 text-xs font-sans tracking-wider text-ink-mute">
          <MapPin className="h-4 w-4" aria-hidden />
          CHGIS 历史地点
        </div>
        {places.length ? (
          <HistoricalPlaceMap places={places} />
        ) : (
          <p className="mt-4 text-sm text-ink-mute">本段没有带坐标的 CHGIS 匹配。</p>
        )}
      </article>
    </div>
  );
}

function HistoricalPlaceMap({
  places,
}: {
  places: Array<{
    entity: CulturalEntity;
    match: CulturalEntity["authority_matches"][number];
  }>;
}) {
  const longitudes = places.map((item) => item.match.longitude as number);
  const latitudes = places.map((item) => item.match.latitude as number);
  const minLongitude = Math.min(...longitudes);
  const maxLongitude = Math.max(...longitudes);
  const minLatitude = Math.min(...latitudes);
  const maxLatitude = Math.max(...latitudes);
  const singlePoint = places.length === 1;
  const x = (value: number) =>
    singlePoint
      ? 250
      : 72 +
        ((value - minLongitude) / Math.max(maxLongitude - minLongitude, 1)) * 350;
  const y = (value: number) =>
    singlePoint
      ? 105
      : 166 -
        ((value - minLatitude) / Math.max(maxLatitude - minLatitude, 1)) * 112;
  const plotted = places.map((item) => ({
    ...item,
    x: x(item.match.longitude as number),
    y: y(item.match.latitude as number),
  }));
  const longitudeLabels = singlePoint
    ? [minLongitude]
    : [minLongitude, (minLongitude + maxLongitude) / 2, maxLongitude];
  const latitudeLabels = singlePoint
    ? [minLatitude]
    : [minLatitude, (minLatitude + maxLatitude) / 2, maxLatitude];

  return (
    <svg
      viewBox="0 0 500 210"
      className="mt-3 h-52 w-full border border-line bg-[#fbfaf7]"
      role="img"
      aria-label="CHGIS历史地点分布"
    >
      {[54, 110, 166].map((lineY) => (
        <line
          key={`horizontal-${lineY}`}
          x1="58"
          y1={lineY}
          x2="442"
          y2={lineY}
          stroke="#e3ded5"
          strokeWidth="1"
          strokeDasharray="3 5"
        />
      ))}
      {[72, 247, 422].map((lineX) => (
        <line
          key={`vertical-${lineX}`}
          x1={lineX}
          y1="38"
          x2={lineX}
          y2="180"
          stroke="#e3ded5"
          strokeWidth="1"
          strokeDasharray="3 5"
        />
      ))}
      {plotted.length > 1 ? (
        <polyline
          points={plotted.map((point) => `${point.x},${point.y}`).join(" ")}
          fill="none"
          stroke="#8aa99e"
          strokeWidth="1.5"
          strokeDasharray="4 5"
        />
      ) : null}
      {longitudeLabels.map((value, index) => (
        <text
          key={`longitude-${value}`}
          x={singlePoint ? 250 : [72, 247, 422][index]}
          y="198"
          textAnchor="middle"
          fontSize="8"
          fill="#9a958d"
        >
          {value.toFixed(1)}°E
        </text>
      ))}
      {latitudeLabels.map((value, index) => (
        <text
          key={`latitude-${value}`}
          x="50"
          y={(singlePoint ? 105 : [166, 110, 54][index]) + 3}
          textAnchor="end"
          fontSize="8"
          fill="#9a958d"
        >
          {value.toFixed(1)}°N
        </text>
      ))}
      {plotted.map(({ entity, match, x: pointX, y: pointY }, index) => {
        const labelOnLeft = pointX > 335;
        const labelX = labelOnLeft ? -10 : 10;
        return (
        <g
          key={`${entity.id}-${match.authority_id}`}
          transform={`translate(${pointX} ${pointY})`}
        >
          <circle r="10" fill="#fffdf9" stroke="#356859" strokeWidth="1.5" />
          <text
            y="3"
            textAnchor="middle"
            fontSize="8"
            fontFamily="sans-serif"
            fill="#356859"
          >
            {index + 1}
          </text>
          <text
            x={labelX}
            y="-2"
            textAnchor={labelOnLeft ? "end" : "start"}
            fontSize="11"
            fill="#1a1a1a"
          >
            {entity.name}
          </text>
          <text
            x={labelX}
            y="12"
            textAnchor={labelOnLeft ? "end" : "start"}
            fontSize="8"
            fill="#8a8680"
          >
            {match.years ?? match.authority_id}
          </text>
        </g>
        );
      })}
    </svg>
  );
}

function StatusMark({ status }: { status: ReviewStatus }) {
  const copy = {
    proposed: "待审",
    confirmed: "已确认",
    rejected: "已驳回",
  }[status];
  return (
    <span
      className={cn(
        "text-[10px] font-sans tracking-wider",
        status === "confirmed" && "text-[#356859]",
        status === "rejected" && "text-accent",
        status === "proposed" && "text-ink-mute",
      )}
    >
      {copy}
    </span>
  );
}

function TextReading({
  title,
  icon,
  text,
}: {
  title: string;
  icon: React.ReactNode;
  text: string;
}) {
  return (
    <article className="bg-surface p-6">
      <div className="flex items-center gap-2 text-xs font-sans tracking-wider text-ink-mute">
        {icon}
        {title}
      </div>
      <p className="mt-4 whitespace-pre-wrap font-serif text-sm leading-8 text-ink-soft">
        {text}
      </p>
    </article>
  );
}

function Timeline({ analysis }: { analysis: CultureAnalysis }) {
  const timedRelations = analysis.relations.filter((relation) => relation.time);
  return (
    <article className="bg-surface p-6">
      <div className="flex items-center gap-2 text-xs font-sans tracking-wider text-ink-mute">
        <Clock3 className="h-4 w-4" aria-hidden />
        文本时间线
      </div>
      {timedRelations.length ? (
        <div className="mt-4 space-y-4">
          {timedRelations.map((relation) => {
            const source = analysis.entities.find(
              (entity) => entity.id === relation.source,
            );
            const target = analysis.entities.find(
              (entity) => entity.id === relation.target,
            );
            return (
              <div key={relation.id} className="flex gap-3">
                <div className="mt-1.5 h-2 w-2 shrink-0 bg-accent" />
                <div>
                  <div className="text-xs font-sans text-accent">
                    {relation.time}
                  </div>
                  <div className="mt-1 flex flex-wrap items-center gap-1 text-sm text-ink-soft">
                    <span>{source?.name}</span>
                    <ChevronRight className="h-3 w-3" aria-hidden />
                    <span>{relation.type}</span>
                    <ChevronRight className="h-3 w-3" aria-hidden />
                    <span>{target?.name}</span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <div className="mt-5 flex items-center gap-2 text-sm text-ink-mute">
          <RotateCcw className="h-4 w-4" aria-hidden />
          本段未抽取到明确时间关系
        </div>
      )}
    </article>
  );
}
