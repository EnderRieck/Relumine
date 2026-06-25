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
  // 逐字（按码点）识别置信度；仅本地 PaddleOCR-VL 提供，其余后端为 null。
  char_confidences?: number[] | null;
  // { 码点位置: [模型 top-k 备选字…] }
  alternatives?: Record<string, string[]> | null;
};

export type ProofreadCategory =
  | "形近"
  | "文义"
  | "缺漏"
  | "衍文"
  | "其他"
  | "低置信";

export type ProofreadCandidate = {
  char: string;
  source: "confusable" | "ocr" | "context";
};

export type ProofreadRisk = {
  position: number;
  original: string;
  snippet: string;
  candidates: ProofreadCandidate[];
  confidence: number;
  ocr_confidence?: number | null;
  reason: string;
  category: ProofreadCategory;
};

export type ProofreadResult = {
  text: string;
  risks: ProofreadRisk[];
  model: string;
  note?: string | null;
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
  database_radar?: {
    scale: number;
    thesis: string;
    axes: Array<{
      key: string;
      label: string;
      description: string;
    }>;
    databases: Array<{
      name: string;
      role: string;
      record_count: number;
      unique_chars: number;
      scores: Record<string, number>;
      strength: string;
      limitation: string;
      derived_from?: string[];
    }>;
    contributions: Array<{
      source: string;
      provides: string;
      used_for: string;
      relumine_value: string;
    }>;
  };
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

export type EntityType =
  | "person"
  | "place"
  | "office"
  | "time"
  | "event"
  | "work"
  | "organization"
  | "other";

export type ReviewStatus = "proposed" | "confirmed" | "rejected";

export type CulturalEntity = {
  id: string;
  name: string;
  normalized_name?: string | null;
  type: EntityType;
  aliases: string[];
  description?: string | null;
  confidence: number;
  evidence: string;
  status: ReviewStatus;
  authority_matches: AuthorityMatch[];
};

export type ConvertEvidence = {
  source: string;
  value?: string | null;
  note?: string | null;
};

export type ConvertSegment = {
  traditional: string;
  simplified: string;
  method: "word" | "char" | "identity";
  confidence: number;
  sources: string[];
  conflict: boolean;
  alternatives: string[];
  evidence: ConvertEvidence[];
};

export type NameConversion = {
  traditional: string;
  simplified: string;
  confidence: number;
  method: "word" | "char" | "mixed" | "identity";
  segments: ConvertSegment[];
  note?: string | null;
};

export type AuthorityMatch = {
  source: "CBDB" | "CHGIS";
  authority_id: string;
  canonical_name: string;
  canonical_name_simplified?: string | null;
  name_conversion?: NameConversion | null;
  match_type: "exact" | "alias" | "prefix";
  confidence: number;
  source_url: string;
  label?: string | null;
  years?: string | null;
  parent_name?: string | null;
  feature_type?: string | null;
  longitude?: number | null;
  latitude?: number | null;
  metadata: Record<string, unknown>;
};

export type CulturalRelation = {
  id: string;
  source: string;
  target: string;
  type: string;
  evidence: string;
  confidence: number;
  time?: string | null;
  place?: string | null;
  interpretation?: string | null;
  status: ReviewStatus;
};

export type CultureAnalysis = {
  id: string;
  title: string;
  source_text: string;
  summary: string;
  modern_translation: string;
  entities: CulturalEntity[];
  relations: CulturalRelation[];
  model: string;
  created_at: string;
};

export type CultureAnalysisSummary = {
  id: string;
  title: string;
  summary: string;
  entity_count: number;
  relation_count: number;
  created_at: string;
};

export type CultureStatus = {
  configured: boolean;
  model: string;
  cbdb_available: boolean;
  chgis_available: boolean;
};
