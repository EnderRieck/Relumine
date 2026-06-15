from __future__ import annotations

import json
import logging
from typing import Any, AsyncIterator

from ocrforge_web.agent.context import build_system_prompt
from ocrforge_web.agent.llm import (
    DeepSeekChatClient,
    accumulate_tool_calls,
    finalize_tool_calls,
)
from ocrforge_web.agent.sessions import Session, SessionStore
from ocrforge_web.agent.skills import load_skills
from ocrforge_web.agent.tools import ToolContext, build_registry
from ocrforge_web.settings import Settings, get_settings

logger = logging.getLogger("ocrforge_web.agent.harness")

Event = dict[str, Any]
_PREVIEW_LIMIT = 3000


def _parse_args(raw: str) -> dict[str, Any]:
    try:
        value = json.loads(raw or "{}")
        return value if isinstance(value, dict) else {"_value": value}
    except json.JSONDecodeError:
        return {}


def _ui_preview(result: Any) -> Any:
    try:
        text = json.dumps(result, ensure_ascii=False)
    except (TypeError, ValueError):
        text = str(result)
    if len(text) > _PREVIEW_LIMIT:
        return {"_truncated": True, "preview": text[:_PREVIEW_LIMIT]}
    return result


class Harness:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.skills = load_skills()
        self.registry = build_registry(self.skills)
        self.sessions = SessionStore(ttl=settings.agent_session_ttl)
        self.system_prompt = build_system_prompt(self.skills)

    # ---------- introspection ----------

    def health(self) -> dict[str, Any]:
        client = DeepSeekChatClient(self.settings)
        return {
            "deepseek_configured": client.configured,
            "model": client.model,
            "brave_configured": bool(self.settings.brave_api_key),
            "browser_enabled": self.settings.agent_enable_browser,
            "skills": self.skills.names(),
            "tools": [t.name for t in self.registry.all()],
        }

    # ---------- public entrypoints ----------

    async def run_chat(
        self,
        session_id: str | None,
        message: str,
        page_context: dict[str, Any] | None,
    ) -> AsyncIterator[Event]:
        session = self.sessions.get_or_create(session_id)
        yield {"type": "session", "session_id": session.id}

        if not session.system_set:
            session.messages.append({"role": "system", "content": self.system_prompt})
            session.system_set = True
        # A user can resend while tool calls are still pending. Every assistant
        # tool_call must be answered or the next request 400s, so close out any
        # orphaned calls with a cancellation result before continuing.
        for tc in session.pending_tool_calls:
            session.messages.append(
                self._tool_message(tc["id"], {"cancelled": "用户发送了新消息"})
            )
        session.pending_tool_calls = []
        session.awaiting_client = None
        session.page_context = page_context
        session.messages.append({"role": "user", "content": message})

        async for event in self._loop(session):
            yield event

    async def run_continue(
        self,
        session_id: str,
        call_id: str,
        result: Any,
        error: str | None,
    ) -> AsyncIterator[Event]:
        session = self.sessions.get(session_id)
        if session is None:
            yield {"type": "error", "message": "会话不存在或已过期"}
            return
        awaiting = session.awaiting_client
        if not awaiting or awaiting.get("id") != call_id:
            yield {"type": "error", "message": "没有匹配的待执行客户端工具"}
            return

        payload: Any = {"error": error} if error else (result if result is not None else {"ok": True})
        session.messages.append(self._tool_message(call_id, payload))
        session.pending_tool_calls = [
            tc for tc in session.pending_tool_calls if tc.get("id") != call_id
        ]
        session.awaiting_client = None

        # Finish any remaining tool calls from the same assistant turn.
        async for event in self._process_pending(session):
            yield event
        if session.awaiting_client:
            return
        async for event in self._loop(session):
            yield event

    # ---------- internals ----------

    async def _loop(self, session: Session) -> AsyncIterator[Event]:
        client = DeepSeekChatClient(self.settings)
        for _ in range(self.settings.agent_max_steps):
            assistant: dict[str, Any] = {"role": "assistant", "content": ""}
            acc: dict[int, dict[str, Any]] = {}
            reasoning = ""
            try:
                async for delta in client.stream(session.messages, self.registry.specs()):
                    if delta.get("content"):
                        assistant["content"] += delta["content"]
                        yield {"type": "token", "text": delta["content"]}
                    # Thinking models (e.g. deepseek-v4-flash) stream reasoning_content
                    # which MUST be echoed back on the next request alongside tool_calls.
                    if delta.get("reasoning_content"):
                        reasoning += delta["reasoning_content"]
                        yield {"type": "reasoning", "text": delta["reasoning_content"]}
                    if delta.get("tool_calls"):
                        accumulate_tool_calls(acc, delta["tool_calls"])
            except Exception as exc:  # noqa: BLE001 - surface to the UI
                logger.warning("LLM stream error: %r", exc, exc_info=True)
                detail = str(exc).strip() or type(exc).__name__
                yield {"type": "error", "message": f"对话出错：{detail}"}
                return

            tool_calls = finalize_tool_calls(acc)
            if tool_calls:
                assistant["tool_calls"] = tool_calls
            if reasoning:
                assistant["reasoning_content"] = reasoning
            session.messages.append(assistant)

            if not tool_calls:
                yield {"type": "done"}
                return

            # Copy: _process_pending pops from this list, and we must NOT mutate
            # the tool_calls stored on the assistant message (it's sent back next turn).
            session.pending_tool_calls = list(tool_calls)
            async for event in self._process_pending(session):
                yield event
            if session.awaiting_client:
                return  # suspended; resumed via run_continue

        yield {"type": "done", "reason": "max_steps"}

    async def _process_pending(self, session: Session) -> AsyncIterator[Event]:
        ctx = ToolContext(settings=self.settings, session=session, registry=self.registry)
        while session.pending_tool_calls:
            tc = session.pending_tool_calls[0]
            name = tc["function"]["name"]
            args = _parse_args(tc["function"].get("arguments", ""))
            yield {"type": "tool_call", "id": tc["id"], "name": name, "args": args}

            tool = self.registry.get(name)
            if tool is None:
                result: Any = {"error": f"unknown tool {name!r}"}
                session.messages.append(self._tool_message(tc["id"], result))
                session.pending_tool_calls.pop(0)
                yield {"type": "tool_result", "id": tc["id"], "name": name, "result": result}
                continue

            if tool.location == "client":
                session.awaiting_client = {"id": tc["id"], "name": name, "args": args}
                yield {"type": "client_tool_call", "call_id": tc["id"], "name": name, "args": args}
                return  # suspend until the frontend posts the result

            try:
                result = await tool.run(args, ctx)
            except Exception as exc:  # noqa: BLE001
                logger.warning("tool %s failed: %s", name, exc)
                result = {"error": str(exc)}

            session.messages.append(self._tool_message(tc["id"], result))
            session.pending_tool_calls.pop(0)
            if isinstance(result, dict) and result.get("image_url"):
                yield {"type": "asset", "url": result["image_url"]}
            yield {
                "type": "tool_result",
                "id": tc["id"],
                "name": name,
                "result": _ui_preview(result),
            }

    @staticmethod
    def _tool_message(call_id: str, result: Any) -> dict[str, Any]:
        content = result if isinstance(result, str) else json.dumps(result, ensure_ascii=False)
        return {"role": "tool", "tool_call_id": call_id, "content": content}


_HARNESS: Harness | None = None


def get_harness() -> Harness:
    global _HARNESS
    if _HARNESS is None:
        _HARNESS = Harness(get_settings())
    return _HARNESS
