from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, AsyncIterator

import httpx

from ocrforge_web.settings import Settings

logger = logging.getLogger("ocrforge_web.agent.llm")

# Transient network failures worth retrying (str() of these is often empty).
_RETRYABLE = (
    httpx.ConnectError,
    httpx.ConnectTimeout,
    httpx.ReadError,
    httpx.ReadTimeout,
    httpx.RemoteProtocolError,
    httpx.PoolTimeout,
    httpx.WriteError,
)
_MAX_ATTEMPTS = 3
_BACKOFF_BASE = 0.6  # seconds; doubled each retry


class DeepSeekChatClient:
    """Streaming, tool-calling chat client for the DeepSeek (OpenAI-compatible) API.

    Reuses the project's ``llm_*`` settings. ``agent_model`` overrides the model
    when the default one lacks function-calling support.
    """

    def __init__(self, settings: Settings) -> None:
        self.api_key = settings.llm_api_key
        self.base_url = settings.llm_base_url.rstrip("/")
        self.model = settings.agent_model or settings.llm_model
        self.timeout = settings.llm_timeout

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    async def stream(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict] | None = None,
        *,
        tool_choice: str = "auto",
        temperature: float = 0.3,
    ) -> AsyncIterator[dict[str, Any]]:
        """Yield ``delta`` objects from the SSE stream.

        Each delta may carry ``content`` (a text fragment) and/or ``tool_calls``
        (streamed function-call fragments to be accumulated by the caller).
        """
        if not self.api_key:
            raise RuntimeError("DeepSeek API key is not configured (OCRFORGE_WEB_LLM_API_KEY)")

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "temperature": temperature,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = tool_choice

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        url = f"{self.base_url}/chat/completions"

        # Retry transient connection failures, but only while NO delta has been
        # emitted yet — retrying mid-stream would duplicate tokens/tool calls.
        last_exc: Exception | None = None
        for attempt in range(_MAX_ATTEMPTS):
            emitted = False
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    async with client.stream("POST", url, json=payload, headers=headers) as resp:
                        if resp.status_code >= 400:
                            body = await resp.aread()
                            detail = body.decode("utf-8", errors="replace")[:600]
                            logger.warning("DeepSeek HTTP %s: %s", resp.status_code, detail)
                            # 4xx/5xx are not retried here (auth/quota/bad request).
                            raise RuntimeError(
                                f"DeepSeek API returned HTTP {resp.status_code}: {detail}"
                            )

                        async for line in resp.aiter_lines():
                            if not line or not line.startswith("data:"):
                                continue
                            data = line[len("data:"):].strip()
                            if not data or data == "[DONE]":
                                if data == "[DONE]":
                                    break
                                continue
                            try:
                                chunk = json.loads(data)
                            except json.JSONDecodeError:
                                continue
                            # DeepSeek can emit an error frame mid-stream (HTTP 200).
                            if isinstance(chunk, dict) and chunk.get("error"):
                                err = chunk["error"]
                                msg = err.get("message") if isinstance(err, dict) else str(err)
                                raise RuntimeError(f"DeepSeek 流内返回错误：{msg}")
                            choices = chunk.get("choices") or []
                            if not choices:
                                continue
                            delta = choices[0].get("delta") or {}
                            if delta:
                                emitted = True
                                yield delta
                return  # finished cleanly
            except _RETRYABLE as exc:
                last_exc = exc
                if emitted or attempt == _MAX_ATTEMPTS - 1:
                    break
                wait = _BACKOFF_BASE * (2**attempt)
                logger.warning(
                    "DeepSeek connection failed (%s), retry %d/%d in %.1fs",
                    type(exc).__name__, attempt + 1, _MAX_ATTEMPTS - 1, wait,
                )
                await asyncio.sleep(wait)

        raise RuntimeError(
            f"无法连接 DeepSeek API（{type(last_exc).__name__ if last_exc else 'network'}），"
            "可能是网络波动，请稍后重试"
        ) from last_exc


def accumulate_tool_calls(
    acc: dict[int, dict[str, Any]], fragments: list[dict[str, Any]]
) -> None:
    """Merge streamed ``delta.tool_calls`` fragments into ``acc`` keyed by index."""
    for frag in fragments:
        idx = frag.get("index", 0)
        slot = acc.setdefault(
            idx,
            {"id": "", "type": "function", "function": {"name": "", "arguments": ""}},
        )
        if frag.get("id"):
            slot["id"] = frag["id"]
        fn = frag.get("function") or {}
        if fn.get("name"):
            slot["function"]["name"] += fn["name"]
        if fn.get("arguments"):
            slot["function"]["arguments"] += fn["arguments"]


def finalize_tool_calls(acc: dict[int, dict[str, Any]]) -> list[dict[str, Any]]:
    return [acc[i] for i in sorted(acc)]
