from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from omegaconf import DictConfig

from ocrforge.data.readers import (
    read_annotation_boxes,
    read_class_label,
    read_class_label_lines,
    read_jsonl,
    read_page_xml,
    resolve_manifest_image,
)
from ocrforge.data.schemas import OCRSample
from ocrforge.utils.paths import resolve_path


class OCRDataset(Sequence[OCRSample]):
    def __init__(self, samples: list[OCRSample]):
        self.samples = samples

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, index: int) -> OCRSample:
        return self.samples[index]


def _apply_limit(samples: list[OCRSample], limit: int | None) -> list[OCRSample]:
    return samples[:limit] if limit else samples


def build_tkh_dataset(cfg: DictConfig, project_root: Path) -> OCRDataset:
    root = resolve_path(cfg.root, project_root)
    split = str(cfg.get("split", "train"))
    manifest = root / "splits" / f"{split}.jsonl"
    samples: list[OCRSample] = []
    for record in read_jsonl(manifest):
        image = resolve_manifest_image(record, project_root)
        stem = image.stem
        gt_path = root / "raw/Class_label" / f"{stem}.txt"
        ann_path = root / "raw/Annotations" / f"{stem}.txt"
        labels = read_class_label_lines(gt_path)
        samples.append(
            OCRSample(
                image_path=image,
                target_text="".join(labels),
                dataset_name="TKH",
                split=split,
                gt_path=gt_path,
                boxes=read_annotation_boxes(ann_path, labels, "xyxy"),
                meta=record,
            )
        )
    return OCRDataset(_apply_limit(samples, cfg.get("limit")))


def build_mth_dataset(cfg: DictConfig, project_root: Path) -> OCRDataset:
    root = resolve_path(cfg.root, project_root)
    split = str(cfg.get("split", "train"))
    manifest = root / "splits" / f"{split}.jsonl"
    samples: list[OCRSample] = []
    for record in read_jsonl(manifest):
        image = resolve_manifest_image(record, project_root)
        stem = image.stem
        gt_path = root / "raw/Class_label" / f"{stem}.txt"
        ann_path = root / "raw/Annotations" / f"{stem}.txt"
        labels = read_class_label_lines(gt_path)
        samples.append(
            OCRSample(
                image_path=image,
                target_text="".join(labels),
                dataset_name="MTH",
                split=split,
                gt_path=gt_path,
                boxes=read_annotation_boxes(ann_path, labels, "xywh"),
                meta=record,
            )
        )
    return OCRDataset(_apply_limit(samples, cfg.get("limit")))


def build_icdar_dataset(cfg: DictConfig, project_root: Path) -> OCRDataset:
    root = resolve_path(cfg.root, project_root)
    split = str(cfg.get("split", "train"))
    manifest = root / "splits" / f"{split}.jsonl"
    samples: list[OCRSample] = []
    for record in read_jsonl(manifest):
        image = resolve_manifest_image(record, project_root)
        gt_path = root / "ground_truth/xml" / f"{image.stem}.xml"
        lines = read_page_xml(gt_path)
        samples.append(
            OCRSample(
                image_path=image,
                target_text="".join(line.text for line in lines),
                dataset_name="ICDAR2019-HDRC-Chinese",
                split=split,
                gt_path=gt_path,
                lines=lines,
                meta=record,
            )
        )
    return OCRDataset(_apply_limit(samples, cfg.get("limit")))

