"""MCP (Model Context Protocol) server for Anvil.

This module implements an MCP server that exposes Anvil's capabilities
to other AI agents and tools via the Model Context Protocol.
"""

from __future__ import annotations

import json
import sys
from typing import Any
from pathlib import Path

from anvil.core.engine import AnvilEngine
from anvil.core.config import AnvilConfig
from anvil.memory.manager import MemoryManager


class AnvilMCPServer:
    """MCP server that exposes Anvil's capabilities."""
    
    def __init__(self, config: AnvilConfig | None = None):
        """Initialize the MCP server.
        
        Args:
            config: Anvil configuration (optional)
        """
        self.config = config or AnvilConfig()
        self.engine = AnvilEngine(self.config)
        self.memory = MemoryManager()
    
    def handle_request(self, request: dict[str, Any]) -> dict[str, Any]:
        """Handle an MCP request.
        
        Args:
            request: MCP request object
            
        Returns:
            MCP response object
        """
        method = request.get("method", "")
        params = request.get("params", {})
        
        # Route to appropriate handler
        handlers = {
            "initialize": self._handle_initialize,
            "tools/list": self._handle_tools_list,
            "tools/call": self._handle_tools_call,
            "resources/list": self._handle_resources_list,
            "resources/read": self._handle_resources_read,
            "prompts/list": self._handle_prompts_list,
            "prompts/get": self._handle_prompts_get,
        }
        
        handler = handlers.get(method)
        if handler:
            try:
                result = handler(params)
                return {
                    "jsonrpc": "2.0",
                    "id": request.get("id"),
                    "result": result,
                }
            except Exception as e:
                return {
                    "jsonrpc": "2.0",
                    "id": request.get("id"),
                    "error": {
                        "code": -32000,
                        "message": str(e),
                    },
                }
        else:
            return {
                "jsonrpc": "2.0",
                "id": request.get("id"),
                "error": {
                    "code": -32601,
                    "message": f"Method not found: {method}",
                },
            }
    
    def _handle_initialize(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle initialize request."""
        return {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "tools": {},
                "resources": {},
                "prompts": {},
            },
            "serverInfo": {
                "name": "anvil",
                "version": "0.3.0",
            },
        }
    
    def _handle_tools_list(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle tools/list request."""
        return {
            "tools": [
                {
                    "name": "run_task",
                    "description": "Execute a coding task with self-verification",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "task": {
                                "type": "string",
                                "description": "Task description",
                            },
                            "model": {
                                "type": "string",
                                "description": "Model to use (optional)",
                            },
                            "max_iterations": {
                                "type": "integer",
                                "description": "Maximum iterations (optional)",
                            },
                        },
                        "required": ["task"],
                    },
                },
                {
                    "name": "verify_code",
                    "description": "Verify code without making changes",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "path": {
                                "type": "string",
                                "description": "Path to verify",
                            },
                            "checks": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Checks to run (syntax, lint, types, tests)",
                            },
                        },
                        "required": ["path"],
                    },
                },
                {
                    "name": "recall_memory",
                    "description": "Recall relevant memories for a query",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Query to recall memories for",
                            },
                            "limit": {
                                "type": "integer",
                                "description": "Maximum memories to return",
                            },
                        },
                        "required": ["query"],
                    },
                },
                {
                    "name": "add_memory",
                    "description": "Add a new memory",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "category": {
                                "type": "string",
                                "enum": ["preference", "project", "pattern", "mistake", "fact"],
                                "description": "Memory category",
                            },
                            "content": {
                                "type": "string",
                                "description": "Memory content",
                            },
                            "context": {
                                "type": "string",
                                "description": "Context (optional)",
                            },
                            "importance": {
                                "type": "number",
                                "description": "Importance 0.0-1.0 (optional)",
                            },
                        },
                        "required": ["category", "content"],
                    },
                },
            ]
        }
    
    def _handle_tools_call(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle tools/call request."""
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})
        
        if tool_name == "run_task":
            return self._call_run_task(arguments)
        elif tool_name == "verify_code":
            return self._call_verify_code(arguments)
        elif tool_name == "recall_memory":
            return self._call_recall_memory(arguments)
        elif tool_name == "add_memory":
            return self._call_add_memory(arguments)
        else:
            raise ValueError(f"Unknown tool: {tool_name}")
    
    def _call_run_task(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Call run_task tool."""
        task = arguments.get("task", "")
        model = arguments.get("model")
        max_iterations = arguments.get("max_iterations", 20)
        
        # Update config if model specified
        if model:
            self.config.model.model = model
        
        # Create engine with updated config
        engine = AnvilEngine(self.config)
        result = engine.run(task, max_iterations=max_iterations)
        
        return {
            "content": [
                {
                    "type": "text",
                    "text": result.output or result.error or "Task completed",
                }
            ],
            "isError": not result.success,
        }
    
    def _call_verify_code(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Call verify_code tool."""
        from anvil.verify.pipeline import VerifyPipeline
        
        path = arguments.get("path", "")
        checks = arguments.get("checks", [])
        
        pipeline = VerifyPipeline(self.config.verify)
        report = pipeline.verify([path], checks=checks if checks else None)
        
        return {
            "content": [
                {
                    "type": "text",
                    "text": report.format_summary(),
                }
            ],
            "isError": not report.passed,
        }
    
    def _call_recall_memory(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Call recall_memory tool."""
        query = arguments.get("query", "")
        limit = arguments.get("limit", 5)
        
        memories = self.memory.recall(query, limit=limit)
        
        if not memories:
            return {
                "content": [
                    {
                        "type": "text",
                        "text": "No memories found",
                    }
                ],
            }
        
        text = "\n\n".join([
            f"[{mem.category.value}] {mem.content}"
            for mem in memories
        ])
        
        return {
            "content": [
                {
                    "type": "text",
                    "text": text,
                }
            ],
        }
    
    def _call_add_memory(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Call add_memory tool."""
        from anvil.memory.manager import MemoryCategory
        
        category = arguments.get("category", "fact")
        content = arguments.get("content", "")
        context = arguments.get("context", "")
        importance = arguments.get("importance", 0.5)
        
        mem = self.memory.add(
            category=MemoryCategory(category),
            content=content,
            context=context,
            importance=importance,
        )
        
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Memory added: {mem.id}",
                }
            ],
        }
    
    def _handle_resources_list(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle resources/list request."""
        return {
            "resources": [
                {
                    "uri": "anvil://config",
                    "name": "Anvil Configuration",
                    "description": "Current Anvil configuration",
                    "mimeType": "application/json",
                },
                {
                    "uri": "anvil://memories",
                    "name": "Agent Memories",
                    "description": "All stored memories",
                    "mimeType": "application/json",
                },
            ]
        }
    
    def _handle_resources_read(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle resources/read request."""
        uri = params.get("uri", "")
        
        if uri == "anvil://config":
            return {
                "contents": [
                    {
                        "uri": uri,
                        "mimeType": "application/json",
                        "text": json.dumps(self.config.to_dict(), indent=2),
                    }
                ]
            }
        elif uri == "anvil://memories":
            memories = self.memory.list()
            return {
                "contents": [
                    {
                        "uri": uri,
                        "mimeType": "application/json",
                        "text": json.dumps([m.to_dict() for m in memories], indent=2),
                    }
                ]
            }
        else:
            raise ValueError(f"Unknown resource: {uri}")
    
    def _handle_prompts_list(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle prompts/list request."""
        return {
            "prompts": [
                {
                    "name": "coding_task",
                    "description": "Execute a coding task with verification",
                    "arguments": [
                        {
                            "name": "task",
                            "description": "Task description",
                            "required": True,
                        }
                    ],
                },
                {
                    "name": "code_review",
                    "description": "Review code for issues",
                    "arguments": [
                        {
                            "name": "path",
                            "description": "Path to review",
                            "required": True,
                        }
                    ],
                },
            ]
        }
    
    def _handle_prompts_get(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle prompts/get request."""
        name = params.get("name", "")
        arguments = params.get("arguments", {})
        
        if name == "coding_task":
            task = arguments.get("task", "")
            return {
                "messages": [
                    {
                        "role": "user",
                        "content": {
                            "type": "text",
                            "text": f"Execute this coding task with self-verification: {task}",
                        },
                    }
                ]
            }
        elif name == "code_review":
            path = arguments.get("path", "")
            return {
                "messages": [
                    {
                        "role": "user",
                        "content": {
                            "type": "text",
                            "text": f"Review this code for issues: {path}",
                        },
                    }
                ]
            }
        else:
            raise ValueError(f"Unknown prompt: {name}")


def run_mcp_server():
    """Run the MCP server on stdin/stdout."""
    server = AnvilMCPServer()
    
    # Read requests from stdin
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        
        try:
            request = json.loads(line)
            response = server.handle_request(request)
            print(json.dumps(response), flush=True)
        except json.JSONDecodeError:
            error_response = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {
                    "code": -32700,
                    "message": "Parse error",
                },
            }
            print(json.dumps(error_response), flush=True)


if __name__ == "__main__":
    run_mcp_server()
