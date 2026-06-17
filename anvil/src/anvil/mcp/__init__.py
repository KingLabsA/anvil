"""MCP (Model Context Protocol) implementation for Anvil.

Provides protocol definitions, server, client, built-in tools,
and a unified tool registry for integrating external MCP servers.
"""

from anvil.mcp.protocol import (
    MCPMessage,
    MCPRequest,
    MCPResponse,
    MCPError,
    ToolDefinition,
    ResourceDefinition,
    PromptDefinition,
    CallResult,
    TOOLS_LIST,
    TOOLS_CALL,
    RESOURCES_LIST,
    RESOURCES_READ,
    PROMPTS_LIST,
    PROMPTS_GET,
    INITIALIZE,
    SHUTDOWN,
)
from anvil.mcp.server import AnvilMCPServer, run_mcp_server
from anvil.mcp.client import MCPClient
from anvil.mcp.registry import MCPToolRegistry
from anvil.mcp.tools import (
    get_builtin_tool_definitions,
    get_builtin_tool_handler,
    query_database,
    read_file,
    write_file,
    http_request,
    git_status,
    git_diff,
    send_slack_message,
    create_github_issue,
    create_github_pr,
)

__all__ = [
    "MCPMessage",
    "MCPRequest",
    "MCPResponse",
    "MCPError",
    "ToolDefinition",
    "ResourceDefinition",
    "PromptDefinition",
    "CallResult",
    "TOOLS_LIST",
    "TOOLS_CALL",
    "RESOURCES_LIST",
    "RESOURCES_READ",
    "PROMPTS_LIST",
    "PROMPTS_GET",
    "INITIALIZE",
    "SHUTDOWN",
    "AnvilMCPServer",
    "run_mcp_server",
    "MCPClient",
    "MCPToolRegistry",
    "get_builtin_tool_definitions",
    "get_builtin_tool_handler",
    "query_database",
    "read_file",
    "write_file",
    "http_request",
    "git_status",
    "git_diff",
    "send_slack_message",
    "create_github_issue",
    "create_github_pr",
]
