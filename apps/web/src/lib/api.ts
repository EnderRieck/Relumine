import type {
  CharRecord,
  CharSummary,
  CultureAnalysis,
  CultureAnalysisSummary,
  CultureStatus,
  ConvertResponse,
  Direction,
  HealthResponse,
  OcrResponse,
  ReviewStatus,
} from "@/lib/types";

class ApiError extends Error {
  status: number;
  body?: unknown;
  constructor(message: string, status: number, body?: unknown) {
    super(message);
    this.status = status;
    this.body = body;
  }
}

async function jsonOrThrow<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let body: unknown;
    try {
      body = await res.json();
    } catch {
      body = await res.text().catch(() => "");
    }
    const detail =
      typeof body === "object" && body && "detail" in body
        ? String((body as { detail: unknown }).detail)
        : res.statusText;
    throw new ApiError(detail, res.status, body);
  }
  return res.json() as Promise<T>;
}

export const api = {
  async health(): Promise<HealthResponse> {
    return jsonOrThrow<HealthResponse>(await fetch("/api/healthz", { cache: "no-store" }));
  },

  async convert(text: string, direction: Direction): Promise<ConvertResponse> {
    return jsonOrThrow<ConvertResponse>(
      await fetch("/api/convert", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, direction }),
      }),
    );
  },

  async ocr(file: File): Promise<OcrResponse> {
    const fd = new FormData();
    fd.append("file", file);
    return jsonOrThrow<OcrResponse>(
      await fetch("/api/ocr", { method: "POST", body: fd }),
    );
  },

  async ocrQueue(): Promise<{ depth: number }> {
    return jsonOrThrow<{ depth: number }>(
      await fetch("/api/ocr/queue", { cache: "no-store" }),
    );
  },

  evolution: {
    async list(params?: { type?: "merge" | "one_to_one"; tier?: "grid" | "archive" }): Promise<CharSummary[]> {
      const search = new URLSearchParams();
      if (params?.type) search.set("type", params.type);
      if (params?.tier) search.set("tier", params.tier);
      const qs = search.toString();
      return jsonOrThrow<CharSummary[]>(
        await fetch(`/api/evolution${qs ? `?${qs}` : ""}`, { cache: "no-store" }),
      );
    },
    async stats(): Promise<import("@/lib/types").EvolutionStats> {
      return jsonOrThrow<import("@/lib/types").EvolutionStats>(
        await fetch("/api/evolution/stats", { cache: "no-store" }),
      );
    },
    async clAnalysis(): Promise<import("@/lib/types").ClAnalysis> {
      return jsonOrThrow<import("@/lib/types").ClAnalysis>(
        await fetch("/api/evolution/cl-analysis", { cache: "no-store" }),
      );
    },
    async get(char: string): Promise<CharRecord> {
      return jsonOrThrow<CharRecord>(
        await fetch(`/api/evolution/${encodeURIComponent(char)}`, { cache: "no-store" }),
      );
    },
  },

  culture: {
    async status(): Promise<CultureStatus> {
      return jsonOrThrow<CultureStatus>(
        await fetch("/api/culture/status", { cache: "no-store" }),
      );
    },
    async analyze(text: string, title?: string): Promise<CultureAnalysis> {
      return jsonOrThrow<CultureAnalysis>(
        await fetch("/api/culture/analyze", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text, title: title || null }),
        }),
      );
    },
    async list(): Promise<CultureAnalysisSummary[]> {
      return jsonOrThrow<CultureAnalysisSummary[]>(
        await fetch("/api/culture/analyses", { cache: "no-store" }),
      );
    },
    async get(id: string): Promise<CultureAnalysis> {
      return jsonOrThrow<CultureAnalysis>(
        await fetch(`/api/culture/analyses/${encodeURIComponent(id)}`, {
          cache: "no-store",
        }),
      );
    },
    async review(
      id: string,
      changes: {
        entity_statuses?: Record<string, ReviewStatus>;
        relation_statuses?: Record<string, ReviewStatus>;
      },
    ): Promise<CultureAnalysis> {
      return jsonOrThrow<CultureAnalysis>(
        await fetch(`/api/culture/analyses/${encodeURIComponent(id)}/review`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            entity_statuses: changes.entity_statuses ?? {},
            relation_statuses: changes.relation_statuses ?? {},
          }),
        }),
      );
    },
  },
};

export { ApiError };
