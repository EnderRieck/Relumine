from __future__ import annotations

from typing import Any

from ocrforge_web.agent.tools.base import Tool, ToolContext, no_params


async def _get_page_context(args: dict[str, Any], ctx: ToolContext) -> Any:
    """Return the latest page snapshot the frontend pushed with the request."""
    snapshot = ctx.session.page_context
    if not snapshot:
        return {"note": "当前没有页面状态快照（前端未提供或页面为空）。"}
    return snapshot


def page_context_tools() -> list[Tool]:
    return [
        Tool(
            name="get_page_context",
            description=(
                "读取用户当前页面的实时状态快照：当前所在标签页、各面板里用户已填写的输入"
                "（繁简通译文本、形声流变检索词/选中字、史脉古籍原文等）与展示结果。"
                "想知道'用户现在在看/填了什么'时调用。"
            ),
            parameters=no_params(),
            handler=_get_page_context,
        )
    ]


def _client_tool(name: str, description: str, parameters: dict) -> Tool:
    return Tool(name=name, description=description, parameters=parameters, location="client")


def client_tools() -> list[Tool]:
    """Declarations for tools the FRONTEND executes (operate the UI).

    The harness suspends when one of these is called and asks the frontend to
    run it via an SSE ``client_tool_call`` event; the frontend posts the result
    back to /api/agent/continue.
    """
    return [
        _client_tool(
            "switch_tab",
            "切换到指定标签页。tab: convert(繁简通译)/ocr(古籍识读)/evolution(形声流变)/culture(史脉)。",
            {
                "type": "object",
                "properties": {
                    "tab": {
                        "type": "string",
                        "enum": ["convert", "ocr", "evolution", "culture"],
                    }
                },
                "required": ["tab"],
                "additionalProperties": False,
            },
        ),
        _client_tool(
            "set_convert_input",
            "在'繁简通译'页填入待转换文本，可选设置方向(direction)。不会自动转换。",
            {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "direction": {"type": "string", "enum": ["t2s", "s2t"]},
                },
                "required": ["text"],
                "additionalProperties": False,
            },
        ),
        _client_tool(
            "run_convert",
            "触发'繁简通译'页对当前输入执行转换。",
            no_params(),
        ),
        _client_tool(
            "set_evolution_search",
            "在'形声流变'页的检索框填入关键词/汉字。",
            {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
                "additionalProperties": False,
            },
        ),
        _client_tool(
            "select_character",
            "在'形声流变'页打开某个汉字的详情视图。",
            {
                "type": "object",
                "properties": {"char": {"type": "string", "description": "汉字（单字）"}},
                "required": ["char"],
                "additionalProperties": False,
            },
        ),
        _client_tool(
            "open_merge_dashboard",
            "在'形声流变'页打开『合并疑难总览』仪表盘（OCR 高风险 / 高语义歧义 / 四维 Top10 排行）。",
            no_params(),
        ),
        _client_tool(
            "analyze_corpus_coverage",
            "在'形声流变'页的『语料覆盖率』里粘贴一段古籍文本或 OCR 输出，统计命中字与风险字，"
            "并打开结果面板。返回覆盖统计供你解读。",
            {
                "type": "object",
                "properties": {"text": {"type": "string", "description": "待统计的语料文本"}},
                "required": ["text"],
                "additionalProperties": False,
            },
        ),
        _client_tool(
            "set_culture_text",
            "在'史脉'页填入待分析的古籍原文，可选填标题。不会自动分析。",
            {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "title": {"type": "string"},
                },
                "required": ["text"],
                "additionalProperties": False,
            },
        ),
        _client_tool(
            "run_culture_analysis",
            "触发'史脉'页对当前原文执行实体-关系抽取分析（较慢）。",
            no_params(),
        ),
    ]
