"""MCP protocol types — JSON-RPC request/response and tool definitions."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class JSONRPCRequest:
    """JSON-RPC 2.0 request for MCP protocol."""
    method: str
    params: dict[str, Any] = field(default_factory=dict)
    id: str | None = None
    jsonrpc: str = "2.0"

    def __post_init__(self):
        if self.id is None:
            self.id = str(uuid.uuid4())

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "jsonrpc": self.jsonrpc,
            "method": self.method,
            "params": self.params,
        }
        if self.id is not None:
            d["id"] = self.id
        return d

    def to_json(self) -> str:
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> JSONRPCRequest:
        return cls(
            method=data["method"],
            params=data.get("params", {}),
            id=data.get("id"),
            jsonrpc=data.get("jsonrpc", "2.0"),
        )

    @classmethod
    def from_json(cls, json_str: str) -> JSONRPCRequest:
        return cls.from_dict(json.loads(json_str))


@dataclass
class JSONRPCResponse:
    """JSON-RPC 2.0 response for MCP protocol."""
    id: str | None = None
    result: Any | None = None
    error: dict[str, Any] | None = None
    jsonrpc: str = "2.0"

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"jsonrpc": self.jsonrpc}
        if self.id is not None:
            d["id"] = self.id
        if self.error is not None:
            d["error"] = self.error
        elif self.result is not None:
            d["result"] = self.result
        return d

    def to_json(self) -> str:
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> JSONRPCResponse:
        return cls(
            id=data.get("id"),
            result=data.get("result"),
            error=data.get("error"),
            jsonrpc=data.get("jsonrpc", "2.0"),
        )

    @classmethod
    def from_json(cls, json_str: str) -> JSONRPCResponse:
        return cls.from_dict(json.loads(json_str))

    @property
    def is_error(self) -> bool:
        return self.error is not None

    @property
    def error_message(self) -> str:
        if self.error:
            return self.error.get("message", "Unknown error")
        return ""

    @property
    def error_code(self) -> int:
        if self.error:
            return self.error.get("code", -1)
        return 0

    @staticmethod
    def make_error(code: int, message: str, id: str | None = None) -> JSONRPCResponse:
        return JSONRPCResponse(
            id=id,
            error={"code": code, "message": message},
        )

    @staticmethod
    def make_result(result: Any, id: str | None = None) -> JSONRPCResponse:
        return JSONRPCResponse(id=id, result=result)


@dataclass
class MCPToolDefinition:
    """Definition of a tool exposed by an MCP server."""
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
    def from_dict(cls, data: dict[str, Any]) -> MCPToolDefinition:
        return cls(
            name=data["name"],
            description=data.get("description", ""),
            input_schema=data.get("inputSchema", data.get("input_schema", {})),
        )


@dataclass
class MCPCallResult:
    """Result from calling an MCP tool."""
    content: list[dict[str, Any]] = field(default_factory=list)
    is_error: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "content": self.content,
            "isError": self.is_error,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MCPCallResult:
        return cls(
            content=data.get("content", []),
            is_error=data.get("isError", data.get("is_error", False)),
        )

    @property
    def text(self) -> str:
        texts = []
        for item in self.content:
            if isinstance(item, dict) and item.get("type") == "text":
                texts.append(item.get("text", ""))
        return "\n".join(texts)

    @classmethod
    def from_text(cls, text: str, is_error: bool = False) -> MCPCallResult:
        return cls(
            content=[{"type": "text", "text": text}],
            is_error=is_error,
        )

    @classmethod
    def from_error(cls, message: str) -> MCPCallResult:
        return cls(
            content=[{"type": "text", "text": f"Error: {message}"}],
            is_error=True,
        )
