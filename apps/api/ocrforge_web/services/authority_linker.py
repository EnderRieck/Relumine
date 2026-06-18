from __future__ import annotations

import json
import sqlite3
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from pathlib import Path
from typing import Any

from ocrforge_web.schemas import AuthorityMatch, CulturalEntity
from ocrforge_web.services import name_convert
from ocrforge_web.settings import Settings

# An alias-only (字/号) CBDB match must fall within this many years of the era
# anchored by the analysis's exact matches, else it is a cross-era namesake.
_ERA_WINDOW = 300


def _with_simplified(match: AuthorityMatch) -> AuthorityMatch:
    """Attach a real-time 繁→简 rendering + evidence to an authority match."""
    conversion = name_convert.convert(match.canonical_name)
    return match.model_copy(
        update={
            "canonical_name_simplified": conversion.simplified,
            "name_conversion": conversion,
        }
    )


class AuthorityLinker:
    def __init__(self, settings: Settings):
        self.cbdb_path = settings.cbdb_path
        self.chgis_api_url = settings.chgis_api_url
        self.timeout = settings.authority_timeout

    @property
    def cbdb_available(self) -> bool:
        return self.cbdb_path.is_file()

    @property
    def chgis_available(self) -> bool:
        return bool(self.chgis_api_url)

    def link_entities(self, entities: list[CulturalEntity]) -> list[CulturalEntity]:
        # Pass 1 — anchor the era from RELIABLE (exact) person matches only, so
        # alias matches can be sanity-checked against the analysis's century.
        context_years: list[int] = []
        if self.cbdb_available:
            for entity in entities:
                if entity.type != "person":
                    continue
                for match in self._match_cbdb(entity):
                    if match.match_type != "exact":
                        continue
                    year = match.metadata.get("index_year") or match.metadata.get(
                        "birth_year"
                    )
                    if isinstance(year, int) and year != 0:
                        context_years.append(year)
        context_year = (
            sorted(context_years)[len(context_years) // 2] if context_years else None
        )

        # Pass 2 — full person matches (exact + era-filtered, unambiguous alias).
        person_matches: dict[str, list[AuthorityMatch]] = {}
        if self.cbdb_available:
            for entity in entities:
                if entity.type == "person":
                    person_matches[entity.id] = self._match_cbdb(
                        entity, context_year=context_year
                    )

        place_matches = {
            entity.id: self._match_chgis(entity, context_year=context_year)
            for entity in entities
            if entity.type == "place" and self.chgis_available
        }
        place_matches = _spatially_rank_place_matches(place_matches)
        linked: list[CulturalEntity] = []
        for entity in entities:
            matches: list[AuthorityMatch] = []
            if entity.type == "person":
                matches = person_matches.get(entity.id, [])
            elif entity.type == "place" and self.chgis_available:
                matches = place_matches.get(entity.id, [])
            matches = [_with_simplified(match) for match in matches]
            # Deliberately do NOT overwrite normalized_name with a match: that made
            # re-linking non-idempotent (a wrong match became the next search key
            # and could drift). The authority name lives on canonical_name /
            # canonical_name_simplified; normalized_name stays as the extractor set it.
            linked.append(entity.model_copy(update={"authority_matches": matches}))
        return linked

    def _match_cbdb(
        self, entity: CulturalEntity, context_year: int | None = None
    ) -> list[AuthorityMatch]:
        names = _candidate_names(entity)
        if not names:
            return []
        connection = sqlite3.connect(
            f"file:{self.cbdb_path}?mode=ro", uri=True, timeout=10
        )
        connection.row_factory = sqlite3.Row
        try:
            main_columns = _table_columns(connection, "BIOG_MAIN")
            person_id = _pick(main_columns, "c_personid", "personid")
            chinese_name = _pick(main_columns, "c_name_chn", "c_name")
            if not person_id or not chinese_name:
                return []
            selected = [
                column
                for column in (
                    person_id,
                    chinese_name,
                    _pick(main_columns, "c_name"),
                    _pick(main_columns, "c_birthyear"),
                    _pick(main_columns, "c_deathyear"),
                    _pick(main_columns, "c_dy"),
                    _pick(main_columns, "c_index_year"),
                    _pick(main_columns, "c_female"),
                )
                if column
            ]
            placeholders = ",".join("?" for _ in names)
            col_list = ",".join(_quote(column) for column in selected)

            exact_rows = list(
                connection.execute(
                    f"SELECT {col_list} FROM BIOG_MAIN "
                    f"WHERE {_quote(chinese_name)} IN ({placeholders}) LIMIT 8",
                    names,
                )
            )

            alias_rows: list[sqlite3.Row] = []
            alt_columns = _table_columns(connection, "ALTNAME_DATA")
            alt_person = _pick(alt_columns, "c_personid", "personid")
            alt_name = _pick(alt_columns, "c_alt_name_chn", "c_alt_name")
            if alt_person and alt_name:
                b_cols = ",".join("b." + _quote(column) for column in selected)
                alias_rows = list(
                    connection.execute(
                        f"SELECT {b_cols}, a.{_quote(alt_name)} AS matched_alias "
                        "FROM ALTNAME_DATA a JOIN BIOG_MAIN b "
                        f"ON a.{_quote(alt_person)} = b.{_quote(person_id)} "
                        f"WHERE a.{_quote(alt_name)} IN ({placeholders}) LIMIT 40",
                        names,
                    )
                )
            return self._assemble_cbdb(
                entity, exact_rows, alias_rows, person_id, chinese_name, context_year
            )
        finally:
            connection.close()

    def _assemble_cbdb(
        self,
        entity: CulturalEntity,
        exact_rows: list[sqlite3.Row],
        alias_rows: list[sqlite3.Row],
        person_id: str,
        chinese_name: str,
        context_year: int | None,
    ) -> list[AuthorityMatch]:
        results: list[AuthorityMatch] = []
        seen: set[str] = set()
        for row in exact_rows:
            pid = str(row[person_id])
            if pid in seen:
                continue
            seen.add(pid)
            results.append(
                self._make_cbdb_match(entity, row, "exact", 0.97, person_id, chinese_name)
            )

        # Alias (字/号) matches are weak: a courtesy name shared by several people
        # (e.g. 子楚) is not an identifier. Only trust an alias that singles out ONE
        # person, only when no exact match already won, and only when it does not
        # land in a different era than the rest of the analysis.
        if not results and alias_rows:
            persons_by_alias: dict[str, set[str]] = defaultdict(set)
            row_by_pair: dict[tuple[str, str], sqlite3.Row] = {}
            for row in alias_rows:
                alias = str(row["matched_alias"])
                pid = str(row[person_id])
                persons_by_alias[alias].add(pid)
                row_by_pair.setdefault((alias, pid), row)
            for alias, pids in persons_by_alias.items():
                if len(pids) != 1:
                    continue  # ambiguous courtesy/alt name — drop entirely
                pid = next(iter(pids))
                if pid in seen:
                    continue
                row = row_by_pair[(alias, pid)]
                if context_year is not None:
                    year = _row_int(row, "c_index_year") or _row_int(row, "c_birthyear")
                    if year is not None and abs(year - context_year) > _ERA_WINDOW:
                        continue  # cross-era namesake
                seen.add(pid)
                results.append(
                    self._make_cbdb_match(entity, row, "alias", 0.65, person_id, chinese_name)
                )
        return results[:3]

    def _make_cbdb_match(
        self,
        entity: CulturalEntity,
        row: sqlite3.Row,
        match_type: str,
        confidence: float,
        person_id: str,
        chinese_name: str,
    ) -> AuthorityMatch:
        authority_id = str(row[person_id])
        birth = _row_value(row, "c_birthyear")
        death = _row_value(row, "c_deathyear")
        return AuthorityMatch(
            source="CBDB",
            authority_id=authority_id,
            canonical_name=str(row[chinese_name] or entity.name),
            match_type=match_type,
            confidence=confidence,
            source_url=(
                "https://cbdb.fas.harvard.edu/cbdbapi/person.php"
                f"?id={urllib.parse.quote(authority_id)}"
            ),
            label="中国历代人物传记资料库",
            years=_year_span(birth, death),
            metadata={
                "birth_year": birth,
                "death_year": death,
                "dynasty_code": _row_value(row, "c_dy"),
                "index_year": _row_value(row, "c_index_year"),
                "female": _row_value(row, "c_female"),
            },
        )

    def _match_chgis(
        self, entity: CulturalEntity, context_year: int | None = None
    ) -> list[AuthorityMatch]:
        candidates: list[dict[str, Any]] = []
        for name in _candidate_names(entity):
            params: dict[str, Any] = {"n": name, "fmt": "json"}
            if context_year is not None and -222 <= context_year <= 1911:
                params["yr"] = context_year
            query = urllib.parse.urlencode(params)
            request = urllib.request.Request(
                f"{self.chgis_api_url}?{query}",
                headers={"User-Agent": "Relumine/0.1 academic research"},
            )
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    payload = json.loads(response.read().decode("utf-8"))
            except (urllib.error.URLError, json.JSONDecodeError, TimeoutError):
                continue
            rows = payload.get("placenames", [])
            if isinstance(rows, list):
                candidates.extend(row for row in rows if isinstance(row, dict))

        ranked = sorted(
            candidates,
            key=lambda row: (
                0 if str(row.get("name", "")) in _candidate_names(entity) else 1,
                0 if row.get("object type") == "POINT" else 1,
                0 if row.get("data source") == "CHGIS" else 1,
                str(row.get("years", "")),
            ),
        )
        results: list[AuthorityMatch] = []
        seen: set[str] = set()
        for row in ranked:
            authority_id = str(row.get("sys_id") or "")
            if not authority_id or authority_id in seen:
                continue
            seen.add(authority_id)
            longitude, latitude = _coordinates(row.get("xy coordinates"))
            canonical_name = str(row.get("name") or entity.name)
            exact = canonical_name in _candidate_names(entity)
            results.append(
                AuthorityMatch(
                    source="CHGIS",
                    authority_id=authority_id,
                    canonical_name=canonical_name,
                    match_type="exact" if exact else "prefix",
                    confidence=0.97 if exact else 0.82,
                    source_url=str(
                        row.get("uri")
                        or f"https://chgis.hudci.org/tgaz/placename/{authority_id}"
                    ),
                    label="中国历史地理信息系统",
                    years=_optional_text(row.get("years")),
                    parent_name=_optional_text(row.get("parent name")),
                    feature_type=_optional_text(row.get("feature type")),
                    longitude=longitude,
                    latitude=latitude,
                    metadata={
                        "transcription": row.get("transcription"),
                        "object_type": row.get("object type"),
                        "data_source": row.get("data source"),
                    },
                )
            )
            if len(results) == 3:
                break
        return results


def _candidate_names(entity: CulturalEntity) -> list[str]:
    names = [entity.name, entity.normalized_name, *entity.aliases]
    return list(dict.fromkeys(name.strip() for name in names if name and name.strip()))


def _table_columns(connection: sqlite3.Connection, table: str) -> set[str]:
    return {
        str(row[1])
        for row in connection.execute(f"PRAGMA table_info({_quote(table)})").fetchall()
    }


def _pick(columns: set[str], *candidates: str) -> str | None:
    return next((candidate for candidate in candidates if candidate in columns), None)


def _quote(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _row_value(row: sqlite3.Row, key: str) -> Any:
    return row[key] if key in row.keys() else None


def _row_int(row: sqlite3.Row, key: str) -> int | None:
    try:
        value = int(_row_value(row, key))
    except (TypeError, ValueError):
        return None
    return value or None


def _year_span(birth: Any, death: Any) -> str | None:
    if birth and death:
        return f"{birth}–{death}"
    if birth:
        return f"{birth}–?"
    if death:
        return f"?–{death}"
    return None


def _coordinates(value: Any) -> tuple[float | None, float | None]:
    try:
        longitude_text, latitude_text = str(value).split(",", maxsplit=1)
        longitude = float(longitude_text.strip())
        latitude = float(latitude_text.strip())
    except (ValueError, TypeError):
        return None, None
    if longitude == 0 or not (-180 <= longitude <= 180 and -90 <= latitude <= 90):
        return None, None
    return longitude, latitude


def _optional_text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _spatially_rank_place_matches(
    matches_by_entity: dict[str, list[AuthorityMatch]],
) -> dict[str, list[AuthorityMatch]]:
    if len(matches_by_entity) < 2:
        return matches_by_entity
    ranked: dict[str, list[AuthorityMatch]] = {}
    for entity_id, matches in matches_by_entity.items():
        other_groups = [
            candidates
            for other_id, candidates in matches_by_entity.items()
            if other_id != entity_id
        ]

        def score(match: AuthorityMatch) -> tuple[float, float]:
            if match.longitude is None or match.latitude is None:
                return (float("inf"), -match.confidence)
            distance = 0.0
            compared = 0
            for candidates in other_groups:
                distances = [
                    (match.longitude - candidate.longitude) ** 2
                    + (match.latitude - candidate.latitude) ** 2
                    for candidate in candidates
                    if candidate.longitude is not None and candidate.latitude is not None
                ]
                if distances:
                    distance += min(distances)
                    compared += 1
            return (
                distance / compared if compared else float("inf"),
                -match.confidence,
            )

        ranked[entity_id] = sorted(matches, key=score)
    return ranked
