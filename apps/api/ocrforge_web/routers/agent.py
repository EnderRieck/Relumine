from __future__ import annotations

import json
import logging
from typing import Any, AsyncIterator

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, StreamingResponse

from ocrforge_web.agent import get_harness
from ocrforge_web.agent.schemas import (
    AgentChatRequest,
    AgentContinueRequest,
    AgentHealth,
    SkillInfo,
)
from ocrforge_web.agent.tools.browser import ASSET_DIR

logger = logging.getLogger("ocrforge_web.routers.agent")

router = APIRouter(tags=["agent"])

_SSE_HEADERS = {
    "Cache-Control": "no-store",
    "Connection": "keep-alive",
    # Disable proxy buffering so tokens stream through promptly.
    "X-Accel-Buffering": "no",
}


def _sse(event: dict[str, Any]) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


async def _stream(events: AsyncIterator[dict[str, Any]]) -> AsyncIterator[str]:
    try:
        async for event in events:
            yield _sse(event)
    except Exception as exc:  # noqa: BLE001 - never break the stream uncaught
        logger.exception("agent stream crashed")
        yield _sse({"type": "error", "message": f"内部错误：{exc}"})


@router.post("/agent/chat")
async def agent_chat(request: AgentChatRequest) -> StreamingResponse:
    harness = get_harness()
    events = harness.run_chat(request.session_id, request.message, request.page_context)
    return StreamingResponse(
        _stream(events), media_type="text/event-stream", headers=_SSE_HEADERS
    )


@router.post("/agent/continue")
async def agent_continue(request: AgentContinueRequest) -> StreamingResponse:
    harness = get_harness()
    events = harness.run_continue(
        request.session_id, request.call_id, request.result, request.error
    )
    return StreamingResponse(
        _stream(events), media_type="text/event-stream", headers=_SSE_HEADERS
    )


@router.get("/agent/health", response_model=AgentHealth)
def agent_health() -> AgentHealth:
    return AgentHealth(**get_harness().health())


@router.get("/agent/skills", response_model=list[SkillInfo])
def agent_skills() -> list[SkillInfo]:
    skills = get_harness().skills.list()
    return [
        SkillInfo(name=s.name, description=s.description, tools=s.tools) for s in skills
    ]


@router.get("/agent/asset/{name}")
def agent_asset(name: str) -> FileResponse:
    # Only serve generated screenshots; block path traversal.
    target = (ASSET_DIR / name).resolve()
    if target.parent != ASSET_DIR.resolve() or not target.is_file():
        raise HTTPException(status_code=404, detail="asset not found")
    return FileResponse(target, media_type="image/png")
