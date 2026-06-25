from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from ocrforge_web.schemas import CulturalEntity, CulturalRelation
from ocrforge_web.settings import Settings

logger = logging.getLogger("ocrforge_web.deepseek_culture")


class ExtractedCulture(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    summary: str
    modern_translation: str
    entities: list[CulturalEntity]
    relations: list[CulturalRelation]


_SYSTEM_PROMPT = """你是严谨的中国古籍数字人文研究助手。请从用户提供的古籍文本中抽取人物、地点、官职、
时间、事件、作品和组织，并建立有原文依据的关系。

必须只输出一个 JSON 对象，不要输出 Markdown。JSON 结构：
{
  "title": "简短篇名",
  "summary": "文本内容摘要",
  "modern_translation": "忠实、通顺的现代汉语解释；疑难处保留谨慎表述",
  "entities": [
    {
      "id": "E1",
      "name": "原文名称",
      "normalized_name": "规范名称或 null",
      "type": "person|place|office|time|event|work|organization|other",
      "aliases": [],
      "description": "在本文中的身份或作用",
      "confidence": 0.0,
      "evidence": "能在原文中找到的最短直接证据",
      "status": "proposed"
    }
  ],
  "relations": [
    {
      "id": "R1",
      "source": "实体 id",
      "target": "实体 id",
      "type": "任职于|出生于|到达|参与|撰写|隶属于|发生于|同时代|其他准确短语",
      "evidence": "能在原文中找到的最短直接证据",
      "confidence": 0.0,
      "time": "原文时间或 null",
      "place": "原文地点或 null",
      "interpretation": "关系解释",
      "status": "proposed"
    }
  ]
}

规则：
1. 不得补造文本未出现的生平、年代或关系；常识只能用于规范名称，不能作为关系证据。
2. evidence 必须逐字来自原文。无法找到直接证据的关系不要输出。
3. source 和 target 必须引用 entities 中存在的 id。
4. 同一实体只保留一条，可将异名放入 aliases。
5. confidence 表示文本证据强度，不表示模型自信；直接明示关系可高于 0.9，推断关系不得高于 0.7。
6. modern_translation 不确定处使用“疑为”“或指”等措辞。
"""


class DeepSeekCultureClient:
    def __init__(self, settings: Settings):
        self.api_key = settings.llm_api_key
        self.base_url = settings.llm_base_url.rstrip("/")
        self.model = settings.llm_model
        self.timeout = settings.llm_timeout
        self.max_tokens = settings.llm_max_tokens

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def analyze(self, text: str, title: str | None = None) -> ExtractedCulture:
        if not self.api_key:
            raise RuntimeError("DeepSeek API key is not configured")

        user_prompt = f"篇名提示：{title or '无'}\n\n待分析古籍原文：\n{text}"
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.1,
            "max_tokens": self.max_tokens,
            "stream": False,
        }
        request = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw: dict[str, Any] = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            logger.warning("DeepSeek HTTP %s: %s", exc.code, detail[:500])
            raise RuntimeError(f"DeepSeek API returned HTTP {exc.code}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"cannot reach DeepSeek API: {exc.reason}") from exc

        try:
            choice = raw["choices"][0]
            content = choice["message"]["content"]
            parsed = _normalize_payload(
                json.loads(_strip_code_fence(content)),
                source_text=text,
                suggested_title=title,
            )
            result = ExtractedCulture.model_validate(parsed)
        except (KeyError, IndexError, TypeError, json.JSONDecodeError, ValidationError) as exc:
            finish_reason = None
            content_length = None
            try:
                choice = raw["choices"][0]
                finish_reason = choice.get("finish_reason")
                content_length = len(choice.get("message", {}).get("content") or "")
            except Exception:  # noqa: BLE001 - best-effort diagnostics
                pass
            logger.warning(
                "invalid structured response from DeepSeek: %s "
                "(finish_reason=%s, content_length=%s, max_tokens=%s)",
                exc,
                finish_reason,
                content_length,
                self.max_tokens,
            )
            raise RuntimeError("DeepSeek returned an invalid structured response") from exc

        return _sanitize_result(result, text)


def _strip_code_fence(content: str) -> str:
    value = content.strip()
    if value.startswith("```"):
        lines = value.splitlines()
        value = "\n".join(lines[1:-1])
    return value.strip()


def _normalize_payload(
    payload: Any,
    *,
    source_text: str,
    suggested_title: str | None,
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise TypeError("structured response must be a JSON object")

    type_aliases = {
        "人物": "person",
        "person": "person",
        "地点": "place",
        "地名": "place",
        "location": "place",
        "place": "place",
        "官职": "office",
        "职位": "office",
        "title": "office",
        "role": "office",
        "office": "office",
        "时间": "time",
        "日期": "time",
        "date": "time",
        "time": "time",
        "事件": "event",
        "行动": "event",
        "action": "event",
        "military_action": "event",
        "event": "event",
        "作品": "work",
        "书名": "work",
        "work": "work",
        "组织": "organization",
        "势力": "organization",
        "军队": "organization",
        "group": "organization",
        "organization": "organization",
    }

    raw_entities = payload.get("entities")
    entities: list[dict[str, Any]] = []
    if isinstance(raw_entities, list):
        for index, raw in enumerate(raw_entities, start=1):
            if not isinstance(raw, dict):
                continue
            name = str(raw.get("name") or raw.get("text") or "").strip()
            if not name:
                continue
            raw_type = str(raw.get("type") or raw.get("category") or "other").strip()
            aliases = raw.get("aliases", [])
            if isinstance(aliases, str):
                aliases = [aliases]
            if not isinstance(aliases, list):
                aliases = []
            evidence = str(raw.get("evidence") or name).strip()
            entities.append(
                {
                    "id": str(raw.get("id") or f"E{index}"),
                    "name": name,
                    "normalized_name": raw.get("normalized_name"),
                    "type": type_aliases.get(raw_type, "other"),
                    "aliases": [str(alias) for alias in aliases if alias],
                    "description": raw.get("description"),
                    "confidence": _confidence(raw.get("confidence")),
                    "evidence": evidence if evidence in source_text else name,
                    "status": "proposed",
                }
            )

    raw_relations = payload.get("relations")
    relations: list[dict[str, Any]] = []
    if isinstance(raw_relations, list):
        for index, raw in enumerate(raw_relations, start=1):
            if not isinstance(raw, dict):
                continue
            source = str(raw.get("source") or raw.get("source_id") or "").strip()
            target = str(raw.get("target") or raw.get("target_id") or "").strip()
            relation_type = str(
                raw.get("type") or raw.get("relation") or raw.get("predicate") or ""
            ).strip()
            if not source or not target or not relation_type:
                continue
            relations.append(
                {
                    "id": str(raw.get("id") or f"R{index}"),
                    "source": source,
                    "target": target,
                    "type": relation_type,
                    "evidence": str(raw.get("evidence") or "").strip(),
                    "confidence": _confidence(raw.get("confidence")),
                    "time": raw.get("time"),
                    "place": raw.get("place"),
                    "interpretation": raw.get("interpretation")
                    or raw.get("description"),
                    "status": "proposed",
                }
            )

    return {
        "title": str(payload.get("title") or suggested_title or "古籍关系分析")[:120],
        "summary": str(payload.get("summary") or "已完成实体与关系抽取。"),
        "modern_translation": str(
            payload.get("modern_translation")
            or payload.get("translation")
            or "未生成今译。"
        ),
        "entities": entities,
        "relations": relations,
    }


def _confidence(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.5
    return min(max(number, 0.0), 1.0)


def _sanitize_result(result: ExtractedCulture, source_text: str) -> ExtractedCulture:
    entities: list[CulturalEntity] = []
    used_ids: set[str] = set()
    for index, entity in enumerate(result.entities, start=1):
        entity_id = entity.id if entity.id and entity.id not in used_ids else f"E{index}"
        used_ids.add(entity_id)
        evidence = entity.evidence if entity.evidence in source_text else entity.name
        entities.append(
            entity.model_copy(
                update={
                    "id": entity_id,
                    "evidence": evidence if evidence in source_text else "",
                    "status": "proposed",
                }
            )
        )

    valid_ids = {entity.id for entity in entities}
    entity_id_by_name = {
        name: entity.id
        for entity in entities
        for name in [entity.name, entity.normalized_name, *entity.aliases]
        if name
    }
    relations: list[CulturalRelation] = []
    used_relation_ids: set[str] = set()
    for index, relation in enumerate(result.relations, start=1):
        source = entity_id_by_name.get(relation.source, relation.source)
        target = entity_id_by_name.get(relation.target, relation.target)
        if source not in valid_ids or target not in valid_ids:
            continue
        if relation.evidence not in source_text:
            continue
        relation_id = (
            relation.id
            if relation.id and relation.id not in used_relation_ids
            else f"R{index}"
        )
        used_relation_ids.add(relation_id)
        relations.append(
            relation.model_copy(
                update={
                    "id": relation_id,
                    "source": source,
                    "target": target,
                    "status": "proposed",
                }
            )
        )

    return result.model_copy(update={"entities": entities, "relations": relations})
