from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger("ocrforge_web.agent.skills")

_BUILTIN_DIR = Path(__file__).resolve().parent / "builtin"


@dataclass
class Skill:
    name: str
    description: str
    body: str
    tools: list[str] = field(default_factory=list)


def _parse_frontmatter(text: str) -> tuple[dict[str, object], str]:
    """Parse a minimal ``---`` YAML-ish frontmatter block. Supports scalar
    ``key: value`` and inline lists ``key: [a, b]``. Avoids a PyYAML dependency.
    """
    if not text.startswith("---"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    fm_raw, body = parts[1], parts[2].lstrip("\n")
    meta: dict[str, object] = {}
    for line in fm_raw.strip().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, val = line.split(":", 1)
        key, val = key.strip(), val.strip()
        if val.startswith("[") and val.endswith("]"):
            meta[key] = [v.strip().strip("\"'") for v in val[1:-1].split(",") if v.strip()]
        else:
            meta[key] = val.strip("\"'")
    return meta, body


def _load_skill(skill_md: Path) -> Skill | None:
    try:
        meta, body = _parse_frontmatter(skill_md.read_text(encoding="utf-8"))
    except OSError as exc:
        logger.warning("cannot read skill %s: %s", skill_md, exc)
        return None
    name = str(meta.get("name") or skill_md.parent.name).strip()
    description = str(meta.get("description") or "").strip()
    tools = meta.get("tools") or []
    if not isinstance(tools, list):
        tools = []
    if not name or not body.strip():
        return None
    return Skill(name=name, description=description, body=body.strip(), tools=[str(t) for t in tools])


class SkillRegistry:
    def __init__(self, skills: list[Skill]) -> None:
        self._skills = {s.name: s for s in skills}

    def list(self) -> list[Skill]:
        return list(self._skills.values())

    def get(self, name: str) -> Skill | None:
        return self._skills.get(name)

    def names(self) -> list[str]:
        return list(self._skills.keys())


def load_skills(directory: Path = _BUILTIN_DIR) -> SkillRegistry:
    skills: list[Skill] = []
    if directory.exists():
        for skill_md in sorted(directory.glob("*/SKILL.md")):
            skill = _load_skill(skill_md)
            if skill:
                skills.append(skill)
    logger.info("loaded %d agent skills", len(skills))
    return SkillRegistry(skills)
