from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from ocrforge_web.agent.tools.base import Tool, ToolContext, no_params

_DATA_DIR = Path(__file__).resolve().parents[2] / "data"


# ---------- evolution character database (read-only) ----------

async def _search_characters(args: dict[str, Any], ctx: ToolContext) -> Any:
    from ocrforge_web.services.evolution_repo import get_repo

    record_type = args.get("record_type") or None
    tier = args.get("tier") or None
    limit = int(args.get("limit") or 30)
    limit = max(1, min(limit, 100))

    def _query() -> list[dict]:
        repo = get_repo()
        rows = repo.list_characters(record_type=record_type, tier=tier)
        return [r.model_dump(exclude_none=True) for r in rows[:limit]]

    rows = await asyncio.to_thread(_query)
    return {"count": len(rows), "characters": rows}


async def _get_character_detail(args: dict[str, Any], ctx: ToolContext) -> Any:
    from ocrforge_web.services.evolution_repo import get_repo

    char = str(args.get("char") or "").strip()
    if not char:
        return {"error": "char is required"}
    char = char[0]  # single character

    def _query() -> dict | None:
        repo = get_repo()
        record = repo.get(char)
        return record.model_dump(exclude_none=True) if record else None

    record = await asyncio.to_thread(_query)
    if record is None:
        return {"error": f"character {char!r} not found in database"}
    return record


async def _get_database_stats(args: dict[str, Any], ctx: ToolContext) -> Any:
    from ocrforge_web.services.evolution_repo import get_repo

    return await asyncio.to_thread(lambda: get_repo().stats())


async def _get_cl_analysis(args: dict[str, Any], ctx: ToolContext) -> Any:
    path = _DATA_DIR / "cl_analysis.v1.json"
    if not path.exists():
        return {"error": "CL analysis not generated yet"}
    return await asyncio.to_thread(lambda: json.loads(path.read_text(encoding="utf-8")))


# ---------- traditional <-> simplified conversion ----------

async def _convert_text(args: dict[str, Any], ctx: ToolContext) -> Any:
    from ocrforge_web.services import opencc_service

    text = str(args.get("text") or "")
    direction = args.get("direction") or "t2s"
    if not text:
        return {"error": "text is required"}
    if direction not in ("t2s", "s2t"):
        return {"error": "direction must be 't2s' or 's2t'"}

    def _run() -> dict:
        result = opencc_service.t2s(text) if direction == "t2s" else opencc_service.s2t(text)
        simplified_side = result if direction == "t2s" else text
        collisions = opencc_service.detect_collisions(simplified_side)
        return {
            "result": result,
            "direction": direction,
            "collisions": [c.model_dump() for c in collisions],
        }

    return await asyncio.to_thread(_run)


async def _convert_name(args: dict[str, Any], ctx: ToolContext) -> Any:
    from ocrforge_web.services import name_convert

    text = str(args.get("text") or "").strip()
    if not text:
        return {"error": "text is required"}

    def _run() -> dict:
        return name_convert.convert(text).model_dump(exclude_none=True)

    return await asyncio.to_thread(_run)


# ---------- OCR 上下文校对 ----------

async def _proofread_ocr(args: dict[str, Any], ctx: ToolContext) -> Any:
    from ocrforge_web.services.ocr_proofread import OcrProofreadClient

    text = str(args.get("text") or "").strip()
    if not text:
        return {"error": "text is required"}

    client = OcrProofreadClient(ctx.settings)

    def _run() -> dict:
        return client.proofread(text).model_dump(exclude_none=True)

    try:
        return await asyncio.to_thread(_run)
    except RuntimeError as exc:
        return {"error": str(exc)}


# ---------- cultural relation graph (history tab) ----------

async def _list_culture_analyses(args: dict[str, Any], ctx: ToolContext) -> Any:
    from ocrforge_web.services.culture_store import CultureStore

    limit = int(args.get("limit") or 20)
    limit = max(1, min(limit, 100))
    path = ctx.settings.culture_db_path

    def _query() -> list[dict]:
        store = CultureStore(path)
        return [s.model_dump() for s in store.list(limit)]

    return {"analyses": await asyncio.to_thread(_query)}


