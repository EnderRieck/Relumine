from __future__ import annotations

import argparse
import json
from pathlib import Path

from _bootstrap import add_src_to_path

add_src_to_path()

from ocrforge.training import plot_train_run


def main() -> None:
    parser = argparse.ArgumentParser(description="Plot OCRForge training loss curve from train_metrics_rank*.jsonl.")
    parser.add_argument("run_dir", help="Training run directory, e.g. CultureCourse/runs/train/20260428-xxxx_exp.")
    parser.add_argument("--output", default=None, help="Output image path. Defaults to run_dir/loss_curve.png.")
    parser.add_argument("--csv", default=None, help="Output CSV path. Defaults to run_dir/loss_curve.csv.")
    args = parser.parse_args()

    run_dir = Path(args.run_dir).resolve()
    output = Path(args.output).resolve() if args.output else None
    csv_path = Path(args.csv).resolve() if args.csv else None
    result = plot_train_run(
        run_dir,
        output_path=output,
        csv_path=csv_path,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
