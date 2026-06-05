from __future__ import annotations

from _bootstrap import add_src_to_path

add_src_to_path()

import json

import hydra
from omegaconf import DictConfig

from ocrforge.runtime.run import prepare_run
from ocrforge.training.trainer import run_training


@hydra.main(version_base=None, config_path="../configs", config_name="config")
def main(cfg: DictConfig) -> None:
    cfg.task = "train"
    context = prepare_run(cfg)
    summary = run_training(cfg, context)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
