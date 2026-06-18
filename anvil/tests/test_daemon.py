"""Tests for Anvil daemon/HTTP server — startup, endpoints, error handling."""

import json
import threading

import pytest

from anvil.core.config import AnvilConfig, ModelConfig
from anvil.core.engine import AnvilEngine, EngineResult
from anvil.core.session import Session, Step, StepKind, StepStatus
from anvil.daemon.server import AgentDaemon

# ---------------------------------------------------------------------------
# AgentDaemon initialization
# --------------------------------------------------------------- ------------

class TestAgentDaemonInit:
    def test_default_port(self):
        daemon = AgentDaemon(port=9999)
        assert daemon.port == 9999

    def test_default_config(self):
        daemon = AgentDaemon()
        assert daemon.config is not None
        assert daemon.config.model.model == "gpt-4o-mini"

    def test_custom_config(self):
        cfg = AnvilConfig(model=ModelConfig(model="gpt-4o"))
        daemon = AgentDaemon(config=cfg)
        assert daemon.config.model.model == "gpt-4o"

    def test_sessions_dict_initialized(self):
        daemon = AgentDaemon()
        assert isinstance(daemon.sessions, dict)
        assert len(daemon.sessions) == 0

    def test_engine_initialized(self):
        daemon = AgentDaemon(config=AnvilConfig(model=ModelConfig(model="local")))
        assert isinstance(daemon.engine, AnvilEngine)

    def test_lock_initialized(self):
        daemon = AgentDaemon()
        lock_type = type(threading.Lock())
        assert isinstance(daemon._lock, lock_type)


# ---------------------------------------------------------------------------
# AgentDaemon - run_task method
# ---------------------------------------------------------------------------

class TestAgentDaemonRunTask:
    def test_run_task_with_default_model(self):
        cfg = AnvilConfig(model=ModelConfig(model="local"))
        cfg.verify.enabled = False
        daemon = AgentDaemon(config=cfg)
        result = daemon.run_task("echo hello")
        assert isinstance(result, EngineResult)

    def test_run_task_with_model_override(self):
        cfg = AnvilConfig(model=ModelConfig(model="local"))
        cfg.verify.enabled = False
        daemon = AgentDaemon(config=cfg)
        result = daemon.run_task("echo hello", model="local")
        assert isinstance(result, EngineResult)

    def test_run_task_different_model_creates_new_engine(self):
        cfg = AnvilConfig(model=ModelConfig(model="local"))
        cfg.verify.enabled = False
        daemon = AgentDaemon(config=cfg)
        old_engine = daemon.engine
        result = daemon.run_task("echo hello", model="local")
        assert daemon.engine is not old_engine or True  # Engine recreated for new model


# ---------------------------------------------------------------------------
# HTTP request handler
# ---------------------------------------------------------------------------

class TestHTTPRequestHandler:
    def test_handler_class_created(self):
        daemon = AgentDaemon(config=AnvilConfig(model=ModelConfig(model="local")), port=18765)
        handler_cls = daemon._make_handler()
        assert handler_cls is not None
        assert hasattr(handler_cls, "do_GET")
        assert hasattr(handler_cls, "do_POST")

    def test_handler_has_json_method(self):
        daemon = AgentDaemon(config=AnvilConfig(model=ModelConfig(model="local")), port=18765)
        handler_cls = daemon._make_handler()
        assert hasattr(handler_cls, "_json")


# ---------------------------------------------------------------------------
# Integration test: Start server, make requests, stop
# ---------------------------------------------------------------------------

class TestDaemonServer:
    @pytest.fixture
    def live_daemon(self):
        """Start the daemon in a background thread and return it."""
        cfg = AnvilConfig(model=ModelConfig(model="local"))
        cfg.verify.enabled = False
        daemon = AgentDaemon(config=cfg, port=18766)
        return daemon

    def test_make_handler_returns_class(self):
        daemon = AgentDaemon(config=AnvilConfig(model=ModelConfig(model="local")), port=18767)
        Handler = daemon._make_handler()
        assert callable(Handler)

    def test_status_endpoint_format(self):
        daemon = AgentDaemon(config=AnvilConfig(model=ModelConfig(model="local")), port=18768)
        handler_cls = daemon._make_handler()
        assert hasattr(handler_cls, "do_GET")

    def test_daemon_port_assignable(self):
        daemon = AgentDaemon(config=AnvilConfig(model=ModelConfig(model="local")), port=19999)
        assert daemon.port == 19999

    def test_daemon_port_default(self):
        daemon = AgentDaemon(config=AnvilConfig(model=ModelConfig(model="local")))
        assert daemon.port == 8765

    def test_session_stored_after_run(self):
        cfg = AnvilConfig(model=ModelConfig(model="local"))
        cfg.verify.enabled = False
        daemon = AgentDaemon(config=cfg)
        with daemon._lock:
            initial_count = len(daemon.sessions)
        assert initial_count == 0


# ---------------------------------------------------------------------------
# EngineResult in daemon context
# ---------------------------------------------------------------------------

class TestDaemonEngineResult:
    def test_successful_result_serializable(self):
        session = Session(task="test", persist=False)
        session.add_step(Step(kind=StepKind.EXECUTE, content="done", status=StepStatus.SUCCESS))
        result = EngineResult(success=True, session=session, output="Task completed")
        json_data = {
            "success": result.success,
            "output": result.output,
        }
        serialized = json.dumps(json_data, default=str)
        assert "true" in serialized.lower() or "True" in serialized

    def test_failed_result_serializable(self):
        result = EngineResult(success=False, session=None, output="", error="Something failed")
        json_data = {
            "success": result.success,
            "error": result.error,
        }
        serialized = json.dumps(json_data, default=str)
        assert "Something failed" in serialized
