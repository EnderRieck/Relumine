from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import closing
from pathlib import Path
from typing import Protocol

from ocrforge_web.schemas import CharRecord, CharSummary


class EvolutionRepository(Protocol):
    def list_characters(
        self, record_type: str | None = None, tier: str | None = None
    ) -> list[CharSummary]: ...
    def get(self, char: str) -> CharRecord | None: ...
    def stats(self) -> dict: ...


class JsonEvolutionRepo:
    def __init__(self, path: Path) -> None:
        self._path = Path(path)
        self._lock = threading.Lock()
        self._mtime: float = -1.0
        self._records: dict[str, CharRecord] = {}
        self._order: list[str] = []
        self._reload_if_stale()

    def _reload_if_stale(self) -> None:
        with self._lock:
            try:
                current = self._path.stat().st_mtime
            except FileNotFoundError:
                if self._mtime != -1.0:
                    self._records = {}
                    self._order = []
                    self._mtime = -1.0
                return

            if current == self._mtime:
                return

            data = json.loads(self._path.read_text(encoding="utf-8"))
            records: dict[str, CharRecord] = {}
            order: list[str] = []
            for raw in _iter_records(data):
                rec = CharRecord.model_validate(_to_char_record(raw))
                key = rec.simplified
                records[key] = rec
                if key not in order:
                    order.append(key)
            self._records = records
            self._order = order
            self._mtime = current

    def list_characters(
        self, record_type: str | None = None, tier: str | None = None
    ) -> list[CharSummary]:
        self._reload_if_stale()
        out = []
        for k in self._order:
            rec = self._records[k]
            merges = [ch for ch in rec.merges if ch != rec.simplified]
            rec_type = "merge" if len(merges) > 1 else "one_to_one"
            if record_type and rec_type != record_type:
                continue
            out.append(
                CharSummary(
                    simplified=rec.simplified,
                    traditional=rec.traditional,
                    pinyin=rec.pinyin,
                    record_type=rec_type,
                    curation_level=rec.extensions.get("curation_level"),
                    merges=" ".join(merges),
                )
            )
        return out

    def get(self, char: str) -> CharRecord | None:
        self._reload_if_stale()
        return self._records.get(char)

    def stats(self) -> dict:
        self._reload_if_stale()
        summaries = self.list_characters()
        return {
            "total": len(summaries),
            "merge_count": sum(1 for item in summaries if item.record_type == "merge"),
            "one_to_one_count": sum(1 for item in summaries if item.record_type == "one_to_one"),
        }


def _iter_records(data: object) -> list[dict]:
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict) and isinstance(data.get("characters"), list):
        return [item for item in data["characters"] if isinstance(item, dict)]
    raise ValueError("evolution data must be a list or an object with a characters list")


def _to_char_record(raw: dict) -> dict:
    if "traditional" in raw and "stages" in raw:
        return raw

    project = raw.get("project_interpretation") or {}
    external = raw.get("external_profile") or {}
    coverage = raw.get("coverage") or {}
    sources = raw.get("traditional_sources") or []
    traditional = raw.get("canonical_traditional") or ""
    simplified = raw.get("simplified") or ""

    extensions = dict(project.get("extensions") or {})
    extensions.update(
        {
            "database_id": raw.get("id"),
            "curation_level": raw.get("curation_level"),
            "record_type": raw.get("record_type"),
            "codepoint": raw.get("codepoint"),
            "canonical_traditional": traditional,
            "simplification_types": raw.get("simplification_types") or [],
            "external_profile": external,
            "traditional_sources": sources,
            "cultural_computation": raw.get("cultural_computation"),
            "coverage": coverage,
        }
    )

    return {
        "simplified": simplified,
        "traditional": traditional,
        "pinyin": raw.get("pinyin"),
        "stages": project.get("stages") or [],
        "merges": project.get("merges") or [item.get("char") for item in sources if item.get("char")],
        "notes": project.get("notes"),
        "extensions": extensions,
    }


_SUMMARY_COLUMNS = (
    "simplified, traditional, pinyin, record_type, curation_level, radical, "
    "simp_strokes, trad_strokes, stroke_reduction, frequency, frequency_tier, "
    "display_tier, ocr_risk_level, ocr_risk_score, semantic_level, "
    "avg_stroke_reduction, coverage_count, merges"
)


class SqliteEvolutionRepo:
    """Read-only repo over the SQLite file generated by build_relumine_database.py.

    Tables: char_summary (slim list fields), char_detail (full record JSON),
    meta (precomputed stats under key 'stats').
    """

    def __init__(self, path: Path) -> None:
        self._path = Path(path)
        if not self._path.exists():
            raise FileNotFoundError(
                f"evolution sqlite database not found: {self._path}. "
                "Run analysis/hanzi_databases/scripts/build_relumine_database.py first."
            )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(f"file:{self._path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        return conn

    def list_characters(
        self, record_type: str | None = None, tier: str | None = None
    ) -> list[CharSummary]:
        query = f"SELECT {_SUMMARY_COLUMNS} FROM char_summary"
        clauses, params = [], []
        if record_type:
            clauses.append("record_type = ?")
            params.append(record_type)
        if tier:
            clauses.append("display_tier = ?")
            params.append(tier)
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY sort_order"
        with closing(self._connect()) as conn:
            rows = conn.execute(query, params).fetchall()
        return [CharSummary(**dict(row)) for row in rows]

    def get(self, char: str) -> CharRecord | None:
        with closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT record_json FROM char_detail WHERE simplified = ?", (char,)
            ).fetchone()
        if row is None:
            return None
        return CharRecord.model_validate(_to_char_record(json.loads(row["record_json"])))

    def stats(self) -> dict:
        with closing(self._connect()) as conn:
            row = conn.execute("SELECT value FROM meta WHERE key = 'stats'").fetchone()
        return json.loads(row["value"]) if row else {}


_REPO: EvolutionRepository | None = None
_REPO_LOCK = threading.Lock()


def get_repo() -> EvolutionRepository:
    from ocrforge_web.settings import get_settings

    global _REPO
    if _REPO is not None:
        return _REPO
    with _REPO_LOCK:
        if _REPO is not None:
            return _REPO
        settings = get_settings()
        backend = settings.evolution_backend.lower()
        if backend == "json":
            _REPO = JsonEvolutionRepo(settings.evolution_path)
        elif backend == "sqlite":
            _REPO = SqliteEvolutionRepo(settings.evolution_path)
        else:
            raise ValueError(f"unknown evolution_backend: {backend!r}")
        return _REPO
