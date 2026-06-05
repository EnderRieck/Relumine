from __future__ import annotations

from _bootstrap import add_src_to_path

add_src_to_path()

import json

import hydra
from omegaconf import DictConfig

from ocrforge.evaluation.runner import run_evaluation
from ocrforge.parallel import check_parallel_compatibility
from ocrforge.runtime.run import prepare_run


@hydra.main(version_base=None, config_path="../configs", config_name="config")
def main(cfg: DictConfig) -> None:
    cfg.task = "evaluate"
    context = prepare_run(cfg)
    compat = check_parallel_compatibility(cfg, "evaluate")
    (context.output_dir / "parallel_compat.json").write_text(json.dumps(compat, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if not compat["supported"]:
        raise RuntimeError(compat["message"])
    summary = run_evaluation(cfg, context)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
