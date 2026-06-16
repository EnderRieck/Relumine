from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from ocrforge_web.schemas import CharRecord, CharSummary
from ocrforge_web.services.evolution_repo import EvolutionRepository, get_repo

router = APIRouter(tags=["evolution"])


@router.get("/evolution", response_model=list[CharSummary])
def list_evolution(
    type: str | None = Query(default=None, pattern="^(merge|one_to_one)$"),
    tier: str | None = Query(default=None, pattern="^(grid|archive)$"),
    repo: EvolutionRepository = Depends(get_repo),
) -> list[CharSummary]:
    return repo.list_characters(record_type=type, tier=tier)


@router.get("/evolution/stats")
def evolution_stats(repo: EvolutionRepository = Depends(get_repo)) -> dict:
    return repo.stats()


@router.get("/evolution/cl-analysis")
def evolution_cl_analysis() -> dict:
    import json
    from pathlib import Path

    path = Path(__file__).resolve().parents[1] / "data" / "cl_analysis.v1.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="CL analysis not generated yet")
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["database_radar"] = _database_radar_payload()
    return payload


def _database_radar_payload() -> dict:
    axes = [
        {
            "key": "coverage",
            "label": "规模覆盖",
            "description": "字符/词条覆盖范围，反映能作为底层证据库的广度。",
        },
        {
            "key": "mapping",
            "label": "繁简映射",
            "description": "是否直接给出繁简对应、多候选和转换关系。",
        },
        {
            "key": "lexical",
            "label": "字义词证",
            "description": "读音、释义、词条例证等可解释语言证据。",
        },
        {
            "key": "structure",
            "label": "字形结构",
            "description": "笔画、部首、IDS 部件拆解等字形计算能力。",
        },
        {
            "key": "interpretation",
            "label": "文化解释",
            "description": "是否解释简化机制、语义歧义、OCR 风险和演化证据链。",
        },
    ]
    databases = [
        {
            "name": "Unihan",
            "role": "基础属性层",
            "record_count": 1555629,
            "unique_chars": 102998,
            "scores": {
                "coverage": 5,
                "mapping": 3,
                "lexical": 4,
                "structure": 4,
                "interpretation": 1,
            },
            "strength": "编码范围最大，提供读音、释义、笔画、部首和官方繁简变体。",
            "limitation": "不解释具体简化机制，也不生成文化计算指标。",
        },
        {
            "name": "OpenCC",
            "role": "转换规则层",
            "record_count": 8130,
            "unique_chars": 8169,
            "scores": {
                "coverage": 3,
                "mapping": 5,
                "lexical": 1,
                "structure": 1,
                "interpretation": 1,
            },
            "strength": "繁简转换和多候选映射最直接，是全量繁简对应的主骨架。",
            "limitation": "只告诉怎么转，不说明为什么这样转。",
        },
        {
            "name": "CC-CEDICT",
            "role": "词义例证层",
            "record_count": 125002,
            "unique_chars": 14382,
            "scores": {
                "coverage": 4,
                "mapping": 4,
                "lexical": 5,
                "structure": 1,
                "interpretation": 2,
            },
            "strength": "词级繁简、拼音和英文释义可验证映射在真实词条中的使用。",
            "limitation": "词典不分析字形结构，也不专门讨论简化造成的歧义。",
        },
        {
            "name": "CHISE IDS",
            "role": "字形结构层",
            "record_count": 97431,
            "unique_chars": 97431,
            "scores": {
                "coverage": 4,
                "mapping": 1,
                "lexical": 1,
                "structure": 5,
                "interpretation": 1,
            },
            "strength": "提供 IDS 部件分解，适合计算部件变化和 OCR 形近风险。",
            "limitation": "不处理现代繁简转换，也不提供词义解释。",
        },
        {
            "name": "Relumine",
            "role": "综合解释层",
            "record_count": 4941,
            "unique_chars": 4941,
            "scores": {
                "coverage": 3,
                "mapping": 4,
                "lexical": 3,
                "structure": 4,
                "interpretation": 5,
            },
            "strength": "把四库证据整合为简化类型、语义歧义、笔画削减、OCR 风险和演化证据链。",
            "limitation": "规模小于官方底库，定位是可解释研究层而不是替代官方库。",
            "derived_from": ["Unihan", "OpenCC", "CC-CEDICT", "CHISE IDS"],
        },
    ]
    contributions = [
        {
            "source": "Unihan",
            "provides": "笔画、部首、读音、释义、官方变体",
            "used_for": "笔画削减、基础属性、读音同化分析",
            "relumine_value": "把基础属性转成可比较的简化指标。",
        },
        {
            "source": "OpenCC",
            "provides": "简繁单字映射和多候选关系",
            "used_for": "确定收录范围、构造多繁一简来源",
            "relumine_value": "在映射之上标注简化类型和歧义风险。",
        },
        {
            "source": "CC-CEDICT",
            "provides": "词级繁简、拼音和释义例证",
            "used_for": "字频代理、词义验证、语义歧义统计",
            "relumine_value": "把词条例证转成文化语义解释。",
        },
        {
            "source": "CHISE IDS",
            "provides": "汉字 IDS 部件拆解",
            "used_for": "部件变化、形近混淆、OCR 风险估计",
            "relumine_value": "把结构数据转成古籍 OCR 风险提示。",
        },
    ]
    thesis = (
        "四个外部库提供权威证据，Relumine 的优势不是规模更大，"
        "而是把证据转化为繁简演化解释、文化计算指标和可复核的证据链。"
    )
    return {
        "scale": 5,
        "axes": axes,
        "databases": databases,
        "contributions": contributions,
        "thesis": thesis,
    }


@router.get("/evolution/{char}", response_model=CharRecord)
def get_evolution(char: str, repo: EvolutionRepository = Depends(get_repo)) -> CharRecord:
    record = repo.get(char)
    if record is None:
        raise HTTPException(status_code=404, detail=f"character {char!r} not found")
    return record
