export type Direction = "t2s" | "s2t";

export type Collision = {
  position: number;
  simplified: string;
  source_traditionals: string[];
};

export type ConvertResponse = {
  result: string;
  direction: Direction;
  collisions: Collision[];
};

export type OcrResponse = {
  text: string;
  char_count: number;
  latency_ms: number;
};

export type Stage = {
  era: string;
  form: string;
  image?: string | null;
  note?: string | null;
};

export type CharSummary = {
  simplified: string;
  traditional: string;
  pinyin?: string | null;
};

export type CharRecord = {
  simplified: string;
  traditional: string;
  pinyin?: string | null;
  stages: Stage[];
  merges: string[];
  notes?: string | null;
  extensions: Record<string, unknown>;
};

export type HealthResponse = {
  ok: boolean;
  model_loaded: boolean;
  version: string;
};
