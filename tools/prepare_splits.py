from __future__ import annotations

from _bootstrap import add_src_to_path

add_src_to_path()

import argparse
import json
import random
from pathlib import Path

from ocrforge.utils.paths import find_project_root, project_relative

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp", ".webp"}


def images_by_stem(images_dir: Path) -> dict[str, Path]:
    return {
        path.stem: path
        for path in sorted(images_dir.rglob("*"))
        if path.suffix.lower() in IMAGE_EXTENSIONS and not path.name.startswith(".") and path.stat().st_size > 0
    }


def read_ids(path: Path) -> list[str]:
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_manifest(paths: list[Path], output: Path, project_root: Path, split: str, source: str) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as handle:
        for path in paths:
            handle.write(
                json.dumps(
                    {"image": project_relative(path, project_root), "split": split, "split_source": source},
                    ensure_ascii=False,
                )
                + "\n"
            )
    print(f"{output}: {len(paths)}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", choices=["all", "tkh", "mth", "icdar2019"], default="all")
    parser.add_argument("--seed", type=int, default=20260428)
    args = parser.parse_args()
    project_root = find_project_root()

    if args.dataset in {"all", "tkh"}:
        root = project_root / "CultureCourse/datasets/TKH"
        images = images_by_stem(root / "raw/JPEGImages")
        for split in ["train", "test"]:
            ids = read_ids(root / "raw/ImageSets/Main" / f"{split}.txt")
            write_manifest([images[item] for item in ids], root / "splits" / f"{split}.jsonl", project_root, split, "official")

    if args.dataset in {"all", "mth"}:
        root = project_root / "CultureCourse/datasets/MTH"
        images = images_by_stem(root / "raw/JPEGImages")
        ids = read_ids(root / "raw/ImageSets/Main/test.txt")
        rng = random.Random(args.seed)
        rng.shuffle(ids)
        train_end = int(len(ids) * 0.8)
        source = f"generated_from_official_test_seed_{args.seed}_80_20"
        write_manifest([images[item] for item in ids[:train_end]], root / "splits/train.jsonl", project_root, "train", source)
        write_manifest([images[item] for item in ids[train_end:]], root / "splits/test.jsonl", project_root, "test", source)

    if args.dataset in {"all", "icdar2019"}:
        root = project_root / "CultureCourse/datasets/ICDAR2019-HDRC-Chinese"
        images = sorted(
            path
            for path in (root / "images").rglob("*")
            if path.suffix.lower() in IMAGE_EXTENSIONS and not path.name.startswith(".") and path.stat().st_size > 0
        )
        rng = random.Random(args.seed)
        rng.shuffle(images)
        train_end = int(len(images) * 0.8)
        write_manifest(images[:train_end], root / "splits/train.jsonl", project_root, "train", f"generated_seed_{args.seed}_80_20")
        write_manifest(images[train_end:], root / "splits/test.jsonl", project_root, "test", f"generated_seed_{args.seed}_80_20")


if __name__ == "__main__":
    main()

