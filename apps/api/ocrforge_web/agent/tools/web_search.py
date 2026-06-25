from __future__ import annotations

import logging
from typing import Any

import httpx

from ocrforge_web.agent.tools.base import Tool, ToolContext

logger = logging.getLogger("ocrforge_web.agent.web_search")


def _error_detail(exc: Exception) -> str:
    detail = str(exc).strip()
    return f"{type(exc).__name__}: {detail}" if detail else type(exc).__name__


async def _web_search(args: dict[str, Any], ctx: ToolContext) -> Any:
    settings = ctx.settings
    if not settings.brave_api_key:
        return {"error": "Brave 搜索未配置（设置 OCRFORGE_WEB_BRAVE_API_KEY 后启用）"}

    query = str(args.get("query") or "").strip()
    if not query:
        return {"error": "query is required"}
    count = int(args.get("count") or 5)
    count = max(1, min(count, 10))

    headers = {
        "Accept": "application/json",
        "X-Subscription-Token": settings.brave_api_key,
    }
    params = {"q": query, "count": count}
    client_kwargs: dict[str, Any] = {"timeout": 20.0, "trust_env": True}
    if settings.brave_proxy_url:
        client_kwargs["proxy"] = settings.brave_proxy_url
        client_kwargs["trust_env"] = False
    try:
        async with httpx.AsyncClient(**client_kwargs) as client:
            resp = await client.get(settings.brave_endpoint, headers=headers, params=params)
            if resp.status_code >= 400:
                return {"error": f"Brave API HTTP {resp.status_code}: {resp.text[:200]}"}
            data = resp.json()
    except httpx.HTTPError as exc:
        detail = _error_detail(exc)
        logger.warning(
            "Brave web_search request failed: %s | endpoint=%s | query=%r",
            detail,
            settings.brave_endpoint,
            query,
            extra={"brave_proxy_configured": bool(settings.brave_proxy_url)},
        )
        return {"error": f"无法访问 Brave 搜索：{detail}"}
    except ValueError as exc:
        detail = _error_detail(exc)
        logger.warning("Brave web_search returned invalid JSON: %s", detail)
        return {"error": f"Brave 搜索返回了无法解析的 JSON：{detail}"}

    results = []
    for item in (data.get("web", {}) or {}).get("results", [])[:count]:
        results.append(
            {
                "title": item.get("title"),
                "url": item.get("url"),
                "description": item.get("description"),
                "age": item.get("age"),
            }
        )
    return {"query": query, "results": results}


def web_search_tools() -> list[Tool]:
    return [
        Tool(
            name="web_search",
            description=(
                "Brave 联网搜索，返回标题/URL/摘要列表。用于库内没有、需要最新或外部信息时；"
                "拿到 URL 后可用 browse_page 读取正文。"
            ),
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "搜索关键词"},
                    "count": {"type": "integer", "minimum": 1, "maximum": 10, "default": 5},
                },
                "required": ["query"],
                "additionalProperties": False,
            },
            handler=_web_search,
        )
    ]
