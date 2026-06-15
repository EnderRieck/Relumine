from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any
from uuid import uuid4

from ocrforge_web.agent.tools.base import Tool, ToolContext

logger = logging.getLogger("ocrforge_web.agent.browser")

# Screenshots are written here and served via GET /api/agent/asset/{name}.
ASSET_DIR = Path(__file__).resolve().parents[2] / "data" / "agent_cache"


class BrowserManager:
    """Lazily launches a single headless Chromium and reuses it across calls."""

    def __init__(self) -> None:
        self._playwright = None
        self._browser = None
        self._lock = asyncio.Lock()

    async def _ensure(self):
        if self._browser is not None:
            return self._browser
        async with self._lock:
            if self._browser is None:
                from playwright.async_api import async_playwright

                self._playwright = await async_playwright().start()
                self._browser = await self._playwright.chromium.launch(headless=True)
                logger.info("headless chromium launched for agent")
        return self._browser

    async def new_page(self):
        browser = await self._ensure()
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
            )
        )
        page = await context.new_page()
        return context, page

    async def close(self) -> None:
        try:
            if self._browser is not None:
                await self._browser.close()
            if self._playwright is not None:
                await self._playwright.stop()
        except Exception as exc:  # noqa: BLE001 - best-effort cleanup
            logger.warning("error closing browser: %s", exc)
        finally:
            self._browser = None
            self._playwright = None


_MANAGER = BrowserManager()


def get_browser_manager() -> BrowserManager:
    return _MANAGER


async def _browse_page(args: dict[str, Any], ctx: ToolContext) -> Any:
    if not ctx.settings.agent_enable_browser:
        return {"error": "无头浏览器已禁用（OCRFORGE_WEB_AGENT_ENABLE_BROWSER=true 启用）"}

    url = str(args.get("url") or "").strip()
    if not url:
        return {"error": "url is required"}
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    mode = args.get("mode") or "text"

    mgr = get_browser_manager()
    try:
        context, page = await mgr.new_page()
    except Exception as exc:  # noqa: BLE001
        return {"error": f"无法启动浏览器：{exc}。请确认已运行 `playwright install chromium`。"}

    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        title = await page.title()
        final_url = page.url

        if mode == "screenshot":
            png = await page.screenshot(full_page=False)
            ASSET_DIR.mkdir(parents=True, exist_ok=True)
            name = f"{uuid4().hex}.png"
            (ASSET_DIR / name).write_bytes(png)
            return {
                "title": title,
                "url": final_url,
                "image_url": f"/api/agent/asset/{name}",
                "note": "已截图，图像将在对话中展示。",
            }

        text = await page.evaluate("() => document.body ? document.body.innerText : ''")
        text = (text or "").strip()
        return {
            "title": title,
            "url": final_url,
            "text": text[:6000],
            "truncated": len(text) > 6000,
        }
    except Exception as exc:  # noqa: BLE001
        return {"error": f"打开页面失败：{exc}"}
    finally:
        try:
            await context.close()
        except Exception:  # noqa: BLE001
            pass


def browser_tools() -> list[Tool]:
    return [
        Tool(
            name="browse_page",
            description=(
                "用无头浏览器打开一个 URL。mode=text 返回正文文本(截断)；"
                "mode=screenshot 截图并在对话中展示。常配合 web_search 使用。"
            ),
            parameters={
                "type": "object",
                "properties": {
                    "url": {"type": "string"},
                    "mode": {"type": "string", "enum": ["text", "screenshot"], "default": "text"},
                },
                "required": ["url"],
                "additionalProperties": False,
            },
            handler=_browse_page,
        )
    ]
