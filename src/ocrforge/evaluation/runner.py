from __future__ import annotations

from omegaconf import DictConfig

from ocrforge.data import build_dataset
from ocrforge.evaluation.metrics import aggregate_metrics, text_metrics
from ocrforge.evaluation.writers import write_json, write_jsonl
from ocrforge.models import build_model_module
from ocrforge.parallel import DistributedProgress, barrier, cleanup_distributed, init_distributed, shard_sequence
from ocrforge.processing import get_prompt
from ocrforge.runtime.run import RunContext


def _should_save_sample(save_samples: object, global_index: int) -> bool:
    if isinstance(save_samples, bool):
        return save_samples
    if isinstance(save_samples, int):
        return global_index <= save_samples
    return False


def run_evaluation(cfg: DictConfig, context: RunContext) -> dict:
    dist = init_distributed()
    dataset = build_dataset(cfg.data, context.project_root)
    model = build_model_module(cfg.model, context.project_root).apply_parallel(cfg.parallel, "evaluate", dist.device)
    prompt = get_prompt(str(cfg.eval.prompt_name))
    keep_ascii = bool(cfg.eval.normalize.keep_ascii)

    records = []
    metric_items = []
    limit = cfg.eval.get("limit")
    all_samples = dataset.samples[:limit] if limit else dataset.samples
    samples = shard_sequence(all_samples, dist)
    save_samples = cfg.eval.get("save_samples", False)
    progress = DistributedProgress(
        total=len(all_samples),
        context=dist,
        desc="evaluate",
        enabled=bool(cfg.logging.progress.enabled),
        sync_every=int(cfg.logging.progress.sync_every),
        refresh_seconds=float(cfg.logging.progress.get("refresh_seconds", 1.0)),
    )
    try:
        for index, sample in enumerate(samples, start=1):
            global_index = dist.rank + (index - 1) * dist.world_size + 1
            save_sample = _should_save_sample(save_samples, global_index)
            sample_dir = context.output_dir / "samples" / f"{global_index:06d}_{sample.image_path.stem}" if save_sample else None
            try:
                prediction = model.generate_page(sample.image_path, prompt, sample_dir, save_results=save_sample)
                metrics = text_metrics(prediction, sample.target_text, keep_ascii=keep_ascii)
                metric_items.append(metrics)
                records.append(
                    {
                        "index": index,
                        "global_index": global_index,
                        "rank": dist.rank,
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
                        "global_index": global_index,
                        "rank": dist.rank,
                        "ok": False,
                        "dataset": sample.dataset_name,
                        "split": sample.split,
                        "image": str(sample.image_path),
                        "error": repr(exc),
                    }
                )
                if bool(cfg.runtime.fail_fast):
                    raise
            finally:
                progress.update(1)
        progress.close()
    except BaseException:
        progress.close(wait=False)
        raise

    rank_predictions = context.output_dir / f"predictions_rank{dist.rank}.jsonl"
    rank_metrics = context.output_dir / f"metrics_rank{dist.rank}.json"
    rank_summary = aggregate_metrics(metric_items)
    rank_summary.update({"rank": dist.rank, "samples": len(samples)})
    write_jsonl(rank_predictions, records)
    write_json(rank_metrics, rank_summary)
    barrier(dist)

    if not dist.is_main:
        cleanup_distributed(dist)
        return rank_summary

    merged_records = []
    merged_metrics = []
    for rank in range(dist.world_size):
        path = context.output_dir / f"predictions_rank{rank}.jsonl"
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    import json

                    merged_records.append(json.loads(line))
        metrics_path = context.output_dir / f"metrics_rank{rank}.json"
        if metrics_path.exists():
            import json

            merged_metrics.append(json.loads(metrics_path.read_text(encoding="utf-8")))
    metric_records = [record["metrics"] for record in merged_records if record.get("ok")]
    summary = aggregate_metrics(metric_records)
    summary.update(
        {
            "samples": len(all_samples),
            "evaluated_records": len(metric_records),
            "world_size": dist.world_size,
            "rank_metrics": merged_metrics,
            "predictions": str(context.output_dir / "predictions.jsonl"),
        }
    )
    write_jsonl(context.output_dir / "predictions.jsonl", merged_records)
    write_json(context.output_dir / "metrics.json", summary)
    cleanup_distributed(dist)
    return summary
