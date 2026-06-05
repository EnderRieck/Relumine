from __future__ import annotations

import os
from pathlib import Path


def find_project_root(start: Path | None = None) -> Path:
    env_root = os.environ.get("OCRFORGE_PROJECT_ROOT")
    if env_root:
        return Path(env_root).expanduser().resolve()

    starts = []
    if start is not None:
        starts.append(start.resolve())
    starts.append(Path.cwd().resolve())
    starts.append(Path(__file__).resolve())

    for item in starts:
        base = item if item.is_dir() else item.parent
        for parent in [base, *base.parents]:
            if (parent / "CultureCourse/datasets").exists() and (parent / "CultureCourse/models").exists():
                return parent.resolve()
            if (parent / "datasets").exists() and (parent / "models").exists():
                return parent.resolve()

    return Path.cwd().resolve()


def resolve_path(path: str | Path, project_root: Path) -> Path:
    item = Path(path).expanduser()
    if item.is_absolute():
        return item
    if item.exists():
        return item.resolve()
    return (project_root / item).resolve()


def project_relative(path: str | Path, project_root: Path) -> str:
    resolved = Path(path).resolve()
    try:
        return str(resolved.relative_to(project_root))
    except ValueError:
        return str(resolved)

