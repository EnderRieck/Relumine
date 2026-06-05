from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TensorParallelPlan:
    tensor_parallel_size: int


def build_tensor_parallel_plan(cfg) -> TensorParallelPlan:
    return TensorParallelPlan(tensor_parallel_size=int(cfg.parallel.tensor_parallel_size))

