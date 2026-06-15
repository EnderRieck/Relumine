from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


# ---------- convert ----------

class Collision(BaseModel):
    position: int
    simplified: str
    source_traditionals: list[str]


class ConvertRequest(BaseModel):
    text: str = Field(..., max_length=20000)
    direction: Literal["t2s", "s2t"] = "t2s"


class ConvertResponse(BaseModel):
    result: str
    direction: Literal["t2s", "s2t"]
    collisions: list[Collision]


# ---------- ocr ----------

class OcrResponse(BaseModel):
    text: str
    char_count: int
    latency_ms: int


class OcrQueueStatus(BaseModel):
    depth: int


# ---------- evolution ----------

class Stage(BaseModel):
    era: str
    form: str
    image: str | None = None
    note: str | None = None


class CharSummary(BaseModel):
    simplified: str
    traditional: str
    pinyin: str | None = None
    record_type: str | None = None  # "merge" | "one_to_one"
    curation_level: str | None = None  # "handcrafted" | "auto_external" | "auto_slim"
    radical: str | None = None
    simp_strokes: int | None = None
    trad_strokes: int | None = None
    stroke_reduction: int | None = None
    frequency: int = 0
    frequency_tier: str | None = None
    display_tier: str | None = None  # "grid" | "archive"
    ocr_risk_level: str | None = None
    ocr_risk_score: int | None = None
    semantic_level: str | None = None
    avg_stroke_reduction: float | None = None
    coverage_count: int = 0
    merges: str | None = None  # space-joined traditional source chars


class CharRecord(BaseModel):
    simplified: str
    traditional: str
    pinyin: str | None = None
    stages: list[Stage] = []
    merges: list[str] = []
    notes: str | None = None
    extensions: dict = {}


# ---------- health ----------

class HealthResponse(BaseModel):
    ok: bool
    model_loaded: bool
    version: str


# ---------- cultural graph ----------

EntityType = Literal[
    "person",
    "place",
    "office",
    "time",
    "event",
    "work",
    "organization",
    "other",
]
ReviewStatus = Literal["proposed", "confirmed", "rejected"]


class AuthorityMatch(BaseModel):
    source: Literal["CBDB", "CHGIS"]
    authority_id: str
    canonical_name: str
    match_type: Literal["exact", "alias", "prefix"]
    confidence: float = Field(ge=0, le=1)
    source_url: str
    label: str | None = None
    years: str | None = None
    parent_name: str | None = None
    feature_type: str | None = None
    longitude: float | None = None
    latitude: float | None = None
    metadata: dict = Field(default_factory=dict)


class CulturalEntity(BaseModel):
    id: str
    name: str
    normalized_name: str | None = None
    type: EntityType
    aliases: list[str] = Field(default_factory=list)
    description: str | None = None
    confidence: float = Field(default=0.5, ge=0, le=1)
    evidence: str
    status: ReviewStatus = "proposed"
    authority_matches: list[AuthorityMatch] = Field(default_factory=list)


class CulturalRelation(BaseModel):
    id: str
    source: str
    target: str
    type: str
    evidence: str
    confidence: float = Field(default=0.5, ge=0, le=1)
    time: str | None = None
    place: str | None = None
    interpretation: str | None = None
    status: ReviewStatus = "proposed"


class CultureAnalyzeRequest(BaseModel):
    text: str = Field(..., min_length=2, max_length=12000)
    title: str | None = Field(default=None, max_length=120)


class CultureAnalysis(BaseModel):
    id: str
    title: str
    source_text: str
    summary: str
    modern_translation: str
    entities: list[CulturalEntity]
    relations: list[CulturalRelation]
    model: str
    created_at: str


class CultureAnalysisSummary(BaseModel):
    id: str
    title: str
    summary: str
    entity_count: int
    relation_count: int
    created_at: str


class CultureReviewRequest(BaseModel):
    entity_statuses: dict[str, ReviewStatus] = Field(default_factory=dict)
    relation_statuses: dict[str, ReviewStatus] = Field(default_factory=dict)


class CultureStatusResponse(BaseModel):
    configured: bool
    model: str
    cbdb_available: bool = False
    chgis_available: bool = False
