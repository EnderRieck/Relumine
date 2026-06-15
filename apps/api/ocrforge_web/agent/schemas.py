from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class AgentChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=8000)
    session_id: str | None = None
    # Snapshot of the current page state, collected by the frontend bridge.
    page_context: dict[str, Any] | None = None


class AgentContinueRequest(BaseModel):
    session_id: str
    call_id: str
    # Result produced by the frontend after executing a client tool.
    result: Any = None
    error: str | None = None


class SkillInfo(BaseModel):
    name: str
    description: str
    tools: list[str] = Field(default_factory=list)


class AgentHealth(BaseModel):
    deepseek_configured: bool
    model: str
    brave_configured: bool
    browser_enabled: bool
    skills: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
