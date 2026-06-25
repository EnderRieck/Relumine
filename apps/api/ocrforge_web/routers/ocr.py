from __future__ import annotations

import asyncio
import logging
import tempfile
import time
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from ocrforge_web.schemas import (
    OcrQueueStatus,
    OcrResponse,
    ProofreadRequest,
    ProofreadResult,
)
from ocrforge_web.services import ocr_service
from ocrforge_web.services.ocr_proofread import OcrProofreadClient
from ocrforge_web.settings import Settings, get_settings

logger = logging.getLogger("ocrforge_web.ocr_router")

router = APIRouter(tags=["ocr"])


def _proofreader(settings: Settings = Depends(get_settings)) -> OcrProofreadClient:
    return OcrProofreadClient(settings)

_ALLOWED_TYPES = {"image/jpeg", "image/jpg", "image/png", "image/webp"}
_ALLOWED_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}


@router.get("/ocr/queue", response_model=OcrQueueStatus)
async def ocr_queue() -> OcrQueueStatus:
    return OcrQueueStatus(depth=ocr_service.queue_depth())


@router.post("/ocr/proofread", response_model=ProofreadResult)
async def ocr_proofread(
    request: ProofreadRequest,
    proofreader: OcrProofreadClient = Depends(_proofreader),
) -> ProofreadResult:
    """对（OCR 识读出的）古籍文本做上下文校对，标注可疑字并给候选；不改原文。"""
    if not proofreader.configured:
        raise HTTPException(status_code=503, detail="DeepSeek API key is not configured")
    try:
        return await asyncio.to_thread(
            proofreader.proofread,
            request.text,
            request.char_confidences,
            request.ocr_candidates,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/ocr", response_model=OcrResponse)
async def ocr(file: UploadFile = File(...)) -> OcrResponse:
    if not ocr_service.is_loaded():
        raise HTTPException(status_code=503, detail="model not loaded yet")

    content_type = (file.content_type or "").lower()
    suffix = Path(file.filename or "").suffix.lower()
    if content_type not in _ALLOWED_TYPES and suffix not in _ALLOWED_SUFFIXES:
        raise HTTPException(
            status_code=415,
            detail=f"unsupported media type: {content_type or suffix or 'unknown'}",
        )

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="empty upload")

    tmp_suffix = suffix or ".jpg"
    with tempfile.NamedTemporaryFile(suffix=tmp_suffix, delete=False) as tmp:
        tmp.write(data)
        tmp_path = Path(tmp.name)

    try:
        t0 = time.time()
        detailed = await ocr_service.run_ocr_detailed(tmp_path)
        latency_ms = int((time.time() - t0) * 1000)
    finally:
        try:
            tmp_path.unlink()
        except FileNotFoundError:
            pass

    text = detailed["text"]
    return OcrResponse(
        text=text,
        char_count=len(text),
        latency_ms=latency_ms,
        char_confidences=detailed.get("char_confidences"),
        alternatives=detailed.get("alternatives"),
    )
