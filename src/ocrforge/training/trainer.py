from __future__ import annotations

from contextlib import nullcontext
import json
import random
from pathlib import Path
from typing import Any

import torch
from torch.nn.parallel import DistributedDataParallel
from omegaconf import DictConfig, OmegaConf

from ocrforge.data import build_dataset
from ocrforge.data.schemas import OCRSample
from ocrforge.evaluation.metrics import aggregate_metrics, text_metrics
from ocrforge.evaluation.writers import write_json, write_jsonl
from ocrforge.models import build_model_module
from ocrforge.models.finetune import apply_finetune_strategy
from ocrforge.parallel import DistributedProgress, barrier, check_parallel_compatibility, cleanup_distributed, init_distributed, shard_sequence
from ocrforge.processing import get_prompt
from ocrforge.runtime.run import RunContext
from ocrforge.training.plots import plot_train_run


def _save_checkpoint(
    module: Any,
    cfg: DictConfig,
    context: RunContext,
    name: str,
    optimizer: torch.optim.Optimizer,
    step: int,
) -> str:
    checkpoint_root = context.output_dir / str(cfg.train.get("checkpoint_dir", "checkpoints"))
    checkpoint_dir = checkpoint_root / name
    module.save_pretrained(checkpoint_dir)
    torch.save(
        {
            "step": step,
            "optimizer": optimizer.state_dict(),
            "train": OmegaConf.to_container(cfg.train, resolve=True),
        },
        checkpoint_dir / "trainer_state.pt",
    )
    return str(checkpoint_dir)


def _load_trainer_state(cfg: DictConfig, optimizer: torch.optim.Optimizer) -> int:
    checkpoint = cfg.train.get("resume_from_checkpoint")
    if not checkpoint:
        return 0
    state_path = Path(str(checkpoint)) / "trainer_state.pt"
    state = torch.load(state_path, map_location="cpu")
    optimizer.load_state_dict(state["optimizer"])
    return int(state.get("step", 0))


def _pad_1d(tensor: torch.Tensor, length: int, value: int) -> torch.Tensor:
    tensor = tensor.squeeze(0)
    if tensor.numel() == length:
        return tensor
    padding = torch.full((length - tensor.numel(),), value, dtype=tensor.dtype)
    return torch.cat([tensor, padding], dim=0)


def _collate_training_batches(batches: list[dict[str, Any]], pad_token_id: int) -> dict[str, Any]:
    max_length = max(int(batch["input_ids"].shape[1]) for batch in batches)
    input_ids = torch.stack([_pad_1d(batch["input_ids"], max_length, pad_token_id) for batch in batches], dim=0)
    attention_mask = torch.stack([_pad_1d(batch["attention_mask"], max_length, 0) for batch in batches], dim=0)
    images_seq_mask = torch.stack([_pad_1d(batch["images_seq_mask"], max_length, 0).bool() for batch in batches], dim=0)
    labels = torch.stack([_pad_1d(batch["labels"], max_length, -100) for batch in batches], dim=0)
    images = [item for batch in batches for item in batch["images"]]
    images_spatial_crop = torch.cat([batch["images_spatial_crop"] for batch in batches], dim=0)
    return {
        "input_ids": input_ids,
        "attention_mask": attention_mask,
        "images": images,
        "images_seq_mask": images_seq_mask,
        "images_spatial_crop": images_spatial_crop,
        "labels": labels,
    }


def _collate_module_training_batches(module: Any, batches: list[dict[str, Any]], pad_token_id: int) -> dict[str, Any]:
    if hasattr(module, "collate_training_batches"):
        return module.collate_training_batches(batches, pad_token_id)
    return _collate_training_batches(batches, pad_token_id)


def _epoch_samples(samples: list[OCRSample], cfg: DictConfig, rank: int, epoch: int) -> list[OCRSample]:
    items = list(samples)
    if bool(cfg.data.get("shuffle", False)):
        rng = random.Random(int(cfg.seed) + rank * 1009 + epoch)
        rng.shuffle(items)
    return items


class SampleCycler:
    def __init__(self, samples: list[OCRSample], cfg: DictConfig, rank: int):
        if not samples:
            raise RuntimeError(f"Rank {rank} has no training samples. Reduce world size or use a larger dataset.")
        self.samples = samples
        self.cfg = cfg
        self.rank = rank
        self.epoch = 0
        self.position = 0
        self.current = _epoch_samples(samples, cfg, rank, self.epoch)
        self.seen = 0

    def next(self, count: int) -> list[OCRSample]:
        batch = []
        while len(batch) < count:
            if self.position >= len(self.current):
                self.epoch += 1
                self.position = 0
                self.current = _epoch_samples(self.samples, self.cfg, self.rank, self.epoch)
            batch.append(self.current[self.position])
            self.position += 1
            self.seen += 1
        return batch


