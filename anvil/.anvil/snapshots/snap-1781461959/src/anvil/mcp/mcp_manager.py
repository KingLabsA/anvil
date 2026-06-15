"""MCP Server Manager — register, start, stop, and communicate with MCP servers."""

from __future__ import annotations

import json
import os
import subprocess
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from anvil.mcp.mcp_types import (
    JSONRPCRequest,
    JSONRPCResponse,
    MCPCallResult,
    MCPToolDefinition,
)

try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False


@dataclass
class MCPServer:
    """Configuration for an MCP server connection."""
    name: str
    type: str = "local"  # "local" or "remote"
    command: str = ""
    args: list[str] = field(default_factory=list)
    url: str = ""
    headers: dict[str, str] = field(default_factory=dict)
    environment: dict[str, str] = field(default_factory=dict)
    enabled: bool = True
    timeout: int = 5

    _process: Any | None = field(default=None, repr=False, compare=False)
    _stdin: Any | None = field(default=None, repr=False, compare=False)
    _stdout: Any | None = field(default=None, repr=False, compare=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False, compare=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "type": self.type,
            "command": self.command,
            "args": self.args,
            "url": self.url,
            "headers": self.headers,
            "environment": self.environment,
            "enabled": self.enabled,
            "timeout": self.timeout,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MCPServer:
        return cls(
            name=data["name"],
            type=data.get("type", "local"),
            command=data.get("command", ""),
            args=data.get("args", []),
            url=data.get("url", ""),
            headers=data.get("headers", {}),
            environment=data.get("environment", {}),
            enabled=data.get("enabled", True),
            timeout=data.get("timeout", 5),
        )


class MCPManager:
    """Manages MCP server lifecycle and communication."""

    def __init__(self, config_dir: Path | None = None):
        self._servers: dict[str, MCPServer] = {}
        self._discovered_tools: dict[str, list[MCPToolDefinition]] = {}
        self._request_id_counter = 0
        self._id_lock = threading.Lock()
        self.config_dir = config_dir or (Path.home() / ".anvil" / "mcp")

    def register(self, server: MCPServer) -> None:
        """Register an MCP server configuration."""
        self._servers[server.name] = server
        self._discovered_tools.pop(server.name, None)
        self._save_config()

    def unregister(self, name: str) -> bool:
        """Remove a registered MCP server."""
        if name not in self._servers:
            return False
        self.stop_server(name)
        del self._servers[name]
        self._discovered_tools.pop(name, None)
        self._save_config()
        return True

    def list_servers(self) -> list[MCPServer]:
        """List all registered MCP servers."""
        return list(self._servers.values())

    def get_server(self, name: str) -> MCPServer | None:
        """Get a server by name."""
        return self._servers.get(name)

    def start_server(self, name: str) -> MCPCallResult:
        """Start a local MCP server subprocess."""
        server = self._servers.get(name)
        if not server:
            return MCPCallResult.from_error(f"Server '{name}' not registered")
        if server.type == "remote":
            return MCPCallResult.from_text("Remote server — no subprocess needed")
        if not server.command:
            return MCPCallResult.from_error(f"Server '{name}' has no command configured")

        with server._lock:
            if server._process is not None and server._process.poll() is None:
                return MCPCallResult.from_text(f"Server '{name}' already running")

            env = {**os.environ, **server.environment}
            try:
                proc = subprocess.Popen(
                    [server.command, *server.args],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    env=env,
                    bufsize=0,
                )
                server._process = proc
                server._stdin = proc.stdin
                server._stdout = proc.stdout
                time.sleep(0.2)
                if proc.poll() is not None and proc.returncode != 0:
                    stderr = proc.stderr.read().decode("utf-8", errors="replace")[:2000]
                    server._process = None
                    server._stdin = None
                    server._stdout = None
                    return MCPCallResult.from_error(f"Server '{name}' exited with code {proc.returncode}: {stderr}")
            except FileNotFoundError:
                return MCPCallResult.from_error(f"Command not found: {server.command}")
            except Exception as e:
                return MCPCallResult.from_error(f"Failed to start '{name}': {e}")

        return MCPCallResult.from_text(f"Server '{name}' started (PID: {proc.pid})")

    def stop_server(self, name: str) -> MCPCallResult:
        """Stop a local MCP server subprocess."""
        server = self._servers.get(name)
        if not server:
            return MCPCallResult.from_error(f"Server '{name}' not registered")
        if server.type == "remote":
            return MCPCallResult.from_text("Remote server — no subprocess to stop")

        with server._lock:
            if server._process is None:
                return MCPCallResult.from_text(f"Server '{name}' not running")

            proc = server._process
            try:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=2)
            except Exception:
                pass
            finally:
                server._process = None
                server._stdin = None
                server._stdout = None

        return MCPCallResult.from_text(f"Server '{name}' stopped")

    def list_tools(self, server_name: str) -> list[MCPToolDefinition]:
        """Discover tools from an MCP server via JSON-RPC."""
        server = self._servers.get(server_name)
        if not server:
            return []

        cache = self._discovered_tools.get(server_name)
        if cache is not None:
            return cache

        tools = self._discover_tools(server)
        self._discovered_tools[server_name] = tools
        return tools

    def call_tool(self, server_name: str, tool_name: str, args: dict[str, Any]) -> MCPCallResult:
        """Invoke an MCP tool on a server."""
        server = self._servers.get(server_name)
        if not server:
            return MCPCallResult.from_error(f"Server '{server_name}' not registered")

        prefixed_name = f"{server_name}_{tool_name}"

        if server.type == "remote":
            return self._call_remote_tool(server, tool_name, args)
        return self._call_local_tool(server, tool_name, args)

    def _discover_tools(self, server: MCPServer) -> list[MCPToolDefinition]:
        """Send a tools/list request to discover available tools."""
        if server.type == "remote":
            return self._discover_remote_tools(server)
        return self._discover_local_tools(server)

    def _next_id(self) -> str:
        with self._id_lock:
            self._request_id_counter += 1
            return f"anvil-mcp-{self._request_id_counter}"

    def _discover_local_tools(self, server: MCPServer) -> list[MCPToolDefinition]:
        """Discover tools from a local MCP server via stdio JSON-RPC."""
        if not server._process or server._process.poll() is not None:
            start_result = self.start_server(server.name)
            if start_result.is_error:
                return []

        request = JSONRPCRequest(
            method="tools/list",
            params={},
            id=self._next_id(),
        )

        response = self._send_local_request(server, request, timeout=server.timeout)
        if response is None or response.is_error:
            return []

        result = response.result or {}
        tool_list = result.get("tools", [])
        return [MCPToolDefinition.from_dict(t) for t in tool_list]

    def _discover_remote_tools(self, server: MCPServer) -> list[MCPToolDefinition]:
        """Discover tools from a remote MCP server via HTTP."""
        if not HAS_HTTPX:
            return []
        try:
            headers = {"Content-Type": "application/json", **server.headers}
            request = JSONRPCRequest(method="tools/list", params={}, id=self._next_id())
            resp = httpx.post(
                server.url,
                json=request.to_dict(),
                headers=headers,
                timeout=server.timeout,
            )
            if resp.status_code == 401:
                return []
            resp.raise_for_status()
            data = resp.json()
            if "error" in data:
                return []
            result = data.get("result", {})
            return [MCPToolDefinition.from_dict(t) for t in result.get("tools", [])]
        except Exception:
            return []

    def _call_remote_tool(self, server: MCPServer, tool_name: str, args: dict[str, Any]) -> MCPCallResult:
        """Call a tool on a remote MCP server via HTTP."""
        if not HAS_HTTPX:
            return MCPCallResult.from_error("httpx not installed — cannot call remote MCP servers")
        request = JSONRPCRequest(
            method="tools/call",
            params={"name": tool_name, "arguments": args},
            id=self._next_id(),
        )
        headers = {"Content-Type": "application/json", **server.headers}
        try:
            resp = httpx.post(
                server.url,
                json=request.to_dict(),
                headers=headers,
                timeout=server.timeout * 6,
            )
            if resp.status_code == 401:
                return MCPCallResult.from_error(
                    f"Authentication required for '{server.name}'. "
                    "OAuth flow initiation is needed — configure credentials in server headers."
                )
            resp.raise_for_status()
            data = resp.json()
            if "error" in data:
                err = data["error"]
                return MCPCallResult.from_error(f"Server error ({err.get('code')}): {err.get('message')}")
            result = data.get("result", {})
            return MCPCallResult.from_dict(result)
        except httpx.TimeoutException:
            return MCPCallResult.from_error(f"Timeout calling '{tool_name}' on '{server.name}'")
        except Exception as e:
            return MCPCallResult.from_error(f"Failed to call '{tool_name}' on '{server.name}': {e}")

    def _call_local_tool(self, server: MCPServer, tool_name: str, args: dict[str, Any]) -> MCPCallResult:
        """Call a tool on a local MCP server via stdio JSON-RPC."""
        if not server._process or server._process.poll() is not None:
            start_result = self.start_server(server.name)
            if start_result.is_error:
                return MCPCallResult.from_error(f"Cannot start server: {start_result.text}")

        request = JSONRPCRequest(
            method="tools/call",
            params={"name": tool_name, "arguments": args},
            id=self._next_id(),
        )

        response = self._send_local_request(server, request, timeout=server.timeout * 6)
        if response is None:
            return MCPCallResult.from_error(f"No response from '{server.name}'")
        if response.is_error:
            return MCPCallResult.from_error(f"Server error: {response.error_message}")

        result = response.result or {}
        return MCPCallResult.from_dict(result)

    def _send_local_request(
        self, server: MCPServer, request: JSONRPCRequest, timeout: int = 5
    ) -> JSONRPCResponse | None:
        """Send a JSON-RPC request to a local server via stdin/stdout."""
        if server._stdin is None or server._stdout is None:
            return None

        try:
            msg = request.to_json() + "\n"
            server._stdin.write(msg.encode("utf-8"))
            server._stdin.flush()

            response_lines = []
            deadline = time.time() + timeout

            while time.time() < deadline:
                line = server._stdout.readline()
                if line:
                    response_lines.append(line)
                    try:
                        data = json.loads("".join(response_lines).decode("utf-8") if isinstance(response_lines[0], bytes) else "".join(response_lines))
                        return JSONRPCResponse.from_dict(data)
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        if response_lines:
                            try:
                                combined = ""
                                for l in response_lines:
                                    combined += l if isinstance(l, str) else l.decode("utf-8", errors="replace")
                                data = json.loads(combined)
                                return JSONRPCResponse.from_dict(data)
                            except json.JSONDecodeError:
                                continue
                else:
                    time.sleep(0.05)

            return JSONRPCResponse.make_error(-32000, "Timeout waiting for response", request.id)
        except Exception as e:
            return JSONRPCResponse.make_error(-32000, f"Communication error: {e}", request.id)

    def _save_config(self) -> None:
        """Persist server configurations to disk."""
        self.config_dir.mkdir(parents=True, exist_ok=True)
        config_file = self.config_dir / "servers.json"
        data = {name: server.to_dict() for name, server in self._servers.items()}
        config_file.write_text(json.dumps(data, indent=2))

    def load_config(self) -> None:
        """Load server configurations from disk."""
        config_file = self.config_dir / "servers.json"
        if not config_file.exists():
            return
        try:
            data = json.loads(config_file.read_text())
            for name, server_data in data.items():
                self._servers[name] = MCPServer.from_dict(server_data)
        except (json.JSONDecodeError, KeyError):
            pass

    def shutdown_all(self) -> None:
        """Stop all running servers."""
        for name in list(self._servers.keys()):
            if self._servers[name].type == "local":
                self.stop_server(name)
