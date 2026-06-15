from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Awaitable, Callable, Literal

if TYPE_CHECKING:
    from ocrforge_web.agent.sessions import Session
    from ocrforge_web.settings import Settings

ToolLocation = Literal["server", "client"]

# A server tool handler: async (args, ctx) -> result (json-serialisable or str).
ToolHandler = Callable[["dict[str, Any]", "ToolContext"], Awaitable[Any]]


@dataclass
class ToolContext:
    """Everything a tool needs at call time."""

    settings: "Settings"
    session: "Session"
    registry: "ToolRegistry"


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict  # JSON Schema for the function arguments
    location: ToolLocation = "server"
    handler: ToolHandler | None = None

    def spec(self) -> dict:
        """DeepSeek/OpenAI tool spec."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    async def run(self, args: dict[str, Any], ctx: ToolContext) -> Any:
        if self.location == "client":
            # Client tools are executed by the frontend; the harness handles this
            # before ever calling run(). Reaching here is a programming error.
            raise RuntimeError(f"client tool {self.name!r} cannot run on the server")
        if self.handler is None:
            raise RuntimeError(f"server tool {self.name!r} has no handler")
        return await self.handler(args, ctx)


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> "ToolRegistry":
        self._tools[tool.name] = tool
        return self

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def __contains__(self, name: str) -> bool:
        return name in self._tools

    def all(self) -> list[Tool]:
        return list(self._tools.values())

    def specs(self, names: list[str] | None = None) -> list[dict]:
        if names is None:
            return [t.spec() for t in self._tools.values()]
        return [self._tools[n].spec() for n in names if n in self._tools]


def no_params() -> dict:
    return {"type": "object", "properties": {}, "additionalProperties": False}
