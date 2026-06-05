from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PipelinePlan:
    stages: int
    micro_batch_size: int
    vision_stage: int
    projector_stage: int
    lm_head_stage: int


def build_pipeline_plan(cfg) -> PipelinePlan:
    partition = cfg.parallel.partition
    return PipelinePlan(
        stages=int(cfg.parallel.stages),
        micro_batch_size=int(cfg.parallel.micro_batch_size),
        vision_stage=int(partition.vision_stage),
        projector_stage=int(partition.projector_stage),
        lm_head_stage=int(partition.lm_head_stage),
    )
