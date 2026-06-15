from __future__ import annotations

from typing import Any

from ocrforge_web.agent.tools.base import Tool, ToolContext, no_params
from ocrforge_web.agent.skills import SkillRegistry


def skill_tools(skills: SkillRegistry) -> list[Tool]:
    async def _list_skills(args: dict[str, Any], ctx: ToolContext) -> Any:
        return {
            "skills": [
                {"name": s.name, "description": s.description} for s in skills.list()
            ]
        }

    async def _run_skill(args: dict[str, Any], ctx: ToolContext) -> Any:
        name = str(args.get("name") or "").strip()
        skill = skills.get(name)
        if skill is None:
            return {
                "error": f"未知技能 {name!r}",
                "available": skills.names(),
            }
        return {
            "skill": skill.name,
            "recommended_tools": skill.tools,
            "instructions": skill.body,
        }

    return [
        Tool(
            name="list_skills",
            description="列出可用的技能（封装好的常用能力流程）及其用途。",
            parameters=no_params(),
            handler=_list_skills,
        ),
        Tool(
            name="run_skill",
            description=(
                "加载某个技能的详细操作指令并按其流程执行。先用 list_skills 查看可用技能。"
            ),
            parameters={
                "type": "object",
                "properties": {"name": {"type": "string"}},
                "required": ["name"],
                "additionalProperties": False,
            },
            handler=_run_skill,
        ),
    ]
