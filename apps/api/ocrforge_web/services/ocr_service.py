from __future__ import annotations

import asyncio
import logging
import os
import time
from pathlib import Path
from typing import Any

from PIL import Image
from omegaconf import DictConfig, OmegaConf

logger = logging.getLogger("ocrforge_web.ocr")

_MODULE: Any | None = None
_LOCK = asyncio.Lock()
# 单卡串行下的等待人数：waiting = 进入 run_ocr 但还没拿到 _LOCK 的请求数（含正在跑的那位）
_WAITING = 0
_WAITING_LOCK = asyncio.Lock()


def is_loaded() -> bool:
    return _MODULE is not None


def queue_depth() -> int:
    """当前正在进行 + 等待中的 OCR 请求总数。0 表示空闲。"""
    return _WAITING


def _build_module(settings):
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
    global _MODULE
    if _MODULE is not None:
        return
    if os.environ.get("OCRFORGE_WEB_SKIP_OCR", "").lower() in {"1", "true", "yes"}:
        logger.warning("OCRFORGE_WEB_SKIP_OCR set, skipping model load")
        return
    _MODULE = await asyncio.to_thread(_build_module, settings)
    if settings.ocr_warmup:
        await asyncio.to_thread(_warmup, _MODULE)


async def shutdown() -> None:
    global _MODULE
    _MODULE = None


async def run_ocr(image_path: Path) -> str:
    """串行化：单卡同时只跑一个推理，其余请求按到达顺序排队。

    `_WAITING` 在拿锁之前 ++、释放锁之后 --，让 /api/ocr/queue 能反映真实队伍长度。
    """
    if _MODULE is None:
        raise RuntimeError("OCR model not loaded")

    global _WAITING
    async with _WAITING_LOCK:
        _WAITING += 1
    try:
        async with _LOCK:
            return await asyncio.to_thread(_MODULE.generate_page, image_path, None, None, False)
    finally:
        async with _WAITING_LOCK:
            _WAITING -= 1
