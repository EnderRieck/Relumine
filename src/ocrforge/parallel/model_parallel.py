from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelParallelPlan:
    vision_device: int
    projector_device: int
    language_devices: tuple[int, ...]
    lm_head_device: int


def build_model_parallel_plan(cfg) -> ModelParallelPlan:
    partition = cfg.parallel.partition
    return ModelParallelPlan(
        vision_device=int(partition.vision),
        projector_device=int(partition.projector),
        language_devices=tuple(int(item) for item in partition.language),
        lm_head_device=int(partition.lm_head),
    )

