from __future__ import annotations

import json
import os
import platform
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from hydra.core.hydra_config import HydraConfig
from hydra.utils import get_original_cwd
from omegaconf import DictConfig, OmegaConf

from ocrforge.utils.paths import find_project_root, resolve_path


@dataclass(frozen=True)
class RunContext:
    project_root: Path
    output_dir: Path


def _cfg_to_container(cfg: DictConfig) -> Any:
    return OmegaConf.to_container(cfg, resolve=True, throw_on_missing=False)


def _collect_overrides() -> list[str]:
    if not HydraConfig.initialized():
        return []
    return list(HydraConfig.get().overrides.task)


def _synchronize_default_output_dir(raw_output_dir: str, overrides: list[str]) -> str:
    if any(item.startswith("runtime.output_dir=") or item.startswith("+runtime.output_dir=") for item in overrides):
        return raw_output_dir
    run_stamp = os.environ.get("OCRFORGE_RUN_STAMP")
    if not run_stamp:
        return raw_output_dir
    path = Path(raw_output_dir)
    name = re.sub(r"^\d{8}-\d{6}_", f"{run_stamp}_", path.name)
    return str(path.with_name(name))


def prepare_run(cfg: DictConfig) -> RunContext:
    original_cwd = Path(get_original_cwd()).resolve()
    configured_root = str(cfg.runtime.get("project_root", "auto"))
    project_root = find_project_root(original_cwd) if configured_root == "auto" else resolve_path(configured_root, original_cwd)
    overrides = _collect_overrides()
    synchronized_output_dir = _synchronize_default_output_dir(str(cfg.runtime.output_dir), overrides)
    cfg.runtime.output_dir = synchronized_output_dir
    output_dir = resolve_path(synchronized_output_dir, project_root)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "logs").mkdir(exist_ok=True)

    OmegaConf.save(config=cfg, f=output_dir / "config_resolved.yaml", resolve=True)
    (output_dir / "config_overrides.yaml").write_text(
        "\n".join(f"- {item}" for item in overrides) + ("\n" if overrides else "[]\n"),
        encoding="utf-8",
    )
    (output_dir / "command.txt").write_text(" ".join(sys.argv) + "\n", encoding="utf-8")
    env = {
        "python": sys.version,
        "platform": platform.platform(),
        "cwd": str(original_cwd),
        "project_root": str(project_root),
        "env": {
            key: os.environ.get(key)
            for key in ["CUDA_VISIBLE_DEVICES", "OCRFORGE_PROJECT_ROOT", "OCRFORGE_RUN_STAMP", "HF_ENDPOINT"]
            if os.environ.get(key) is not None
        },
        "config": _cfg_to_container(cfg),
    }
    (output_dir / "env.json").write_text(json.dumps(env, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    return RunContext(project_root=project_root, output_dir=output_dir)
