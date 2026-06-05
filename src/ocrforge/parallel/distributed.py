from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass
from typing import Sequence, TypeVar

import torch
import torch.distributed as dist
from tqdm import tqdm

T = TypeVar("T")


@dataclass(frozen=True)
class DistributedContext:
    enabled: bool
    rank: int
    local_rank: int
    world_size: int
    device: torch.device

    @property
    def is_main(self) -> bool:
        return self.rank == 0


def init_distributed() -> DistributedContext:
    world_size = int(os.environ.get("WORLD_SIZE", "1"))
    rank = int(os.environ.get("RANK", "0"))
    local_rank = int(os.environ.get("LOCAL_RANK", "0"))
    enabled = world_size > 1
    if torch.cuda.is_available():
        torch.cuda.set_device(local_rank)
        device = torch.device(f"cuda:{local_rank}")
    else:
        device = torch.device("cpu")
    if enabled and not dist.is_initialized():
        backend = "nccl" if torch.cuda.is_available() else "gloo"
        dist.init_process_group(backend=backend)
    return DistributedContext(enabled=enabled, rank=rank, local_rank=local_rank, world_size=world_size, device=device)


def shard_sequence(items: Sequence[T], context: DistributedContext) -> list[T]:
    if not context.enabled:
        return list(items)
    return list(items)[context.rank :: context.world_size]


def barrier(context: DistributedContext) -> None:
    if context.enabled and dist.is_initialized():
        if context.device.type == "cuda":
            try:
                dist.barrier(device_ids=[context.local_rank])
                return
            except TypeError:
                pass
        dist.barrier()


def cleanup_distributed(context: DistributedContext) -> None:
    if context.enabled and dist.is_initialized():
        dist.destroy_process_group()


class DistributedProgress:
    def __init__(
        self,
        total: int,
        context: DistributedContext,
        desc: str,
        enabled: bool = True,
        sync_every: int = 1,
        refresh_seconds: float = 1.0,
        aggregate: str = "sum",
    ):
        self.total = total
        self.context = context
        self.enabled = enabled
        self.sync_every = max(int(sync_every), 1)
        self.refresh_seconds = max(float(refresh_seconds), 0.1)
        self.aggregate = aggregate
        self.local_count = 0
        self._lock = threading.Lock()
        self.last_displayed = 0
        self.bar = tqdm(total=total, desc=desc, disable=not enabled or not context.is_main)
        self._progress_group = None
        self._progress_device = context.device
        self._thread: threading.Thread | None = None

        if enabled and context.enabled and dist.is_initialized() and total > 0 and aggregate == "sum":
            self._progress_group = self._create_progress_group()
            self._thread = threading.Thread(target=self._sync_loop, name=f"{desc}-progress", daemon=True)
            self._thread.start()

    def update(self, n: int = 1, force: bool = False) -> None:
        with self._lock:
            self.local_count += n
        if not self.enabled:
            return
        if self._thread is not None:
            return
        if not force and self.local_count % self.sync_every != 0:
            return
        if self.context.is_main:
            self._display(self.local_count)

    def close(self, wait: bool = True) -> None:
        if self.enabled:
            if self._thread is not None:
                if not wait:
                    if self.context.is_main:
                        self.bar.close()
                    return
                self._thread.join()
                if self._progress_group is not None:
                    dist.destroy_process_group(self._progress_group)
            else:
                self.update(0, force=True)
            if self.context.is_main:
                self.bar.close()

    def _create_progress_group(self) -> dist.ProcessGroup:
        try:
            group = dist.new_group(backend="gloo")
            self._progress_device = torch.device("cpu")
            return group
        except Exception:
            group = dist.new_group()
            self._progress_device = self.context.device
            return group

    def _sync_loop(self) -> None:
        while True:
            with self._lock:
                local_count = self.local_count
            tensor = torch.tensor([local_count], dtype=torch.long, device=self._progress_device)
            dist.all_reduce(tensor, op=dist.ReduceOp.SUM, group=self._progress_group)
            global_count = int(tensor.item())
            if self.context.is_main:
                self._display(global_count)
            if global_count >= self.total:
                break
            time.sleep(self.refresh_seconds)

    def _display(self, count: int) -> None:
        current = min(self.total, count)
        self.bar.update(max(0, current - self.last_displayed))
        self.last_displayed = current
