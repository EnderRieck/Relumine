from __future__ import annotations

from ocrforge_web.agent.skills import SkillRegistry
from ocrforge_web.agent.tools.base import Tool, ToolContext, ToolRegistry
from ocrforge_web.agent.tools.browser import browser_tools, get_browser_manager
from ocrforge_web.agent.tools.db_tools import db_tools
from ocrforge_web.agent.tools.page_tools import client_tools, page_context_tools
from ocrforge_web.agent.tools.skill_tools import skill_tools
from ocrforge_web.agent.tools.web_search import web_search_tools

__all__ = [
    "Tool",
    "ToolContext",
    "ToolRegistry",
    "build_registry",
    "get_browser_manager",
]


def build_registry(skills: SkillRegistry) -> ToolRegistry:
    registry = ToolRegistry()
    for tool in db_tools():
        registry.register(tool)
    for tool in web_search_tools():
        registry.register(tool)
    for tool in browser_tools():
        registry.register(tool)
    for tool in page_context_tools():
        registry.register(tool)
    for tool in client_tools():
        registry.register(tool)
    for tool in skill_tools(skills):
        registry.register(tool)
    return registry