async def _get_culture_analysis(args: dict[str, Any], ctx: ToolContext) -> Any:
    from ocrforge_web.services.culture_store import CultureStore

    analysis_id = str(args.get("id") or "").strip()
    if not analysis_id:
        return {"error": "id is required"}
    path = ctx.settings.culture_db_path

    def _query() -> dict | None:
        store = CultureStore(path)
        analysis = store.get(analysis_id)
        return analysis.model_dump() if analysis else None

    record = await asyncio.to_thread(_query)
    if record is None:
        return {"error": f"culture analysis {analysis_id!r} not found"}
    return record


def db_tools() -> list[Tool]:
    return [
        Tool(
            name="search_characters",
            description=(
                "检索繁简字库。可按 record_type(merge=多对一合并字 / one_to_one=一对一) 与 "
                "tier(grid=常用 / archive=罕用扩展) 过滤，返回字头摘要列表。"
            ),
            parameters={
                "type": "object",
                "properties": {
                    "record_type": {"type": "string", "enum": ["merge", "one_to_one"]},
                    "tier": {"type": "string", "enum": ["grid", "archive"]},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 100, "default": 30},
                },
                "additionalProperties": False,
            },
            handler=_search_characters,
        ),
        Tool(
            name="get_character_detail",
            description=(
                "取单个简体汉字的完整记录：繁体来源(merges)、历史演化阶段(stages)、拼音、"
                "笔画、以及 extensions 内的文化计算指标(OCR 风险/语义歧义/简化方式)。"
            ),
            parameters={
                "type": "object",
                "properties": {"char": {"type": "string", "description": "简体汉字（单字）"}},
                "required": ["char"],
                "additionalProperties": False,
            },
            handler=_get_character_detail,
        ),
        Tool(
            name="get_database_stats",
            description="返回繁简字库的统计概览（总量、合并字数、各 tier/curation 分布等）。",
            parameters=no_params(),
            handler=_get_database_stats,
        ),
        Tool(
            name="get_cl_analysis",
            description=(
                "返回全库的计算语言学分析：笔画简化分布、省力原则相关性、同音归并、OCR 易混对。"
            ),
            parameters=no_params(),
            handler=_get_cl_analysis,
        ),
        Tool(
            name="convert_text",
            description="繁简转换。direction=t2s 繁→简，s2t 简→繁；附带多对一合并字碰撞信息。",
            parameters={
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "direction": {"type": "string", "enum": ["t2s", "s2t"], "default": "t2s"},
                },
                "required": ["text"],
                "additionalProperties": False,
            },
            handler=_convert_text,
        ),
        Tool(
            name="convert_name",
            description=(
                "把繁体专有名词(人名/地名，尤其 CBDB/CHGIS 权威名)做'繁→简'转换：联合四个文字"
                "数据库——CC-CEDICT 整词优先、OpenCC+Unihan 逐字兜底、CHISE 部件佐证，返回简体结果、"
                "置信度、分歧标注(conflict)与各库证据。人名/地名请用本工具而非 convert_text。"
            ),
            parameters={
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "繁体专有名词（人名/地名）"}
                },
                "required": ["text"],
                "additionalProperties": False,
            },
            handler=_convert_name,
        ),
        Tool(
            name="proofread_ocr",
            description=(
                "古籍 OCR 校对：按 OCR 逐字置信度选出待校对字、用形近字库 + OCR 次优给候选。"
                "选字依赖逐字置信度，纯文本调用拿不到置信度会返回空结果——此时应提示用户到"
                "「古籍识读」页用本地 PaddleOCR-VL 识读后点「校对」。"
            ),
            parameters={
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "待校对的古籍文本（通常为繁体）"}
                },
                "required": ["text"],
                "additionalProperties": False,
            },
            handler=_proofread_ocr,
        ),
        Tool(
            name="list_culture_analyses",
            description="列出'史脉'标签页中已保存的古籍文化关系分析（实体-关系图谱）摘要。",
            parameters={
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "minimum": 1, "maximum": 100, "default": 20}
                },
                "additionalProperties": False,
            },
            handler=_list_culture_analyses,
        ),
        Tool(
            name="get_culture_analysis",
            description="按 id 取某条古籍文化关系分析的完整内容（实体、关系、今译、摘要）。",
            parameters={
                "type": "object",
                "properties": {"id": {"type": "string"}},
                "required": ["id"],
                "additionalProperties": False,
            },
            handler=_get_culture_analysis,
        ),
    ]
