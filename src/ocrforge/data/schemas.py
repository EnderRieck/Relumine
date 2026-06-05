from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class TextBox:
    text: str
    box: tuple[int, int, int, int]
    box_format: str


@dataclass(frozen=True)
class TextLine:
    text: str
    points: str = ""
    line_id: str = ""


@dataclass(frozen=True)
class OCRSample:
    image_path: Path
    target_text: str
    dataset_name: str
    split: str
    gt_path: Path | None = None
    boxes: list[TextBox] = field(default_factory=list)
    lines: list[TextLine] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)

