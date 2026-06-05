from __future__ import annotations

from fastapi import APIRouter

from ocrforge_web.schemas import ConvertRequest, ConvertResponse
from ocrforge_web.services import opencc_service

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
