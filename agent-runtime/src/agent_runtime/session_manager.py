"""Session lifecycle management — create, start, pause, resume, stop."""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from .memory_store import MemoryStore
from .models import SessionState, SessionStatus
from .state_serializer import StateSerializer

logger = logging.getLogger(__name__)


class SessionError(Exception):
    pass


class SessionManager:
    def __init__(
        self,
        state_serializer: StateSerializer | None = None,
        memory_store: MemoryStore | None = None,
    ) -> None:
        self._state_serializer = state_serializer or StateSerializer()
        self._memory_store = memory_store or MemoryStore()
        self._running_tasks: dict[str, asyncio.Task] = {}
        self._heartbeat_intervals: dict[str, float] = {}
        self._auto_checkpoint_interval = 60.0

    def create_session(self, name: str, model: str, config: dict[str, Any] | None = None) -> SessionState:
        cfg = config or {}
        state = SessionState(
            session_id=uuid.uuid4().hex[:16],
            name=name,
            model=model,
            system_prompt=cfg.get("system_prompt", ""),
            tools=cfg.get("tools", []),
        )
        self._state_serializer.save_session(state)
        logger.info("Created session %s (%s)", state.session_id, name)
        return state

    async def start_session(self, session_id: str) -> SessionState:
        state = self._state_serializer.load_session(session_id)
        if state is None:
            raise SessionError(f"Session {session_id} not found")
        if state.status == SessionStatus.RUNNING:
            raise SessionError(f"Session {session_id} is already running")
        state.status = SessionStatus.RUNNING
        state.updated_at = datetime.now(timezone.utc)
        self._state_serializer.save_session(state)
        task = asyncio.create_task(self._session_loop(session_id))
        self._running_tasks[session_id] = task
        logger.info("Started session %s", session_id)
        return state

    async def pause_session(self, session_id: str) -> SessionState:
        state = self._state_serializer.load_session(session_id)
        if state is None:
            raise SessionError(f"Session {session_id} not found")
        if state.status != SessionStatus.RUNNING:
            raise SessionError(f"Session {session_id} is not running")
        state.status = SessionStatus.PAUSED
        state.updated_at = datetime.now(timezone.utc)
        self._state_serializer.save_session(state)
        task = self._running_tasks.pop(session_id, None)
        if task and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._state_serializer.create_checkpoint(session_id, label="pause-checkpoint")
        logger.info("Paused session %s", session_id)
        return state

    async def resume_session(self, session_id: str, checkpoint_id: str | None = None) -> SessionState:
        state = self._state_serializer.load_session(session_id)
        if state is None:
            raise SessionError(f"Session {session_id} not found")
        if checkpoint_id:
            state = self._state_serializer.resume_from_checkpoint(session_id, checkpoint_id)
        state.status = SessionStatus.RUNNING
        state.updated_at = datetime.now(timezone.utc)
        self._state_serializer.save_session(state)
        task = asyncio.create_task(self._session_loop(session_id))
        self._running_tasks[session_id] = task
        logger.info("Resumed session %s", session_id)
        return state

    async def stop_session(self, session_id: str) -> SessionState:
        state = self._state_serializer.load_session(session_id)
        if state is None:
            raise SessionError(f"Session {session_id} not found")
        state.status = SessionStatus.STOPPED
        state.updated_at = datetime.now(timezone.utc)
        self._state_serializer.save_session(state)
        task = self._running_tasks.pop(session_id, None)
        if task and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._state_serializer.create_checkpoint(session_id, label="stop-checkpoint")
        logger.info("Stopped session %s", session_id)
        return state

    def list_sessions(self) -> list[SessionState]:
        return self._state_serializer.list_sessions()

    def get_session_status(self, session_id: str) -> SessionState:
        state = self._state_serializer.load_session(session_id)
        if state is None:
            raise SessionError(f"Session {session_id} not found")
        return state

    def get_memory_store(self) -> MemoryStore:
        return self._memory_store

    def get_state_serializer(self) -> StateSerializer:
        return self._state_serializer

    async def _session_loop(self, session_id: str) -> None:
        last_checkpoint = asyncio.get_event_loop().time()
        try:
            while True:
                await asyncio.sleep(1.0)
                now = asyncio.get_event_loop().time()
                if now - last_checkpoint >= self._auto_checkpoint_interval:
                    state = self._state_serializer.load_session(session_id)
                    if state and state.status == SessionStatus.RUNNING:
                        self._state_serializer.create_checkpoint(
                            session_id, label="auto-checkpoint"
                        )
                        self._state_serializer.prune_checkpoints(session_id, keep_last=10)
                    last_checkpoint = now
        except asyncio.CancelledError:
            logger.info("Session loop cancelled for %s", session_id)

    async def shutdown(self) -> None:
        logger.info("Shutting down session manager, preserving %d active sessions", len(self._running_tasks))
        for session_id, task in list(self._running_tasks.items()):
            if not task.done():
                task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            self._state_serializer.create_checkpoint(session_id, label="shutdown-checkpoint")
        self._running_tasks.clear()
        logger.info("All sessions preserved and shut down")
