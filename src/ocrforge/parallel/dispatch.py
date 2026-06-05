from __future__ import annotations

from collections.abc import Iterable

import torch

from ocrforge.parallel.model_parallel import build_model_parallel_plan
from ocrforge.parallel.pipeline import build_pipeline_plan


def _cuda_name(device: int) -> str:
    return f"cuda:{device}" if torch.cuda.is_available() else "cpu"


def _language_layers(model) -> list[str]:
    layers = getattr(getattr(model, "model", None), "layers", None)
    if layers is None:
        return []
    return [f"model.layers.{index}" for index in range(len(layers))]


def _spread(items: list[str], devices: Iterable[int]) -> dict[str, str]:
    devices = list(devices)
    if not devices:
        raise ValueError("At least one language device is required.")
    return {name: _cuda_name(devices[index % len(devices)]) for index, name in enumerate(items)}


def build_model_device_map(model, cfg) -> dict[str, str]:
    plan = build_model_parallel_plan(cfg)
    device_map: dict[str, str] = {
        "model.sam_model": _cuda_name(plan.vision_device),
        "model.qwen2_model": _cuda_name(plan.vision_device),
        "model.projector": _cuda_name(plan.projector_device),
        "model.view_seperator": _cuda_name(plan.projector_device),
        "model.embed_tokens": _cuda_name(plan.projector_device),
        "model.norm": _cuda_name(plan.language_devices[-1]),
        "lm_head": _cuda_name(plan.lm_head_device),
    }
    device_map.update(_spread(_language_layers(model), plan.language_devices))
    return device_map


def build_pipeline_device_map(model, cfg) -> dict[str, str]:
    plan = build_pipeline_plan(cfg)
    devices = list(cfg.parallel.devices)
    if plan.stages > len(devices):
        raise ValueError(f"Pipeline stages ({plan.stages}) exceed configured devices ({devices}).")
    stage_devices = [int(devices[index]) for index in range(plan.stages)]
    layers = _language_layers(model)
    layer_devices = []
    for index, _ in enumerate(layers):
        stage = min((index * plan.stages) // max(len(layers), 1), plan.stages - 1)
        layer_devices.append(stage_devices[stage])
    device_map: dict[str, str] = {
        "model.sam_model": _cuda_name(stage_devices[plan.vision_stage]),
        "model.qwen2_model": _cuda_name(stage_devices[plan.vision_stage]),
        "model.projector": _cuda_name(stage_devices[plan.projector_stage]),
        "model.view_seperator": _cuda_name(stage_devices[plan.projector_stage]),
        "model.embed_tokens": _cuda_name(stage_devices[plan.projector_stage]),
        "model.norm": _cuda_name(stage_devices[-1]),
        "lm_head": _cuda_name(stage_devices[plan.lm_head_stage]),
    }
    device_map.update({name: _cuda_name(device) for name, device in zip(layers, layer_devices)})
    return device_map


def dispatch_with_device_map(model, device_map: dict[str, str]):
    from accelerate import dispatch_model

    return dispatch_model(model, device_map=device_map)
