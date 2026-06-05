from __future__ import annotations

from pathlib import Path

from omegaconf import DictConfig, OmegaConf

from ocrforge.data.datasets import OCRDataset, build_icdar_dataset, build_mth_dataset, build_tkh_dataset


def _with_common(child: DictConfig, parent: DictConfig) -> DictConfig:
    merged = OmegaConf.create(OmegaConf.to_container(child, resolve=True))
    merged.split = parent.get("split", child.get("split", "train"))
    merged.limit = child.get("limit")
    merged.shuffle = parent.get("shuffle", child.get("shuffle", False))
    return merged


def build_dataset(cfg: DictConfig, project_root: Path) -> OCRDataset:
    name = str(cfg.name).lower()
    if name == "tkh":
        return build_tkh_dataset(cfg, project_root)
    if name == "mth":
        return build_mth_dataset(cfg, project_root)
    if name in {"icdar", "icdar2019", "icdar2019_hdrc"}:
        return build_icdar_dataset(cfg, project_root)
    if name == "mixed":
        samples = []
        for child in cfg.datasets:
            child_cfg = _with_common(child, cfg)
            samples.extend(build_dataset(child_cfg, project_root).samples)
        limit = cfg.get("limit")
        return OCRDataset(samples[:limit] if limit else samples)
    raise ValueError(f"Unknown dataset: {cfg.name}")
