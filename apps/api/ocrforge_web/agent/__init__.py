"""Agent Harness — manages the chat agent's context, tools and skills.

The harness drives a DeepSeek (OpenAI-compatible) tool-calling loop. Server-side
tools (database, search, browser) run inside the loop; client-side tools (reading
or operating the web UI) suspend the loop and ask the frontend to execute them,
then resume via the /continue endpoint.
"""

from ocrforge_web.agent.harness import Harness, get_harness

__all__ = ["Harness", "get_harness"]
