"""Daemon mode — persistent Anvil agent as a local server."""

from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse

from anvil.core.config import AnvilConfig
from anvil.core.engine import AnvilEngine, EngineResult


class AgentDaemon:
    def __init__(self, config: AnvilConfig | None = None, port: int = 8765):
        self.config = config or AnvilConfig()
        self.port = port
        self.engine = AnvilEngine(self.config)
        self.sessions: dict[str, dict] = {}
        self._lock = threading.Lock()

    def start(self) -> None:
        server = HTTPServer(("localhost", self.port), self._make_handler())
        print(f"Anvil daemon running on http://localhost:{self.port}")
        print("  POST /run        — Execute a task")
        print("  GET  /status     — Check daemon status")
        print("  GET  /sessions   — List sessions")
        print("  GET  /session/:id — Get session details")
        print("  POST /stop       — Stop the daemon")
        server.serve_forever()

    def _make_handler(self):
        daemon = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                path = urlparse(self.path).path
                if path == "/status":
                    self._json({"status": "running", "model": daemon.config.model.model, "uptime": True})
                elif path == "/sessions":
                    self._json({"sessions": list(daemon.sessions.keys())})
                elif path.startswith("/session/"):
                    sid = path.split("/session/")[1]
                    self._json(daemon.sessions.get(sid, {"error": "not found"}))
                else:
                    self._json({"error": "not found"}, 404)

            def do_POST(self):
                path = urlparse(self.path).path
                length = int(self.headers.get("Content-Length", 0))
                body = json.loads(self.rfile.read(length)) if length else {}

                if path == "/run":
                    task = body.get("task", "")
                    model = body.get("model", daemon.config.model.model)
                    if model != daemon.config.model.model:
                        daemon.config.model.model = model
                        daemon.engine = AnvilEngine(daemon.config)
                    result = daemon.engine.run(task)
                    session_data = result.session.summary() if result.session else {}
                    with daemon._lock:
                        if result.session:
                            daemon.sessions[result.session.id] = session_data
                    self._json({
                        "success": result.success,
                        "output": result.output,
                        "verify_report": result.verify_report.format_summary() if result.verify_report else None,
                        "session": session_data,
                    })
                elif path == "/stop":
                    self._json({"status": "stopping"})
                    threading.Thread(target=lambda: time.sleep(0.5) or self.server.shutdown()).start()
                else:
                    self._json({"error": "not found"}, 404)

            def _json(self, data, code=200):
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(data, default=str).encode())

            def log_message(self, format, *args):
                pass

        return Handler

    def run_task(self, task: str, model: str | None = None) -> EngineResult:
        if model and model != self.config.model.model:
            self.config.model.model = model
            self.engine = AnvilEngine(self.config)
        return self.engine.run(task)
