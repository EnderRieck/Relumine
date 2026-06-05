from __future__ import annotations

import importlib.util

import torch
from omegaconf import DictConfig


def check_parallel_compatibility(cfg: DictConfig, task: str) -> dict:
    mode = str(cfg.parallel.mode)
    devices = list(cfg.parallel.get("devices", []))
    cuda_count = torch.cuda.device_count() if torch.cuda.is_available() else 0
    report = {
        "mode": mode,
        "task": task,
        "cuda_available": torch.cuda.is_available(),
        "cuda_count": cuda_count,
        "devices": devices,
        "backend": str(cfg.parallel.get("backend", "")),
        "supported": False,
        "message": "",
    }

    if devices and cuda_count and max(int(device) for device in devices) >= cuda_count:
        report["message"] = f"Configured devices {devices} exceed available CUDA device count {cuda_count}."
        return report

    if mode == "data":
        report["supported"] = True
        report["message"] = "Data parallel mode is supported via torch.distributed/DeepSpeed configuration."
        return report

    if mode == "model":
        has_accelerate = importlib.util.find_spec("accelerate") is not None
        report["supported"] = has_accelerate
        report["message"] = (
            "Model parallel mode is supported via accelerate.dispatch_model module device maps."
            if has_accelerate
            else "Model parallel mode requires accelerate, which is not importable."
        )
        return report

    if mode == "pipeline":
        has_accelerate = importlib.util.find_spec("accelerate") is not None
        report["supported"] = has_accelerate
        report["message"] = (
            "Pipeline mode is supported as staged layer placement via accelerate.dispatch_model; concurrent microbatch scheduling is not enabled."
            if has_accelerate
            else "Pipeline mode requires accelerate, which is not importable."
        )
        return report

    if mode == "tensor":
        has_deepspeed = importlib.util.find_spec("deepspeed") is not None
        report["supported"] = bool(has_deepspeed and task == "evaluate")
        if report["supported"]:
            report["message"] = "Tensor mode is supported for evaluation through deepspeed.init_inference tensor parallel."
        elif has_deepspeed:
            report["message"] = "Tensor mode is currently evaluation-only; DeepSpeed tensor-parallel training is not enabled for this DeepSeek remote-code model."
        else:
            report["message"] = "Tensor mode requires deepspeed, which is not importable."
        return report

    report["message"] = f"Unknown parallel mode: {mode}"
    return report
