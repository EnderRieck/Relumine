from __future__ import annotations

from fastapi import APIRouter

from ocrforge_web.schemas import (
    ConvertRequest,
    ConvertResponse,
    NameConversion,
    NameConvertBatchRequest,
    NameConvertRequest,
)
from ocrforge_web.services import name_convert, opencc_service

router = APIRouter(tags=["convert"])


@router.post("/convert", response_model=ConvertResponse)
def convert(req: ConvertRequest) -> ConvertResponse:
    if req.direction == "t2s":
        result = opencc_service.t2s(req.text)
        simplified_side = result
    else:
        result = opencc_service.s2t(req.text)
        simplified_side = req.text

    collisions = opencc_service.detect_collisions(simplified_side)
    return ConvertResponse(result=result, direction=req.direction, collisions=collisions)


@router.post("/convert/name", response_model=NameConversion)
def convert_name(req: NameConvertRequest) -> NameConversion:
    """繁→简 conversion of a single proper noun (CBDB/CHGIS name) with
    multi-source evidence (CC-CEDICT 词级 → OpenCC/Unihan 字级 → CHISE 佐证)."""
    return name_convert.convert(req.text)


@router.post("/convert/name/batch", response_model=list[NameConversion])
def convert_name_batch(req: NameConvertBatchRequest) -> list[NameConversion]:
    return [name_convert.convert(text) for text in req.texts]


@router.get("/convert/name/sources")
def convert_name_sources() -> dict:
    """Report which text databases the conversion index loaded."""
    return name_convert.info()
