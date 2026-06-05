from __future__ import annotations

from _bootstrap import add_src_to_path

add_src_to_path()

import json

import hydra
from omegaconf import DictConfig

from ocrforge.data import build_dataset
from ocrforge.runtime.run import prepare_run


@hydra.main(version_base=None, config_path="../configs", config_name="config")
def main(cfg: DictConfig) -> None:
    cfg.task = "check_data"
    context = prepare_run(cfg)
    dataset = build_dataset(cfg.data, context.project_root)
    summary = {
        "dataset": cfg.data.name,
        "split": cfg.data.split,
        "samples": len(dataset),
        "first": None,
    }
    if len(dataset):
        first = dataset[0]
        summary["first"] = {
            "dataset": first.dataset_name,
            "image": str(first.image_path),
            "gt": str(first.gt_path) if first.gt_path else None,
            "target_chars": len(first.target_text),
            "boxes": len(first.boxes),
            "lines": len(first.lines),
        }
    (context.output_dir / "data_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
