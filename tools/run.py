from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path


def parse_devices(raw: str) -> list[str]:
    devices = [item.strip() for item in raw.split(",") if item.strip()]
    if not devices:
        raise ValueError("--devices must contain at least one device id, e.g. 0 or 0,1")
    for device in devices:
        if not device.isdigit():
            raise ValueError(f"Invalid device id {device!r}; expected comma-separated integers.")
    return devices


def hydra_devices_override(devices: list[str]) -> str:
    return "parallel.devices=[" + ",".join(devices) + "]"


def logical_devices(physical_devices: list[str]) -> list[str]:
    return [str(index) for index, _ in enumerate(physical_devices)]


def requested_parallel_mode(overrides: list[str]) -> str:
    for item in reversed(overrides):
        if item.startswith("parallel="):
            return item.split("=", 1)[1]
        if item.startswith("parallel.mode="):
            return item.split("=", 1)[1]
    return "data"


TRAIN_OVERRIDE_ALIASES = {
    "max_step": "train.max_steps",
    "max_steps": "train.max_steps",
    "batch_size": "train.batch_size",
    "grad_accum": "train.gradient_accumulation_steps",
    "gradient_accumulation_steps": "train.gradient_accumulation_steps",
    "eval_every_steps": "train.eval_every_steps",
}


def normalize_overrides(entry: str, overrides: list[str]) -> list[str]:
    if entry != "train":
        return overrides
    normalized = []
    for item in overrides:
        if "=" not in item:
            normalized.append(item)
            continue
        key, value = item.split("=", 1)
        normalized.append(f"{TRAIN_OVERRIDE_ALIASES.get(key, key)}={value}")
    return normalized


def main() -> None:
    argv = sys.argv[1:]
    if not argv or argv[0] not in {"train", "evaluate", "predict"}:
        raise SystemExit("Usage: run.py {train,evaluate,predict} --devices 0,1 [--conda-env ENV] [--dry-run] [Hydra overrides...]")
    entry = argv[0]
    rest = argv[1:]

    parser = argparse.ArgumentParser(
        description="Launch OCRForge train/evaluate with torchrun when multiple devices are requested."
    )
    parser.add_argument("--devices", required=True, help="Comma-separated GPU ids, e.g. 0 or 0,1,2,3.")
    parser.add_argument("--conda-env", default="", help="Optional conda env name, e.g. deepseek-ocr2-maca.")
    parser.add_argument("--dry-run", action="store_true", help="Print the resolved command without running it.")
    args, overrides = parser.parse_known_args(rest)

    overrides = normalize_overrides(entry, [item for item in overrides if item != "--"])
    devices = parse_devices(args.devices)
    visible_devices = logical_devices(devices)
    parallel_mode = requested_parallel_mode(overrides)
    repo_root = Path(__file__).resolve().parents[2]
    script = repo_root / "CultureCourse/tools" / f"{entry}.py"
    overrides.append(hydra_devices_override(visible_devices))

    use_torchrun = len(devices) > 1 and parallel_mode in {"data", "tensor"}
    if not use_torchrun:
        python_executable = "python" if args.conda_env else sys.executable
        cmd = [python_executable, str(script), *overrides]
    else:
        cmd = [
            "torchrun",
            "--standalone",
            f"--nproc_per_node={len(devices)}",
            str(script),
            *overrides,
        ]

    if args.conda_env:
        cmd = ["conda", "run", "--no-capture-output", "-n", args.conda_env, *cmd]

    env = os.environ.copy()
    env["CUDA_VISIBLE_DEVICES"] = ",".join(devices)
    env["PYTHONUNBUFFERED"] = "1"
    env.setdefault("OCRFORGE_RUN_STAMP", datetime.now().strftime("%Y%m%d-%H%M%S"))

    printable = f"CUDA_VISIBLE_DEVICES={env['CUDA_VISIBLE_DEVICES']} " + " ".join(cmd)
    print(printable, flush=True)
    if args.dry_run:
        return
    raise SystemExit(subprocess.run(cmd, cwd=str(repo_root), env=env).returncode)


if __name__ == "__main__":
    main()
