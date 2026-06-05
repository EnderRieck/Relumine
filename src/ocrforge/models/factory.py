from __future__ import annotations

from pathlib import Path

from omegaconf import DictConfig

from ocrforge.models.deepseek_ocr2 import DeepSeekOCR2Module
from ocrforge.models.paddleocr_vl import PaddleOCRVLModule


def build_model_module(cfg: DictConfig, project_root: Path):
    name = str(cfg.name)
    if name == "deepseek_ocr2":
        return DeepSeekOCR2Module(cfg, project_root)
    if name == "paddleocr_vl":
        return PaddleOCRVLModule(cfg, project_root)
    raise ValueError(f"Unknown model backend: {name}")
