from __future__ import annotations

import sqlite3
from pathlib import Path

from ocrforge_web.schemas import (
    CultureAnalysis,
    CultureAnalysisSummary,
    CultureReviewRequest,
)


class CultureStore:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS documents (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    source_text TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    modern_translation TEXT NOT NULL,
                    model TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS entities (
                    document_id TEXT NOT NULL,
                    local_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    normalized_name TEXT,
                    type TEXT NOT NULL,
                    aliases_json TEXT NOT NULL,
                    description TEXT,
                    confidence REAL NOT NULL,
                    evidence TEXT NOT NULL,
                    status TEXT NOT NULL,
                    authority_json TEXT NOT NULL DEFAULT '[]',
                    PRIMARY KEY (document_id, local_id),
                    FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS relations (
                    document_id TEXT NOT NULL,
                    local_id TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    target_id TEXT NOT NULL,
                    type TEXT NOT NULL,
                    evidence TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    time_label TEXT,
                    place_label TEXT,
                    interpretation TEXT,
                    status TEXT NOT NULL,
                    PRIMARY KEY (document_id, local_id),
                    FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_entities_name ON entities(name);
                CREATE INDEX IF NOT EXISTS idx_relations_type ON relations(type);
                """
            )
            columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(entities)").fetchall()
            }
            if "authority_json" not in columns:
                connection.execute(
                    "ALTER TABLE entities ADD COLUMN authority_json TEXT NOT NULL DEFAULT '[]'"
                )

    def save(self, analysis: CultureAnalysis) -> CultureAnalysis:
        import json

        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO documents
                    (id, title, source_text, summary, modern_translation, model, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    analysis.id,
                    analysis.title,
                    analysis.source_text,
                    analysis.summary,
                    analysis.modern_translation,
                    analysis.model,
                    analysis.created_at,
                ),
            )
            connection.executemany(
                """
                INSERT INTO entities
                    (document_id, local_id, name, normalized_name, type, aliases_json,
                     description, confidence, evidence, status, authority_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        analysis.id,
                        entity.id,
                        entity.name,
                        entity.normalized_name,
                        entity.type,
                        json.dumps(entity.aliases, ensure_ascii=False),
                        entity.description,
                        entity.confidence,
                        entity.evidence,
                        entity.status,
                        json.dumps(
                            [match.model_dump() for match in entity.authority_matches],
                            ensure_ascii=False,
                        ),
                    )
                    for entity in analysis.entities
                ],
            )
            connection.executemany(
                """
                INSERT INTO relations
                    (document_id, local_id, source_id, target_id, type, evidence,
                     confidence, time_label, place_label, interpretation, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        analysis.id,
                        relation.id,
                        relation.source,
                        relation.target,
                        relation.type,
                        relation.evidence,
                        relation.confidence,
                        relation.time,
                        relation.place,
                        relation.interpretation,
                        relation.status,
                    )
                    for relation in analysis.relations
                ],
            )
        return analysis

    def get(self, analysis_id: str) -> CultureAnalysis | None:
        import json

        with self._connect() as connection:
            document = connection.execute(
                "SELECT * FROM documents WHERE id = ?", (analysis_id,)
            ).fetchone()
            if document is None:
                return None
            entity_rows = connection.execute(
                "SELECT * FROM entities WHERE document_id = ? ORDER BY local_id",
                (analysis_id,),
            ).fetchall()
            relation_rows = connection.execute(
                "SELECT * FROM relations WHERE document_id = ? ORDER BY local_id",
                (analysis_id,),
            ).fetchall()

        return CultureAnalysis(
            id=document["id"],
            title=document["title"],
            source_text=document["source_text"],
            summary=document["summary"],
            modern_translation=document["modern_translation"],
            model=document["model"],
            created_at=document["created_at"],
            entities=[
                {
                    "id": row["local_id"],
                    "name": row["name"],
                    "normalized_name": row["normalized_name"],
                    "type": row["type"],
                    "aliases": json.loads(row["aliases_json"]),
                    "description": row["description"],
                    "confidence": row["confidence"],
                    "evidence": row["evidence"],
                    "status": row["status"],
                    "authority_matches": json.loads(row["authority_json"] or "[]"),
                }
                for row in entity_rows
            ],
            relations=[
                {
                    "id": row["local_id"],
                    "source": row["source_id"],
                    "target": row["target_id"],
                    "type": row["type"],
                    "evidence": row["evidence"],
                    "confidence": row["confidence"],
                    "time": row["time_label"],
                    "place": row["place_label"],
                    "interpretation": row["interpretation"],
                    "status": row["status"],
                }
                for row in relation_rows
            ],
        )

    def list(self, limit: int = 20) -> list[CultureAnalysisSummary]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT d.id, d.title, d.summary, d.created_at,
                       COUNT(DISTINCT e.local_id) AS entity_count,
                       COUNT(DISTINCT r.local_id) AS relation_count
                FROM documents d
                LEFT JOIN entities e ON e.document_id = d.id
                LEFT JOIN relations r ON r.document_id = d.id
                GROUP BY d.id
                ORDER BY d.created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [CultureAnalysisSummary(**dict(row)) for row in rows]

    def review(
        self, analysis_id: str, request: CultureReviewRequest
    ) -> CultureAnalysis | None:
        with self._connect() as connection:
            exists = connection.execute(
                "SELECT 1 FROM documents WHERE id = ?", (analysis_id,)
            ).fetchone()
            if exists is None:
                return None
            connection.executemany(
                """
                UPDATE entities SET status = ?
                WHERE document_id = ? AND local_id = ?
                """,
                [
                    (status, analysis_id, local_id)
                    for local_id, status in request.entity_statuses.items()
                ],
            )
            connection.executemany(
                """
                UPDATE relations SET status = ?
                WHERE document_id = ? AND local_id = ?
                """,
                [
                    (status, analysis_id, local_id)
                    for local_id, status in request.relation_statuses.items()
                ],
            )
        return self.get(analysis_id)

    def replace_entities(
        self, analysis_id: str, entities: list
    ) -> CultureAnalysis | None:
        import json

        with self._connect() as connection:
            exists = connection.execute(
                "SELECT 1 FROM documents WHERE id = ?", (analysis_id,)
            ).fetchone()
            if exists is None:
                return None
            connection.executemany(
                """
                UPDATE entities
                SET normalized_name = ?, authority_json = ?
                WHERE document_id = ? AND local_id = ?
                """,
                [
                    (
                        entity.normalized_name,
                        json.dumps(
                            [match.model_dump() for match in entity.authority_matches],
                            ensure_ascii=False,
                        ),
                        analysis_id,
                        entity.id,
                    )
                    for entity in entities
                ],
            )
        return self.get(analysis_id)
