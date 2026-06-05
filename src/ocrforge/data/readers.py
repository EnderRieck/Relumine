from __future__ import annotations

import json
from pathlib import Path
from xml.etree import ElementTree as ET

from ocrforge.data.schemas import TextBox, TextLine
from ocrforge.utils.paths import resolve_path


def read_jsonl(path: Path) -> list[dict]:
    records = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                records.append(json.loads(line))
    return records


def read_class_label(path: Path) -> str:
    return "".join(line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip())


def read_class_label_lines(path: Path) -> list[str]:
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def read_annotation_boxes(path: Path, labels: list[str], box_format: str) -> list[TextBox]:
    boxes: list[TextBox] = []
    if not path.exists():
        return boxes
    lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    for index, line in enumerate(lines):
        if index >= len(labels):
            break
        try:
            _, coords = line.split(maxsplit=1)
            values = tuple(int(float(item)) for item in coords.split(","))
            if len(values) != 4:
                continue
        except ValueError:
            continue
        boxes.append(TextBox(text=labels[index], box=values, box_format=box_format))
    return boxes


def xml_child_text(element: ET.Element, suffix: str) -> str:
    for child in element.iter():
        if child.tag.endswith(suffix) and child.text:
            return child.text.strip()
    return ""


def read_page_xml(path: Path) -> list[TextLine]:
    tree = ET.parse(path)
    output: list[TextLine] = []
    for element in tree.getroot().iter():
        if not element.tag.endswith("TextLine"):
            continue
        coords = ""
        for child in element:
            if child.tag.endswith("Coords"):
                coords = child.attrib.get("points", "")
                break
        text = xml_child_text(element, "Unicode")
        if text:
            output.append(TextLine(text=text, points=coords, line_id=element.attrib.get("id", "")))
    return output


def resolve_manifest_image(record: dict, project_root: Path) -> Path:
    return resolve_path(record["image"], project_root)

