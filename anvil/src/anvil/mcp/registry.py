"""MCP Tool Registry — discovers and manages tools from MCP servers and built-ins.

Integrates external MCP server tools with Anvil's engine, providing a
unified tool interface that agents can use without knowing the source.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from anvil.mcp.client import MCPClient
from anvil.mcp.protocol import CallResult, ToolDefinition
from anvil.mcp.tools import get_builtin_tool_definitions, get_builtin_tool_handler


class MCPToolRegistry:
    """Unified tool registry that combines built-in tools with MCP server tools."""

    def __init__(self, anvil_engine: Any = None):
        self.anvil = anvil_engine
        self._mcp_clients: dict[str, MCPClient] = {}
        self._server_configs: list[dict[str, Any]] = []
        self._tools: dict[str, tuple[ToolDefinition, str]] = {}
        self._builtin_tools: dict[str, ToolDefinition] = {}
        self._discovered = False

        for defn in get_builtin_tool_definitions():
            self._builtin_tools[defn.name] = defn
            self._tools[defn.name] = (defn, "__builtin__")

    def register_mcp_server(self, server_config: dict[str, Any]) -> None:
        """Register an MCP server from a config dict.

        Expected keys:
            name: str — unique server identifier
            command: str — executable to launch (for stdio servers)
            args: list[str] — command arguments
            url: str — HTTP endpoint (for remote servers)
            env: dict[str, str] — environment variables
            headers: dict[str, str] — HTTP headers
            timeout: int — request timeout in seconds
        """
        self._server_configs.append(server_config)
        self._discovered = False

    def register_mcp_server_from_file(self, config_path: str | Path) -> None:
        """Register MCP servers from a JSON config file."""
        path = Path(config_path).expanduser()
        if not path.exists():
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return

        servers = data.get("servers", [])
        if isinstance(servers, list):
            for server in servers:
                if "name" in server:
                    self.register_mcp_server(server)

    def discover_tools(self) -> None:
        """Discover tools from all registered MCP servers."""
        for config in self._server_configs:
            name = config.get("name", "")
            if not name:
                continue
            if name in self._mcp_clients:
                continue

            client = self._create_client(config)
            if client is None:
                continue

            self._mcp_clients[name] = client

            try:
                tools = client.list_tools()
                for tool_def in tools:
                    prefixed = f"{name}__{tool_def.name}"
                    self._tools[prefixed] = (tool_def, name)
            except Exception:
                pass

        self._discovered = True

    def _create_client(self, config: dict[str, Any]) -> MCPClient | None:
        command = config.get("command")
        args = config.get("args", [])
        url = config.get("url")
        env = config.get("env", {})
        headers = config.get("headers", {})
        timeout = config.get("timeout", 30)

        resolved_env = {}
        for k, v in env.items():
            if isinstance(v, str) and v.startswith("${") and v.endswith("}"):
                env_var = v[2:-1]
                resolved_env[k] = os.environ.get(env_var, "")
            else:
                resolved_env[k] = v

        if command:
            return MCPClient(
                server_command=command,
                server_args=args,
                env=resolved_env,
                timeout=timeout,
            )
        if url:
            return MCPClient(
                server_url=url,
                headers=headers,
                timeout=timeout,
            )
        return None

    def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> CallResult:
        """Call a tool by name — routes to built-in or MCP server."""
        if tool_name in self._builtin_tools:
            handler = get_builtin_tool_handler(tool_name)
            if handler is None:
                return CallResult.from_error(f"No handler for built-in tool: {tool_name}")
            try:
                return handler(**arguments)
            except TypeError as e:
                return CallResult.from_error(f"Invalid arguments for {tool_name}: {e}")
            except Exception as e:
                return CallResult.from_error(f"Tool execution failed: {e}")

        if not self._discovered:
            self.discover_tools()

        entry = self._tools.get(tool_name)
        if entry is None:
            return CallResult.from_error(f"Unknown tool: {tool_name}")

        tool_def, server_name = entry
        if server_name == "__builtin__":
            handler = get_builtin_tool_handler(tool_def.name)
            if handler:
                try:
                    return handler(**arguments)
                except Exception as e:
                    return CallResult.from_error(f"Tool execution failed: {e}")
            return CallResult.from_error(f"No handler for tool: {tool_def.name}")

        client = self._mcp_clients.get(server_name)
        if client is None:
            return CallResult.from_error(f"MCP server '{server_name}' not connected")

        original_name = tool_def.name
        if "__" in tool_name:
            original_name = tool_name.split("__", 1)[1]

        return client.call_tool(original_name, arguments)

    def get_available_tools(self) -> list[dict[str, Any]]:
        """Get list of all available tools in MCP format."""
        if not self._discovered:
            self.discover_tools()

        tools: list[dict[str, Any]] = []
        seen: set[str] = set()

        for tool_name, (tool_def, _server) in self._tools.items():
            if tool_name in seen:
                continue
            seen.add(tool_name)
            tools.append(tool_def.to_dict())

        return tools

    def get_tool_names(self) -> list[str]:
        """Get list of all tool names."""
        if not self._discovered:
            self.discover_tools()
        return list(self._tools.keys())

    def shutdown(self) -> None:
        """Disconnect all MCP server clients."""
        for client in self._mcp_clients.values():
            try:
                client.disconnect()
            except Exception:
                pass
        self._mcp_clients.clear()
