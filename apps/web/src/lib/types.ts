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
  record_type?: "merge" | "one_to_one" | null;
  curation_level?: "handcrafted" | "auto_external" | "auto_slim" | string | null;
  radical?: string | null;
  simp_strokes?: number | null;
  trad_strokes?: number | null;
  stroke_reduction?: number | null;
  frequency?: number;
  frequency_tier?: string | null;
  display_tier?: "grid" | "archive" | string | null;
  ocr_risk_level?: string | null;
  ocr_risk_score?: number | null;
  semantic_level?: string | null;
  avg_stroke_reduction?: number | null;
  coverage_count?: number;
  merges?: string | null;
};

export type ReductionSummary = {
  char_count: number;
  with_strokes: number;
  mean: number;
  median: number;
  max: number;
  min: number;
  buckets: Record<string, number>;
};

export type ClAnalysis = {
  stroke_reduction: { full: ReductionSummary; curated: ReductionSummary };
  least_effort: {
    char_count: number;
    pearson_logfreq: number;
    spearman: number;
    deciles: Array<{
      decile: number;
      freq_range: [number, number];
      mean_reduction: number;
      char_count: number;
    }>;
    note?: string;
  };
  homophony: {
    group_count: number;
    distribution: Record<string, number>;
    examples: Record<string, Array<{ simplified: string; sources: string[] }>>;
    note?: string;
  };
  ocr_confusion: {
    glyphs_with_ids: number;
    pair_count: number;
    top_pairs: Array<{
      a: string;
      b: string;
      a_simplified: string;
      b_simplified: string;
      similarity: number;
      strokes: [number, number];
      shared_components: string[];
    }>;
    note?: string;
  };
};

export type EvolutionStats = {
  total: number;
  grid_count?: number;
  archive_count?: number;
  merge_count: number;
  one_to_one_count: number;
  handcrafted_count?: number;
  auto_external_count?: number;
  auto_slim_count?: number;
  high_ocr_risk_count?: number;
  high_semantic_count?: number;
  high_frequency_count?: number;
  avg_stroke_reduction?: number;
  radical_groups?: Array<{ radical: string; count: number }>;
  stroke_reduction_buckets?: Record<string, number>;
  frequency_tiers?: Record<string, number>;
};

export type UnihanProfile = {
  char?: string;
  codepoint?: string;
  mandarin?: string | null;
  definition?: string | null;
  total_strokes?: string | null;
  radical_stroke?: string | null;
  traditional_variants?: string[];
  simplified_variants?: string[];
};

export type CedictExample = {
  traditional: string;
  simplified: string;
  pinyin?: string | null;
  definition?: string | null;
};

export type TraditionalSource = {
  char: string;
  codepoint?: string;
  role?: string;
  unihan?: UnihanProfile;
  chise_ids?: string | null;
  cc_cedict?: {
    aligned_pair_count?: number;
    examples?: CedictExample[];
  };
};

export type CulturalComputation = {
  semantic_ambiguity?: {
    level?: string;
    source_count?: number;
    distinct_meaning_count?: number;
    meanings?: Array<{
      char: string;
      meaning: string;
    }>;
    note?: string;
  };
  component_shift?: {
    traditional_components?: string[];
    simplified_components?: string[];
    removed_components?: string[];
    added_components?: string[];
    shared_components?: string[];
    change_count?: number;
  };
  ocr_risk?: {
    level?: string;
    score?: number;
    reasons?: string[];
  };
  frequency_profile?: {
    cc_cedict_occurrences?: number;
    rank_in_database?: number;
    tier?: string;
  };
  stroke_profile?: {
    average_reduction?: number;
    max_reduction?: number;
    pair_count?: number;
  };
  cultural_tags?: string[];
};

export type CharExtensions = {
  curation_level?: "handcrafted" | "auto_external" | string;
  record_type?: string;
  codepoint?: string;
  canonical_traditional?: string;
  simplification_types?: string[];
  external_profile?: {
    unihan?: UnihanProfile;
    chise_ids?: string | null;
    opencc_simplified_to_traditional?: string[];
    cc_cedict_as_simplified_occurrences?: number;
    cc_cedict_as_traditional_occurrences?: number;
  };
  traditional_sources?: TraditionalSource[];
  cultural_computation?: CulturalComputation;
  coverage?: Record<string, boolean>;
  excluded_sources?: string[];
  requires_historical_review?: boolean;
  merge_diagram?: string;
};

export type CharRecord = {
  simplified: string;
  traditional: string;
  pinyin?: string | null;
  stages: Stage[];
  merges: string[];
  notes?: string | null;
  extensions: CharExtensions;
};

export type HealthResponse = {
  ok: boolean;
  model_loaded: boolean;
  version: string;
};
