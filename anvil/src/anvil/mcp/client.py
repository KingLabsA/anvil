"""MCP Client — connect to external MCP servers via stdio or HTTP.

Provides a unified interface for discovering and calling tools on
remote MCP servers, whether they run as local subprocesses (stdio)
or as HTTP endpoints.
"""

from __future__ import annotations

import json
import os
import subprocess
import threading
import time
from typing import Any

from anvil.mcp.protocol import (
    CallResult,
    MCPError,
    MCPRequest,
    MCPResponse,
    ResourceDefinition,
    ToolDefinition,
    TOOLS_CALL,
    TOOLS_LIST,
    RESOURCES_LIST,
    RESOURCES_READ,
)

try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False


class MCPClient:
    """Client for connecting to an MCP server via stdio or HTTP."""

    def __init__(
        self,
        server_command: str | None = None,
        server_args: list[str] | None = None,
        server_url: str | None = None,
        env: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
        timeout: int = 30,
    ):
        self._server_command = server_command
        self._server_args = server_args or []
        self._server_url = server_url
        self._env = env or {}
        self._headers = headers or {}
        self._timeout = timeout

        self._process: subprocess.Popen | None = None
        self._stdin: Any = None
        self._stdout: Any = None
        self._lock = threading.Lock()
        self._request_id = 0
        self._id_lock = threading.Lock()
        self._connected = False

    @property
    def is_stdio(self) -> bool:
        return self._server_command is not None

    @property
    def is_http(self) -> bool:
        return self._server_url is not None

    @property
    def connected(self) -> bool:
        return self._connected

    def _next_id(self) -> str:
        with self._id_lock:
            self._request_id += 1
            return f"mcp-client-{self._request_id}"

    def connect(self) -> bool:
        if self.is_stdio:
            return self._connect_stdio()
        if self.is_http:
            self._connected = True
            return True
        return False

    def _connect_stdio(self) -> bool:
        if not self._server_command:
            return False
        with self._lock:
            if self._process is not None and self._process.poll() is None:
                self._connected = True
                return True
            full_env = {**os.environ, **self._env}
            try:
                proc = subprocess.Popen(
                    [self._server_command, *self._server_args],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    env=full_env,
                    bufsize=0,
                )
                self._process = proc
                self._stdin = proc.stdin
                self._stdout = proc.stdout
                time.sleep(0.2)
                if proc.poll() is not None and proc.returncode != 0:
                    stderr_data = proc.stderr.read().decode("utf-8", errors="replace")[:2000]
                    self._process = None
                    self._stdin = None
                    self._stdout = None
                    return False
                self._connected = True
                return True
            except (FileNotFoundError, OSError):
                return False

    def disconnect(self) -> None:
        with self._lock:
            if self._process is not None:
                try:
                    self._process.terminate()
                    try:
                        self._process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        self._process.kill()
                        self._process.wait(timeout=2)
                except Exception:
                    pass
                finally:
                    self._process = None
                    self._stdin = None
                    self._stdout = None
                    self._connected = False

    def list_tools(self) -> list[ToolDefinition]:
        response = self._send_request(TOOLS_LIST, {})
        if response is None:
            return []
        result = response.result if isinstance(response, MCPResponse) else {}
        tools_data = result.get("tools", [])
        return [ToolDefinition.from_dict(t) for t in tools_data]

    def call_tool(self, name: str, arguments: dict[str, Any]) -> CallResult:
        response = self._send_request(TOOLS_CALL, {"name": name, "arguments": arguments})
        if response is None:
            return CallResult.from_error("No response from MCP server")
        if isinstance(response, MCPError):
            return CallResult.from_error(response.error.get("message", "Unknown error"))
        result = response.result if isinstance(response, MCPResponse) else {}
        return CallResult.from_dict(result)

    def list_resources(self) -> list[ResourceDefinition]:
        response = self._send_request(RESOURCES_LIST, {})
        if response is None:
            return []
        result = response.result if isinstance(response, MCPResponse) else {}
        resources_data = result.get("resources", [])
        return [ResourceDefinition.from_dict(r) for r in resources_data]

    def read_resource(self, uri: str) -> dict[str, Any]:
        response = self._send_request(RESOURCES_READ, {"uri": uri})
        if response is None:
            return {"error": "No response from MCP server"}
        if isinstance(response, MCPError):
            return {"error": response.error.get("message", "Unknown error")}
        return response.result if isinstance(response, MCPResponse) else {}

    def _send_request(self, method: str, params: dict[str, Any]) -> MCPResponse | MCPError | None:
        if self.is_stdio:
            return self._send_stdio(method, params)
        if self.is_http:
            return self._send_http(method, params)
        return None

    def _send_stdio(self, method: str, params: dict[str, Any]) -> MCPResponse | MCPError | None:
        if not self._connected:
            if not self.connect():
                return None

        request = MCPRequest.create(method, params)
        msg = request.to_json() + "\n"

        with self._lock:
            if self._stdin is None or self._stdout is None:
                return None
            try:
                self._stdin.write(msg.encode("utf-8"))
                self._stdin.flush()

                response_lines: list[str] = []
                deadline = time.time() + self._timeout

                while time.time() < deadline:
                    line = self._stdout.readline()
                    if line:
                        decoded = line.decode("utf-8", errors="replace") if isinstance(line, bytes) else line
                        response_lines.append(decoded)
                        try:
                            combined = "".join(response_lines).strip()
                            data = json.loads(combined)
                            if "error" in data:
                                return MCPError.from_dict(data)
                            return MCPResponse.from_dict(data)
                        except json.JSONDecodeError:
                            continue
                    else:
                        time.sleep(0.05)

                return MCPError.make(-32000, "Timeout waiting for response", id=request.id)
            except Exception as e:
                return MCPError.make(-32000, f"Communication error: {e}", id=request.id)

    def _send_http(self, method: str, params: dict[str, Any]) -> MCPResponse | MCPError | None:
        if not HAS_HTTPX:
            return MCPError.make(-32000, "httpx not installed")

        request = MCPRequest.create(method, params)
        headers = {"Content-Type": "application/json", **self._headers}

        try:
            resp = httpx.post(
                self._server_url,
                json=request.to_dict(),
                headers=headers,
                timeout=self._timeout,
            )
            if resp.status_code == 401:
                return MCPError.make(-32000, "Authentication required")
            resp.raise_for_status()
            data = resp.json()
            if "error" in data:
                return MCPError.from_dict(data)
            return MCPResponse.from_dict(data)
        except httpx.TimeoutException:
            return MCPError.make(-32000, "Request timed out")
        except Exception as e:
            return MCPError.make(-32000, f"HTTP error: {e}")

    def __enter__(self) -> MCPClient:
        self.connect()
        return self

    def __exit__(self, *args: Any) -> None:
        self.disconnect()
