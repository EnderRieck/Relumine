from __future__ import annotations

import asyncio
import json
import logging
import mimetypes
import os
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Any

from PIL import Image

logger = logging.getLogger("ocrforge_web.ocr")

_MODULE: Any | None = None
_BACKEND: str | None = None
_REMOTE_OCR_URL: str | None = None
_REMOTE_OCR_TIMEOUT: float = 120.0
_LOCK = asyncio.Lock()
# 单卡串行下的等待人数：waiting = 进入 run_ocr 但还没拿到 _LOCK 的请求数（含正在跑的那位）
_WAITING = 0
_WAITING_LOCK = asyncio.Lock()


def is_loaded() -> bool:
    return _MODULE is not None or _BACKEND == "vision"


def queue_depth() -> int:
    """当前正在进行 + 等待中的 OCR 请求总数。0 表示空闲。"""
    return _WAITING


def _build_module(settings):
    from omegaconf import OmegaConf
    from ocrforge.models.factory import build_model_module

    model_cfg = OmegaConf.create({
        "name": "paddleocr_vl",
        "path": str(settings.paddle_ckpt),
        "trust_remote_code": True,
        "local_files_only": True,
        "torch_dtype": settings.paddle_dtype,
        "attn_implementation": settings.paddle_attn,
        "device": settings.paddle_device,
        "task": settings.paddle_task,
        "prompt": "OCR:",
        "max_pixels": settings.paddle_max_pixels,
        "max_new_tokens": settings.paddle_max_new_tokens,
        "use_cache": True,
        "do_sample": False,
        "num_beams": 1,
    })
    parallel_cfg = OmegaConf.create({"mode": "data"})

    logger.info("loading PaddleOCR-VL from %s (dtype=%s, attn=%s, device=%s)",
                settings.paddle_ckpt, settings.paddle_dtype, settings.paddle_attn, settings.paddle_device)
    t0 = time.time()
    module = build_model_module(model_cfg, settings.project_root)
    module = module.apply_parallel(parallel_cfg, "evaluate", settings.paddle_device)
    logger.info("model loaded in %.1fs", time.time() - t0)
    return module


def _vision_available() -> bool:
    try:
        import Vision  # noqa: F401
        from Foundation import NSURL  # noqa: F401
    except Exception as e:
        logger.warning("macOS Vision OCR unavailable: %s", e)
        return False
    return True


def _run_vision_ocr(image_path: Path) -> str:
    import Vision
    from Foundation import NSURL

    lines: list[str] = []
    errors: list[Any] = []

    def completion_handler(request, error):
        if error:
            errors.append(error)
            return
        for observation in request.results() or []:
            candidates = observation.topCandidates_(1)
            if candidates:
                text = str(candidates[0].string()).strip()
                if text:
                    lines.append(text)

    request = Vision.VNRecognizeTextRequest.alloc().initWithCompletionHandler_(completion_handler)
    request.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)
    request.setUsesLanguageCorrection_(True)
    request.setRecognitionLanguages_(["zh-Hant", "zh-Hans", "en-US"])

    url = NSURL.fileURLWithPath_(str(image_path))
    handler = Vision.VNImageRequestHandler.alloc().initWithURL_options_(url, {})
    ok, error = handler.performRequests_error_([request], None)
    if not ok or errors:
        raise RuntimeError(f"macOS Vision OCR failed: {error or errors[0]}")
    return "\n".join(lines).strip()


def _run_remote_ocr(image_path: Path) -> str:
    if not _REMOTE_OCR_URL:
        raise RuntimeError("remote OCR URL is not configured")

    boundary = f"----relumine-ocr-{uuid.uuid4().hex}"
    content_type = mimetypes.guess_type(str(image_path))[0] or "application/octet-stream"
    filename = image_path.name
    file_bytes = image_path.read_bytes()
    body = b"".join(
        [
            f"--{boundary}\r\n".encode(),
            f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'.encode(),
            f"Content-Type: {content_type}\r\n\r\n".encode(),
            file_bytes,
            b"\r\n",
            f"--{boundary}--\r\n".encode(),
        ]
    )
    request = urllib.request.Request(
        _REMOTE_OCR_URL,
        data=body,
        method="POST",
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    try:
        with urllib.request.urlopen(request, timeout=_REMOTE_OCR_TIMEOUT) as response:
            payload = response.read()
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"remote OCR HTTP {e.code}: {detail}") from e

    text = payload.decode("utf-8", errors="replace").strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return text
    if isinstance(data, dict):
        if isinstance(data.get("text"), str):
            return data["text"].strip()
        if isinstance(data.get("result"), str):
            return data["result"].strip()
    return text


