from __future__ import annotations

import logging
import tempfile
import time
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from ocrforge_web.schemas import OcrResponse, OcrQueueStatus
from ocrforge_web.services import ocr_service

logger = logging.getLogger("ocrforge_web.ocr_router")

router = APIRouter(tags=["ocr"])

_ALLOWED_TYPES = {"image/jpeg", "image/jpg", "image/png", "image/webp"}
_ALLOWED_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}


@router.get("/ocr/queue", response_model=OcrQueueStatus)
async def ocr_queue() -> OcrQueueStatus:
    return OcrQueueStatus(depth=ocr_service.queue_depth())


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
        text = await ocr_service.run_ocr(tmp_path)
        latency_ms = int((time.time() - t0) * 1000)
    finally:
        try:
            tmp_path.unlink()
        except FileNotFoundError:
            pass

    return OcrResponse(text=text, char_count=len(text), latency_ms=latency_ms)