def _build_eval_dataset_cfg(cfg: DictConfig) -> DictConfig:
    data_cfg = OmegaConf.create(OmegaConf.to_container(cfg.data, resolve=True))
    data_cfg.split = str(cfg.train.get("eval_split", "test"))
    eval_limit = cfg.train.get("eval_limit")
    if eval_limit is not None:
        data_cfg.limit = int(eval_limit)
    return data_cfg


def _run_step_evaluation(module: Any, cfg: DictConfig, context: RunContext, step: int) -> dict[str, Any]:
    eval_dir = context.output_dir / "eval" / f"step_{step:06d}"
    eval_dir.mkdir(parents=True, exist_ok=True)
    dataset = build_dataset(_build_eval_dataset_cfg(cfg), context.project_root)
    prompt = get_prompt(str(cfg.eval.prompt_name))
    keep_ascii = bool(cfg.eval.normalize.keep_ascii)
    records = []
    metrics_items = []
    for index, sample in enumerate(dataset.samples, start=1):
        try:
            prediction = module.generate_page(sample.image_path, prompt)
            metrics = text_metrics(prediction, sample.target_text, keep_ascii=keep_ascii)
            metrics_items.append(metrics)
            records.append(
                {
                    "index": index,
                    "ok": True,
                    "dataset": sample.dataset_name,
                    "split": sample.split,
                    "image": str(sample.image_path),
                    "gt": str(sample.gt_path) if sample.gt_path else None,
                    "prediction": prediction,
                    "target": sample.target_text,
                    "metrics": metrics,
                }
            )
        except Exception as exc:
            records.append(
                {
                    "index": index,
                    "ok": False,
                    "dataset": sample.dataset_name,
                    "split": sample.split,
                    "image": str(sample.image_path),
                    "error": repr(exc),
                }
            )
    summary = aggregate_metrics(metrics_items)
    summary.update({"step": step, "samples": len(dataset.samples), "predictions": str(eval_dir / "predictions.jsonl")})
    write_jsonl(eval_dir / "predictions.jsonl", records)
    write_json(eval_dir / "metrics.json", summary)
    module.train()
    return summary


