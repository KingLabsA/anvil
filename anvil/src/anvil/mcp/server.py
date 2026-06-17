"""MCP (Model Context Protocol) server for Anvil.

This module implements an MCP server that exposes Anvil's capabilities
to other AI agents and tools via the Model Context Protocol.
Supports both stdio and HTTP transports.
"""

from __future__ import annotations

import json
import sys
import threading
from typing import Any, Callable
from pathlib import Path

from anvil.mcp.protocol import (
    MCPError,
    MCPRequest,
    MCPResponse,
    ResourceDefinition,
    ToolDefinition,
    PromptDefinition,
    CallResult,
    INITIALIZE,
    SHUTDOWN,
    TOOLS_LIST,
    TOOLS_CALL,
    RESOURCES_LIST,
    RESOURCES_READ,
    PROMPTS_LIST,
    PROMPTS_GET,
)


class AnvilMCPServer:
    """MCP server that exposes Anvil's capabilities via the Model Context Protocol."""

    def __init__(self, config: Any | None = None):
        self.config = config
        self._tools: dict[str, dict[str, Any]] = {}
        self._tool_handlers: dict[str, Callable] = {}
        self._resources: dict[str, dict[str, Any]] = {}
        self._resource_handlers: dict[str, Callable] = {}
        self._prompts: dict[str, dict[str, Any]] = {}
        self._prompt_handlers: dict[str, Callable] = {}
        self._initialized = False
        self._engine: Any = None
        self._memory: Any = None
        self._register_default_tools()
        self._register_default_resources()
        self._register_default_prompts()

    def _get_engine(self) -> Any:
        if self._engine is None:
            from anvil.core.engine import AnvilEngine
            from anvil.core.config import AnvilConfig
            cfg = self.config or AnvilConfig()
            self._engine = AnvilEngine(cfg)
        return self._engine

    def _get_memory(self) -> Any:
        if self._memory is None:
            from anvil.memory.manager import MemoryManager
            self._memory = MemoryManager()
        return self._memory

    def register_tool(
        self,
        name: str,
        description: str,
        handler: Callable,
        input_schema: dict[str, Any] | None = None,
    ) -> None:
        self._tools[name] = ToolDefinition(
            name=name, description=description, input_schema=input_schema or {}
        ).to_dict()
        self._tool_handlers[name] = handler

    def register_resource(
        self,
        uri: str,
        handler: Callable,
        name: str = "",
        description: str = "",
        mime_type: str = "text/plain",
    ) -> None:
        self._resources[uri] = ResourceDefinition(
            uri=uri, name=name, description=description, mime_type=mime_type
        ).to_dict()
        self._resource_handlers[uri] = handler

    def register_prompt(
        self,
        name: str,
        handler: Callable,
        description: str = "",
        arguments: list[dict[str, Any]] | None = None,
    ) -> None:
        self._prompts[name] = PromptDefinition(
            name=name, description=description, arguments=arguments or []
        ).to_dict()
        self._prompt_handlers[name] = handler

    def _register_default_tools(self) -> None:
        self.register_tool(
            "run_task",
            "Execute a coding task with self-verification",
            self._call_run_task,
            {
                "type": "object",
                "properties": {
                    "task": {"type": "string", "description": "Task description"},
                    "model": {"type": "string", "description": "Model to use (optional)"},
                    "max_iterations": {"type": "integer", "description": "Maximum iterations (optional)"},
                },
                "required": ["task"],
            },
        )
        self.register_tool(
            "verify_code",
            "Verify code without making changes",
            self._call_verify_code,
            {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to verify"},
                    "checks": {"type": "array", "items": {"type": "string"}, "description": "Checks to run"},
                },
                "required": ["path"],
            },
        )
        self.register_tool(
            "recall_memory",
            "Recall relevant memories for a query",
            self._call_recall_memory,
            {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Query to recall memories for"},
                    "limit": {"type": "integer", "description": "Maximum memories to return"},
                },
                "required": ["query"],
            },
        )
        self.register_tool(
            "add_memory",
            "Add a new memory",
            self._call_add_memory,
            {
                "type": "object",
                "properties": {
                    "category": {"type": "string", "enum": ["preference", "project", "pattern", "mistake", "fact"]},
                    "content": {"type": "string", "description": "Memory content"},
                    "context": {"type": "string", "description": "Context (optional)"},
                    "importance": {"type": "number", "description": "Importance 0.0-1.0 (optional)"},
                },
                "required": ["category", "content"],
            },
        )

    def _register_default_resources(self) -> None:
        self.register_resource(
            "anvil://config",
            lambda: json.dumps(self.config.__dict__ if self.config else {}, indent=2, default=str),
            name="Anvil Configuration",
            description="Current Anvil configuration",
            mime_type="application/json",
        )
        self.register_resource(
            "anvil://memories",
            lambda: json.dumps([m.to_dict() for m in self._get_memory().list()], indent=2),
            name="Agent Memories",
            description="All stored memories",
            mime_type="application/json",
        )

    def _register_default_prompts(self) -> None:
        self.register_prompt(
            "coding_task",
            lambda args: f"Execute this coding task with self-verification: {args.get('task', '')}",
            description="Execute a coding task with verification",
            arguments=[{"name": "task", "description": "Task description", "required": True}],
        )
        self.register_prompt(
            "code_review",
            lambda args: f"Review this code for issues: {args.get('path', '')}",
            description="Review code for issues",
            arguments=[{"name": "path", "description": "Path to review", "required": True}],
        )

    def handle_request(self, request: dict[str, Any]) -> dict[str, Any]:
        """Handle an MCP request and return a JSON-RPC response."""
        method = request.get("method", "")
        params = request.get("params", {})
        req_id = request.get("id")

        handlers: dict[str, Callable] = {
            INITIALIZE: self._handle_initialize,
            SHUTDOWN: self._handle_shutdown,
            TOOLS_LIST: self._handle_tools_list,
            TOOLS_CALL: self._handle_tools_call,
            RESOURCES_LIST: self._handle_resources_list,
            RESOURCES_READ: self._handle_resources_read,
            PROMPTS_LIST: self._handle_prompts_list,
            PROMPTS_GET: self._handle_prompts_get,
        }

        handler = handlers.get(method)
        if handler:
            try:
                result = handler(params)
                return MCPResponse.make(result, id=req_id).to_dict()
            except Exception as e:
                return MCPError.make(-32000, str(e), id=req_id).to_dict()
        return MCPError.method_not_found(method, id=req_id).to_dict()

    def _handle_initialize(self, params: dict[str, Any]) -> dict[str, Any]:
        self._initialized = True
        return {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}, "resources": {}, "prompts": {}},
            "serverInfo": {"name": "anvil", "version": "0.3.0"},
        }

    def _handle_shutdown(self, params: dict[str, Any]) -> dict[str, Any]:
        self._initialized = False
        return {}

    def _handle_tools_list(self, params: dict[str, Any]) -> dict[str, Any]:
        return {"tools": list(self._tools.values())}

    def _handle_tools_call(self, params: dict[str, Any]) -> dict[str, Any]:
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})
        handler = self._tool_handlers.get(tool_name)
        if handler is None:
            raise ValueError(f"Unknown tool: {tool_name}")
        result = handler(arguments)
        if isinstance(result, dict) and "content" in result:
            return result
        return CallResult.from_text(str(result)).to_dict()

    def _handle_resources_list(self, params: dict[str, Any]) -> dict[str, Any]:
        return {"resources": list(self._resources.values())}

    def _handle_resources_read(self, params: dict[str, Any]) -> dict[str, Any]:
        uri = params.get("uri", "")
        handler = self._resource_handlers.get(uri)
        if handler is None:
            raise ValueError(f"Unknown resource: {uri}")
        text = handler()
        resource_info = self._resources.get(uri, {})
        return {
            "contents": [{
                "uri": uri,
                "mimeType": resource_info.get("mimeType", "text/plain"),
                "text": text,
            }]
        }

    def _handle_prompts_list(self, params: dict[str, Any]) -> dict[str, Any]:
        return {"prompts": list(self._prompts.values())}

    def _handle_prompts_get(self, params: dict[str, Any]) -> dict[str, Any]:
        name = params.get("name", "")
        arguments = params.get("arguments", {})
        handler = self._prompt_handlers.get(name)
        if handler is None:
            raise ValueError(f"Unknown prompt: {name}")
        text = handler(arguments)
        return {
            "messages": [{
                "role": "user",
                "content": {"type": "text", "text": text},
            }]
        }

    def _call_run_task(self, arguments: dict[str, Any]) -> dict[str, Any]:
        task = arguments.get("task", "")
        max_iterations = arguments.get("max_iterations", 20)
        engine = self._get_engine()
        result = engine.run(task, max_iterations=max_iterations)
        return CallResult(
            content=[{"type": "text", "text": result.output or result.error or "Task completed"}],
            is_error=not result.success,
        ).to_dict()

    def _call_verify_code(self, arguments: dict[str, Any]) -> dict[str, Any]:
        from anvil.verify.pipeline import VerifyPipeline
        from anvil.core.config import AnvilConfig
        path = arguments.get("path", "")
        checks = arguments.get("checks", [])
        cfg = self.config or AnvilConfig()
        pipeline = VerifyPipeline(cfg.verify)
        report = pipeline.verify([path], checks=checks if checks else None)
        return CallResult(
            content=[{"type": "text", "text": report.format_summary()}],
            is_error=not report.passed,
        ).to_dict()

    def _call_recall_memory(self, arguments: dict[str, Any]) -> dict[str, Any]:
        query = arguments.get("query", "")
        limit = arguments.get("limit", 5)
        memories = self._get_memory().recall(query, limit=limit)
        if not memories:
            return CallResult.from_text("No memories found").to_dict()
        text = "\n\n".join(f"[{mem.category.value}] {mem.content}" for mem in memories)
        return CallResult.from_text(text).to_dict()

    def _call_add_memory(self, arguments: dict[str, Any]) -> dict[str, Any]:
        from anvil.memory.manager import MemoryCategory
        category = arguments.get("category", "fact")
        content = arguments.get("content", "")
        context = arguments.get("context", "")
        importance = arguments.get("importance", 0.5)
        mem = self._get_memory().add(
            category=MemoryCategory(category),
            content=content,
            context=context,
            importance=importance,
        )
        return CallResult.from_text(f"Memory added: {mem.id}").to_dict()

    def run_stdio(self) -> None:
        """Run server over stdio transport."""
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                request = json.loads(line)
                response = self.handle_request(request)
                print(json.dumps(response), flush=True)
            except json.JSONDecodeError:
                error_resp = MCPError.parse_error().to_dict()
                print(json.dumps(error_resp), flush=True)

    def run_http(self, host: str = "127.0.0.1", port: int = 8080) -> None:
        """Run server over HTTP transport using the stdlib http.server."""
        from http.server import HTTPServer, BaseHTTPRequestHandler

        server_ref = self

        class MCPHTTPHandler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:
                content_length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(content_length)
                try:
                    request = json.loads(body.decode("utf-8"))
                    response = server_ref.handle_request(request)
                    response_body = json.dumps(response).encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(response_body)))
                    self.end_headers()
                    self.wfile.write(response_body)
                except json.JSONDecodeError:
                    error_resp = MCPError.parse_error().to_dict()
                    response_body = json.dumps(error_resp).encode("utf-8")
                    self.send_response(400)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(response_body)))
                    self.end_headers()
                    self.wfile.write(response_body)

            def log_message(self, format: str, *args: Any) -> None:
                pass

        http_server = HTTPServer((host, port), MCPHTTPHandler)
        try:
            http_server.serve_forever()
        except KeyboardInterrupt:
            http_server.shutdown()


def run_mcp_server(transport: str = "stdio", host: str = "127.0.0.1", port: int = 8080) -> None:
    """Run the MCP server with the specified transport."""
    server = AnvilMCPServer()
    if transport == "http":
        server.run_http(host, port)
    else:
        server.run_stdio()


if __name__ == "__main__":
    run_mcp_server()