def _warmup(module) -> None:
    img = Image.new("RGB", (32, 32), color=(255, 255, 255))
    tmp = Path("/tmp/ocrforge_web_warmup.png")
    img.save(tmp)
    try:
        t0 = time.time()
        module.generate_page(tmp, None, None, False)
        logger.info("warmup inference in %.1fs", time.time() - t0)
    except Exception as e:
        logger.warning("warmup failed (non-fatal): %s", e)
    finally:
        try:
            tmp.unlink()
        except FileNotFoundError:
            pass


async def startup(settings) -> None:
    global _BACKEND, _MODULE, _REMOTE_OCR_TIMEOUT, _REMOTE_OCR_URL
    if _MODULE is not None:
        return
    if os.environ.get("OCRFORGE_WEB_SKIP_OCR", "").lower() in {"1", "true", "yes"}:
        logger.warning("OCRFORGE_WEB_SKIP_OCR set, skipping model load")
        return

    backend = settings.ocr_backend.lower()
    _REMOTE_OCR_URL = settings.remote_ocr_url
    _REMOTE_OCR_TIMEOUT = settings.remote_ocr_timeout

    if settings.remote_ocr_url and backend in {"auto", "remote"}:
        _BACKEND = "remote"
        logger.info("using remote OCR backend: %s", settings.remote_ocr_url)
        return

    if backend in {"auto", "paddle", "paddleocr", "paddleocr_vl"}:
        try:
            if not settings.paddle_ckpt.exists():
                raise FileNotFoundError(f"PaddleOCR-VL checkpoint not found: {settings.paddle_ckpt}")
            _MODULE = await asyncio.to_thread(_build_module, settings)
            _BACKEND = "paddleocr_vl"
            if settings.ocr_warmup:
                await asyncio.to_thread(_warmup, _MODULE)
            return
        except Exception as e:
            if backend != "auto":
                raise
            logger.warning("PaddleOCR-VL unavailable, falling back to macOS Vision OCR: %s", e)

    if backend in {"auto", "vision", "macos_vision"}:
        if not _vision_available():
            raise RuntimeError("No OCR backend available: PaddleOCR-VL failed and macOS Vision is unavailable")
        _BACKEND = "vision"
        logger.info("using macOS Vision OCR backend")
        return

    raise ValueError(f"unknown OCR backend: {settings.ocr_backend!r}")


async def shutdown() -> None:
    global _BACKEND, _MODULE, _REMOTE_OCR_TIMEOUT, _REMOTE_OCR_URL
    _MODULE = None
    _BACKEND = None
    _REMOTE_OCR_URL = None
    _REMOTE_OCR_TIMEOUT = 120.0


async def run_ocr(image_path: Path) -> str:
    """串行化：单卡同时只跑一个推理，其余请求按到达顺序排队。

    `_WAITING` 在拿锁之前 ++、释放锁之后 --，让 /api/ocr/queue 能反映真实队伍长度。
    """
    if _MODULE is None:
        if _BACKEND not in {"remote", "vision"}:
            raise RuntimeError("OCR model not loaded")

    global _WAITING
    async with _WAITING_LOCK:
        _WAITING += 1
    try:
        async with _LOCK:
            if _BACKEND == "remote":
                return await asyncio.to_thread(_run_remote_ocr, image_path)
            if _BACKEND == "vision":
                return await asyncio.to_thread(_run_vision_ocr, image_path)
            return await asyncio.to_thread(_MODULE.generate_page, image_path, None, None, False)
    finally:
        async with _WAITING_LOCK:
            _WAITING -= 1
