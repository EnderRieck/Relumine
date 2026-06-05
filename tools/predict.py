from __future__ import annotations

from _bootstrap import add_src_to_path

add_src_to_path()

import json
from pathlib import Path

import hydra
from omegaconf import DictConfig

from ocrforge.models import build_model_module
from ocrforge.parallel import check_parallel_compatibility, cleanup_distributed, init_distributed
from ocrforge.processing import get_prompt
from ocrforge.runtime.run import prepare_run


def _required_path(cfg: DictConfig, key: str) -> Path:
    predict_cfg = cfg.get("predict")
    value = None if predict_cfg is None else predict_cfg.get(key)
    if value is None:
        raise SystemExit(
            f"predict.{key} is required, e.g. +predict.{key}=path/to/{'image' if key == 'image' else 'output.txt'}"
        )
    return Path(str(value)).expanduser()


@hydra.main(version_base=None, config_path="../configs", config_name="config")
def main(cfg: DictConfig) -> None:
    cfg.task = "predict"

    image_arg = _required_path(cfg, "image")
    output_arg = _required_path(cfg, "output")

    context = prepare_run(cfg)
    compat = check_parallel_compatibility(cfg, "evaluate")
    (context.output_dir / "parallel_compat.json").write_text(
        json.dumps(compat, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    if not compat["supported"]:
        raise RuntimeError(compat["message"])

    image_path = image_arg if image_arg.is_absolute() else (context.project_root / image_arg).resolve()
    output_path = output_arg if output_arg.is_absolute() else (context.project_root / output_arg).resolve()
    if not image_path.exists():
        raise FileNotFoundError(f"Image not found: {image_path}")

    dist = init_distributed()
    try:
        if not dist.is_main:
            return

        model = build_model_module(cfg.model, context.project_root).apply_parallel(
            cfg.parallel, "evaluate", dist.device
        )
        prompt = get_prompt(str(cfg.eval.prompt_name))
        prediction = model.generate_page(image_path, prompt, output_path=None, save_results=False)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(prediction, encoding="utf-8")

        summary = {
            "image": str(image_path),
            "output": str(output_path),
            "model": str(cfg.model.name),
            "model_path": str(cfg.model.get("path", "")),
            "prompt_name": str(cfg.eval.prompt_name),
            "chars": len(prediction),
            "run_dir": str(context.output_dir),
        }
        (context.output_dir / "prediction.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    finally:
        cleanup_distributed(dist)


if __name__ == "__main__":
    main()