def run_training(cfg: DictConfig, context: RunContext) -> dict:
    dist = init_distributed()
    compat = check_parallel_compatibility(cfg, "train")
    (context.output_dir / "parallel_compat.json").write_text(
        json.dumps(compat, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    if not compat["supported"]:
        raise RuntimeError(compat["message"])

    dataset = build_dataset(cfg.data, context.project_root)
    if not dataset:
        raise RuntimeError("Training dataset is empty.")

    module = build_model_module(cfg.model, context.project_root).apply_parallel(cfg.parallel, "train", dist.device)
    if not getattr(module, "supports_training", True):
        raise RuntimeError(f"Model backend {cfg.model.name!r} does not support training in OCRForge yet.")
    module.model = apply_finetune_strategy(module.model, cfg.train)
    module.train()

    if dist.enabled and str(cfg.parallel.mode) == "data":
        module.model = DistributedDataParallel(
            module.model,
            device_ids=[dist.local_rank],
            output_device=dist.local_rank,
            find_unused_parameters=True,
        )

    device = dist.device
    optimizer = torch.optim.AdamW(
        [parameter for parameter in module.model.parameters() if parameter.requires_grad],
        lr=float(cfg.train.learning_rate),
        weight_decay=float(cfg.train.weight_decay),
    )
    prompt = get_prompt(str(cfg.eval.prompt_name))
    max_steps = int(cfg.train.max_steps)
    batch_size = int(cfg.train.get("batch_size", 1))
    grad_accum_steps = int(cfg.train.get("gradient_accumulation_steps", 1))
    max_grad_norm = float(cfg.train.get("max_grad_norm", 0.0) or 0.0)
    eval_every_steps = int(cfg.train.get("eval_every_steps", 0) or 0)
    save_every_steps = int(cfg.train.get("save_every_steps", 0) or 0)
    metrics_path = context.output_dir / f"train_metrics_rank{dist.rank}.jsonl"
    step = _load_trainer_state(cfg, optimizer)
    start_step = step
    local_samples = shard_sequence(dataset.samples, dist)
    sample_cycler = SampleCycler(local_samples, cfg, dist.rank)
    tokenizer = getattr(module, "tokenizer", None) or getattr(getattr(module, "processor", None), "tokenizer", None)
    pad_token_id = tokenizer.pad_token_id if tokenizer is not None and tokenizer.pad_token_id is not None else 0
    saved_checkpoints = []
    eval_summaries = []
    progress = DistributedProgress(
        total=max(max_steps - start_step, 0),
        context=dist,
        desc="train",
        enabled=bool(cfg.logging.progress.enabled),
        sync_every=int(cfg.logging.progress.sync_every),
        refresh_seconds=float(cfg.logging.progress.get("refresh_seconds", 1.0)),
        aggregate="rank0",
    )
    with metrics_path.open("w", encoding="utf-8") as handle:
        while step < max_steps:
            optimizer.zero_grad(set_to_none=True)
            micro_losses = []
            micro_sample_names = []
            for accumulation_index in range(grad_accum_steps):
                samples = sample_cycler.next(batch_size)
                raw_batches = [module.build_training_batch(sample.image_path, prompt, sample.target_text) for sample in samples]
                batch = _collate_module_training_batches(module, raw_batches, pad_token_id)
                batch = module.move_batch_to_device(batch, device)
                sync_context = (
                    module.model.no_sync()
                    if isinstance(module.model, DistributedDataParallel) and accumulation_index < grad_accum_steps - 1
                    else nullcontext()
                )
                with sync_context:
                    outputs = module.model(**batch)
                    loss = outputs.loss
                    (loss / grad_accum_steps).backward()
                micro_losses.append(float(loss.detach().cpu()))
                micro_sample_names.extend(str(sample.image_path) for sample in samples)

            if max_grad_norm > 0:
                torch.nn.utils.clip_grad_norm_(
                    [parameter for parameter in module.model.parameters() if parameter.requires_grad],
                    max_grad_norm,
                )
            optimizer.step()
            step += 1
            record = {
                "step": step,
                "rank": dist.rank,
                "loss": sum(micro_losses) / max(len(micro_losses), 1),
                "micro_batch_size": batch_size,
                "gradient_accumulation_steps": grad_accum_steps,
                "local_batch_size": batch_size * grad_accum_steps,
                "global_batch_size": batch_size * grad_accum_steps * dist.world_size,
                "epoch": sample_cycler.epoch,
                "samples_seen": sample_cycler.seen,
                "sample_count": len(micro_sample_names),
                "images": micro_sample_names,
            }
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
            handle.flush()
            progress.update(1)

            if eval_every_steps > 0 and step % eval_every_steps == 0:
                barrier(dist)
                if dist.rank == 0:
                    eval_summaries.append(_run_step_evaluation(module, cfg, context, step))
                barrier(dist)
                if save_every_steps > 0 and step % save_every_steps == 0:
                    barrier(dist)
                    if dist.rank == 0:
                        saved_checkpoints.append(_save_checkpoint(module, cfg, context, f"step_{step:06d}", optimizer, step))
                    barrier(dist)
    progress.close()

    if dist.rank == 0 and bool(cfg.train.get("save_final", True)):
        saved_checkpoints.append(_save_checkpoint(module, cfg, context, "final", optimizer, step))

    rank_summary = {
        "steps": step,
        "start_step": start_step,
        "rank": dist.rank,
        "world_size": dist.world_size,
        "train_metrics": str(metrics_path),
        "checkpoints": saved_checkpoints,
        "evals": eval_summaries,
        "global_batch_size": batch_size * grad_accum_steps * dist.world_size,
    }
    (context.output_dir / f"metrics_rank{dist.rank}.json").write_text(
        json.dumps(rank_summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    barrier(dist)

    if dist.rank == 0:
        rank_metrics = []
        for rank in range(dist.world_size):
            path = context.output_dir / f"metrics_rank{rank}.json"
            if path.exists():
                rank_metrics.append(json.loads(path.read_text(encoding="utf-8")))
        summary = {
            "steps": max((item["steps"] for item in rank_metrics), default=step),
            "start_step": start_step,
            "world_size": dist.world_size,
            "checkpoints": saved_checkpoints,
            "evals": eval_summaries,
            "global_batch_size": batch_size * grad_accum_steps * dist.world_size,
            "rank_metrics": rank_metrics,
        }
        if bool(cfg.train.get("plot_curve", True)):
            try:
                summary["loss_curve"] = plot_train_run(context.output_dir)
            except Exception as exc:
                summary["loss_curve_error"] = repr(exc)
        (context.output_dir / "metrics.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        cleanup_distributed(dist)
        return summary

    cleanup_distributed(dist)
    return rank_summary
