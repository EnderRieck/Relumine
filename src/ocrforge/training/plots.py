from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path
from statistics import mean
from typing import Any


def load_train_metrics(run_dir: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in sorted(run_dir.glob("train_metrics_rank*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                record = json.loads(line)
                record["source"] = path.name
                records.append(record)
    records.sort(key=lambda item: (int(item.get("step", 0)), int(item.get("rank", 0))))
    return records


def aggregate_loss_by_step(records: list[dict[str, Any]]) -> list[dict[str, float]]:
    grouped: dict[int, list[float]] = defaultdict(list)
    for record in records:
        if "step" in record and "loss" in record:
            grouped[int(record["step"])].append(float(record["loss"]))
    return [{"step": step, "loss": mean(losses)} for step, losses in sorted(grouped.items())]


def write_loss_csv(rows: list[dict[str, float]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["step", "loss"])
        writer.writeheader()
        writer.writerows(rows)


def plot_loss_curve(rows: list[dict[str, float]], output_path: Path, title: str | None = None) -> None:
    if not rows:
        raise RuntimeError("No train loss records found.")

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    steps = [row["step"] for row in rows]
    losses = [row["loss"] for row in rows]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(9, 5), dpi=160)
    ax.plot(steps, losses, color="#2563eb", linewidth=1.8)
    ax.set_xlabel("Step")
    ax.set_ylabel("Loss")
    ax.set_title(title or "Training Loss")
    ax.grid(True, alpha=0.25)
    fig.tight_layout()
    fig.savefig(output_path)
    plt.close(fig)


def plot_train_run(
    run_dir: Path,
    output_path: Path | None = None,
    csv_path: Path | None = None,
) -> dict[str, str]:
    records = load_train_metrics(run_dir)
    rows = aggregate_loss_by_step(records)
    plot_path = output_path or run_dir / "loss_curve.png"
    resolved_csv_path = csv_path or run_dir / "loss_curve.csv"
    write_loss_csv(rows, resolved_csv_path)
    plot_loss_curve(rows, plot_path, title=f"Training Loss: {run_dir.name}")
    return {"plot": str(plot_path), "csv": str(resolved_csv_path), "points": str(len(rows))}
