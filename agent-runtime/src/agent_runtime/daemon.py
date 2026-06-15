"""Main daemon process — background agent manager with heartbeat and auto-checkpoint."""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import time
from pathlib import Path

from .memory_store import MemoryStore
from .models import HealthResponse
from .session_manager import SessionManager
from .state_serializer import StateSerializer

logger = logging.getLogger(__name__)

PID_DIR = Path.home() / ".agent_runtime"
PID_FILE = PID_DIR / "agentd.pid"


class AgentDaemon:
    def __init__(
        self,
        state_serializer: StateSerializer | None = None,
        memory_store: MemoryStore | None = None,
        host: str = "0.0.0.0",
        port: int = 8721,
        auto_checkpoint_interval: float = 60.0,
        session_timeout: float = 3600.0,
    ) -> None:
        self._state_serializer = state_serializer or StateSerializer()
        self._memory_store = memory_store or MemoryStore()
        self._session_manager = SessionManager(
            state_serializer=self._state_serializer,
            memory_store=self._memory_store,
        )
        self._host = host
        self._port = port
        self._auto_checkpoint_interval = auto_checkpoint_interval
        self._session_timeout = session_timeout
        self._start_time = time.monotonic()
        self._shutdown_event = asyncio.Event()
        self._heartbeat_task: asyncio.Task | None = None
        self._cleanup_task: asyncio.Task | None = None
        self._server_task: asyncio.Task | None = None

    @property
    def session_manager(self) -> SessionManager:
        return self._session_manager

    @property
    def uptime_seconds(self) -> float:
        return time.monotonic() - self._start_time

    def health(self) -> HealthResponse:
        active = sum(
            1
            for s in self._session_manager.list_sessions()
            if s.status.value == "running"
        )
        return HealthResponse(
            status="healthy",
            uptime_seconds=self.uptime_seconds,
            active_sessions=active,
        )

    async def start(self) -> None:
        logger.info("AgentDaemon starting on %s:%d", self._host, self._port)
        PID_DIR.mkdir(parents=True, exist_ok=True)
        PID_FILE.write_text(str(os.getpid()))

        loop = asyncio.get_event_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, self._handle_signal, sig)

        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())

        try:
            from .server import create_app
            import uvicorn

            app = create_app(self)
            config = uvicorn.Config(app, host=self._host, port=self._port, log_level="info")
            server = uvicorn.Server(config)
            self._server_task = asyncio.create_task(server.serve())
            logger.info("AgentDaemon HTTP server started on %s:%d", self._host, self._port)
            await self._shutdown_event.wait()
            await self._graceful_shutdown()
        finally:
            self._remove_pid()

    async def _graceful_shutdown(self) -> None:
        logger.info("Starting graceful shutdown...")
        if self._heartbeat_task and not self._heartbeat_task.done():
            self._heartbeat_task.cancel()
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
        if self._server_task and not self._server_task.done():
            self._server_task.cancel()
        await self._session_manager.shutdown()
        logger.info("Graceful shutdown complete")

    def _handle_signal(self, sig: signal.Signals) -> None:
        logger.info("Received signal %s, initiating shutdown", sig.name)
        self._shutdown_event.set()

    async def _heartbeat_loop(self) -> None:
        try:
            while True:
                sessions = self._session_manager.list_sessions()
                for s in sessions:
                    if s.status.value == "running":
                        logger.debug("Heartbeat: session %s is running", s.session_id)
                await asyncio.sleep(10.0)
        except asyncio.CancelledError:
            logger.info("Heartbeat loop cancelled")

    async def _cleanup_loop(self) -> None:
        try:
            while True:
                sessions = self._session_manager.list_sessions()
                for s in sessions:
                    if s.status.value == "stopped":
                        checkpoints = self._state_serializer.list_checkpoints(s.session_id)
                        if len(checkpoints) > 10:
                            pruned = self._state_serializer.prune_checkpoints(s.session_id, keep_last=5)
                            logger.info("Cleanup: pruned %d checkpoints for session %s", pruned, s.session_id)
                await asyncio.sleep(300.0)
        except asyncio.CancelledError:
            logger.info("Cleanup loop cancelled")

    def _remove_pid(self) -> None:
        try:
            PID_FILE.unlink(missing_ok=True)
        except OSError:
            pass

    @staticmethod
    def is_running() -> bool:
        if not PID_FILE.exists():
            return False
        try:
            pid = int(PID_FILE.read_text().strip())
            os.kill(pid, 0)
            return True
        except (ProcessLookupError, ValueError, OSError):
            try:
                PID_FILE.unlink(missing_ok=True)
            except OSError:
                pass
            return False

    @staticmethod
    def stop_running() -> bool:
        if not PID_FILE.exists():
            return False
        try:
            pid = int(PID_FILE.read_text().strip())
            os.kill(pid, signal.SIGTERM)
            logger.info("Sent SIGTERM to agentd (pid=%d)", pid)
            return True
        except ProcessLookupError:
            PID_FILE.unlink(missing_ok=True)
            return False
        except (ValueError, OSError) as e:
            logger.error("Failed to stop agentd: %s", e)
            return False
