"""MCP Protocol Definitions — JSON-RPC 2.0 message types and constants.

Implements the Model Context Protocol specification with support for:
- Tools: Functions the AI can call
- Resources: Data the AI can read
- Prompts: Reusable prompt templates
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from typing import Any

TOOLS_LIST = "tools/list"
TOOLS_CALL = "tools/call"
RESOURCES_LIST = "resources/list"
RESOURCES_READ = "resources/read"
PROMPTS_LIST = "prompts/list"
PROMPTS_GET = "prompts/get"
INITIALIZE = "initialize"
SHUTDOWN = "shutdown"


@dataclass
class MCPMessage:
    """Base MCP message (JSON-RPC 2.0)."""

    jsonrpc: str = "2.0"
    id: int | str | None = None
    method: str = ""
    params: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"jsonrpc": self.jsonrpc}
        if self.id is not None:
            d["id"] = self.id
        if self.method:
            d["method"] = self.method
        if self.params:
            d["params"] = self.params
        return d

    def to_json(self) -> str:
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MCPMessage:
        return cls(
            jsonrpc=data.get("jsonrpc", "2.0"),
            id=data.get("id"),
            method=data.get("method", ""),
            params=data.get("params", {}),
        )

    @classmethod
    def from_json(cls, json_str: str) -> MCPMessage:
        return cls.from_dict(json.loads(json_str))


@dataclass
class MCPRequest(MCPMessage):
    """MCP request — expects a response."""

    def __post_init__(self):
        if self.id is None:
            self.id = str(uuid.uuid4())

    @classmethod
    def create(cls, method: str, params: dict[str, Any] | None = None) -> MCPRequest:
        return cls(method=method, params=params or {})


@dataclass
class MCPResponse:
    """MCP successful response."""

    jsonrpc: str = "2.0"
    id: int | str | None = None
    result: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"jsonrpc": self.jsonrpc, "id": self.id, "result": self.result}
        return d

    def to_json(self) -> str:
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MCPResponse:
        return cls(
            jsonrpc=data.get("jsonrpc", "2.0"),
            id=data.get("id"),
            result=data.get("result", {}),
        )

    @classmethod
    def from_json(cls, json_str: str) -> MCPResponse:
        return cls.from_dict(json.loads(json_str))

    @staticmethod
    def make(result: Any, id: int | str | None = None) -> MCPResponse:
        if isinstance(result, dict):
            return MCPResponse(id=id, result=result)
        return MCPResponse(id=id, result={"value": result})


@dataclass
class MCPError:
    """MCP error response."""

    jsonrpc: str = "2.0"
    id: int | str | None = None
    error: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"jsonrpc": self.jsonrpc, "id": self.id, "error": self.error}
        return d

    def to_json(self) -> str:
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MCPError:
        return cls(
            jsonrpc=data.get("jsonrpc", "2.0"),
            id=data.get("id"),
            error=data.get("error", {}),
        )

    @classmethod
    def from_json(cls, json_str: str) -> MCPError:
        return cls.from_dict(json.loads(json_str))

    @staticmethod
    def make(code: int, message: str, id: int | str | None = None, data: Any = None) -> MCPError:
        err: dict[str, Any] = {"code": code, "message": message}
        if data is not None:
            err["data"] = data
        return MCPError(id=id, error=err)

    @staticmethod
    def method_not_found(method: str, id: int | str | None = None) -> MCPError:
        return MCPError.make(-32601, f"Method not found: {method}", id=id)

    @staticmethod
    def invalid_params(message: str, id: int | str | None = None) -> MCPError:
        return MCPError.make(-32602, f"Invalid params: {message}", id=id)

    @staticmethod
    def internal_error(message: str, id: int | str | None = None) -> MCPError:
        return MCPError.make(-32603, f"Internal error: {message}", id=id)

    @staticmethod
    def parse_error(id: int | str | None = None) -> MCPError:
        return MCPError.make(-32700, "Parse error", id=id)


@dataclass
class ToolDefinition:
    """Definition of an MCP tool."""

    name: str
    description: str = ""
    input_schema: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"name": self.name}
        if self.description:
            d["description"] = self.description
        if self.input_schema:
            d["inputSchema"] = self.input_schema
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ToolDefinition:
        return cls(
            name=data["name"],
            description=data.get("description", ""),
            input_schema=data.get("inputSchema", data.get("input_schema", {})),
        )


@dataclass
class ResourceDefinition:
    """Definition of an MCP resource."""

    uri: str
    name: str = ""
    description: str = ""
    mime_type: str = "text/plain"

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"uri": self.uri}
        if self.name:
            d["name"] = self.name
        if self.description:
            d["description"] = self.description
        if self.mime_type:
            d["mimeType"] = self.mime_type
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ResourceDefinition:
        return cls(
            uri=data["uri"],
            name=data.get("name", ""),
            description=data.get("description", ""),
            mime_type=data.get("mimeType", "text/plain"),
        )


@dataclass
class PromptDefinition:
    """Definition of an MCP prompt template."""

    name: str
    description: str = ""
    arguments: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"name": self.name}
        if self.description:
            d["description"] = self.description
        if self.arguments:
            d["arguments"] = self.arguments
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PromptDefinition:
        return cls(
            name=data["name"],
            description=data.get("description", ""),
            arguments=data.get("arguments", []),
        )


@dataclass
class CallResult:
    """Result from calling an MCP tool."""

    content: list[dict[str, Any]] = field(default_factory=list)
    is_error: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {"content": self.content, "isError": self.is_error}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CallResult:
        return cls(
            content=data.get("content", []),
            is_error=data.get("isError", data.get("is_error", False)),
        )

    @property
    def text(self) -> str:
        return "\n".join(
            item.get("text", "")
            for item in self.content
            if isinstance(item, dict) and item.get("type") == "text"
        )

    @classmethod
    def from_text(cls, text: str, is_error: bool = False) -> CallResult:
        return cls(content=[{"type": "text", "text": text}], is_error=is_error)

    @classmethod
    def from_error(cls, message: str) -> CallResult:
        return cls(content=[{"type": "text", "text": f"Error: {message}"}], is_error=True)
