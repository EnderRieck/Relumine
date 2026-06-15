from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4


@dataclass
class Session:
    """In-memory conversation state. Lost on restart (by design)."""

    id: str
    messages: list[dict[str, Any]] = field(default_factory=list)
    # Tool calls from the latest assistant message that still need a result.
    pending_tool_calls: list[dict[str, Any]] = field(default_factory=list)
    # The single client tool whose result the frontend is currently computing.
    awaiting_client: dict[str, Any] | None = None
    # Latest page snapshot pushed from the frontend (read by get_page_context).
    page_context: dict[str, Any] | None = None
    system_set: bool = False
    created_at: float = field(default_factory=time.time)
    last_active: float = field(default_factory=time.time)

    def touch(self) -> None:
        self.last_active = time.time()


class SessionStore:
    def __init__(self, ttl: float = 3600.0) -> None:
        self._sessions: dict[str, Session] = {}
        self._lock = threading.Lock()
        self._ttl = ttl

    def _gc_locked(self) -> None:
        if self._ttl <= 0:
            return
        cutoff = time.time() - self._ttl
        stale = [sid for sid, s in self._sessions.items() if s.last_active < cutoff]
        for sid in stale:
            self._sessions.pop(sid, None)

    def get_or_create(self, session_id: str | None) -> Session:
        with self._lock:
            self._gc_locked()
            if session_id and session_id in self._sessions:
                session = self._sessions[session_id]
                session.touch()
                return session
            sid = session_id or uuid4().hex
            session = Session(id=sid)
            self._sessions[sid] = session
            return session

    def get(self, session_id: str) -> Session | None:
        with self._lock:
            session = self._sessions.get(session_id)
            if session:
                session.touch()
            return session

    def drop(self, session_id: str) -> None:
        with self._lock:
            self._sessions.pop(session_id, None)
