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
