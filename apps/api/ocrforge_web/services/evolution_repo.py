from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Protocol

from ocrforge_web.schemas import CharRecord, CharSummary


class EvolutionRepository(Protocol):
    def list_characters(self) -> list[CharSummary]: ...
    def get(self, char: str) -> CharRecord | None: ...


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

    def list_characters(self) -> list[CharSummary]:
        self._reload_if_stale()
        return [
            CharSummary(
                simplified=self._records[k].simplified,
                traditional=self._records[k].traditional,
                pinyin=self._records[k].pinyin,
            )
            for k in self._order
        ]

    def get(self, char: str) -> CharRecord | None:
        self._reload_if_stale()
        return self._records.get(char)


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


class SqliteEvolutionRepo:
    def __init__(self, path: Path) -> None:
        raise NotImplementedError(
            "SqliteEvolutionRepo is a placeholder. Implement backed by the same "
            "schema as evolution.json when scaling beyond ~100 characters."
        )

    def list_characters(self) -> list[CharSummary]:  # pragma: no cover
        raise NotImplementedError

    def get(self, char: str) -> CharRecord | None:  # pragma: no cover
        raise NotImplementedError


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
