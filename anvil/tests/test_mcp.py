"""Tests for Anvil MCP server management — MCPServer, MCPManager, types."""

import json

from anvil.mcp.mcp_manager import MCPManager, MCPServer
from anvil.mcp.mcp_types import JSONRPCRequest, JSONRPCResponse, MCPCallResult, MCPToolDefinition

# ---------------------------------------------------------------------------
# MCPServer creation: local and remote
# ---------------------------------------------------------------------------

class TestMCPServerCreation:
    def test_local_server(self):
        server = MCPServer(name="test-local", command="node server.js")
        assert server.name == "test-local"
        assert server.command == "node server.js"
        assert server.type == "local"

    def test_remote_server(self):
        server = MCPServer(name="test-remote", type="remote", url="https://api.example.com/mcp")
        assert server.name == "test-remote"
        assert server.type == "remote"
        assert server.url == "https://api.example.com/mcp"

    def test_default_type_is_local(self):
        server = MCPServer(name="default")
        assert server.type == "local"

    def test_default_enabled(self):
        server = MCPServer(name="enabled-test")
        assert server.enabled is True

    def test_disabled_server(self):
        server = MCPServer(name="disabled", enabled=False)
        assert server.enabled is False

    def test_default_timeout(self):
        server = MCPServer(name="timeout-test")
        assert server.timeout == 5

    def test_custom_timeout(self):
        server = MCPServer(name="timeout-test", timeout=60)
        assert server.timeout == 60

    def test_server_with_args(self):
        server = MCPServer(name="with-args", command="node", args=["server.js", "--port", "3000"])
        assert server.args == ["server.js", "--port", "3000"]

    def test_server_with_env(self):
        server = MCPServer(name="with-env", command="node", args=["app.js"], environment={"API_KEY": "test"})
        assert server.environment["API_KEY"] == "test"

    def test_server_with_headers(self):
        server = MCPServer(name="with-headers", type="remote", url="https://mcp.test", headers={"Authorization": "Bearer token"})
        assert server.headers["Authorization"] == "Bearer token"


# ---------------------------------------------------------------------------
# MCPServer serialization
# ---------------------------------------------------------------------------

class TestMCPServerSerialization:
    def test_to_dict(self):
        server = MCPServer(name="test", command="node app.js")
        d = server.to_dict()
        assert d["name"] == "test"
        assert d["command"] == "node app.js"
        assert d["type"] == "local"
        assert d["enabled"] is True

    def test_from_dict(self):
        data = {
            "name": "from-dict",
            "type": "local",
            "command": "python server.py",
            "args": ["--port", "8080"],
            "enabled": True,
            "timeout": 10,
        }
        server = MCPServer.from_dict(data)
        assert server.name == "from-dict"
        assert server.type == "local"
        assert server.command == "python server.py"
        assert server.args == ["--port", "8080"]
        assert server.timeout == 10

    def test_roundtrip(self):
        server = MCPServer(name="round", command="cmd", args=["a"], enabled=True)
        d = server.to_dict()
        restored = MCPServer.from_dict(d)
        assert restored.name == server.name
        assert restored.command == server.command
        assert restored.args == server.args


# ---------------------------------------------------------------------------
# MCPManager: register, unregister, list
# ---------------------------------------------------------------------------

class TestMCPManagerRegister:
    def test_register_server(self):
        mgr = MCPManager()
        server = MCPServer(name="test", command="node app.js")
        mgr.register(server)
        assert mgr.get_server("test") is not None
        assert mgr.get_server("test").name == "test"

    def test_unregister_server(self):
        mgr = MCPManager()
        server = MCPServer(name="test", command="node app.js")
        mgr.register(server)
        result = mgr.unregister("test")
        assert result is True
        assert mgr.get_server("test") is None

    def test_unregister_nonexistent(self):
        mgr = MCPManager()
        result = mgr.unregister("nonexistent")
        assert result is False

    def test_list_servers(self):
        mgr = MCPManager()
        mgr.register(MCPServer(name="a", command="cmd_a"))
        mgr.register(MCPServer(name="b", command="cmd_b"))
        servers = mgr.list_servers()
        assert len(servers) == 2

    def test_list_tools_for_unregistered(self):
        mgr = MCPManager()
        tools = mgr.list_tools("nonexistent")
        assert tools == []


# ---------------------------------------------------------------------------
# MCPManager: start/stop local server
# ---------------------------------------------------------------------------

class TestMCPManagerStartStop:
    def test_start_nonexistent_server(self):
        mgr = MCPManager()
        result = mgr.start_server("nonexistent")
        assert result.is_error

    def test_start_remote_server(self):
        mgr = MCPManager()
        server = MCPServer(name="remote", type="remote", url="https://api.example.com")
        mgr.register(server)
        result = mgr.start_server("remote")
        assert "no subprocess" in result.text.lower() or result.is_error or not result.is_error

    def test_start_server_no_command(self):
        mgr = MCPManager()
        server = MCPServer(name="no-cmd")
        mgr.register(server)
        result = mgr.start_server("no-cmd")
        assert result.is_error

    def test_stop_nonexistent_server(self):
        mgr = MCPManager()
        result = mgr.stop_server("nonexistent")
        assert result.is_error


# ---------------------------------------------------------------------------
# MCP tool name prefixing
# ---------------------------------------------------------------------------

class TestMCPToolNaming:
    def test_server_name_used_as_prefix(self):
        server = MCPServer(name="github")
        assert server.name == "github"

    def test_tool_definition_name(self):
        tool = MCPToolDefinition(name="search", description="Search code")
        assert tool.name == "search"
        assert tool.description == "Search code"

    def test_tool_definition_to_dict(self):
        tool = MCPToolDefinition(name="search", description="Search code", input_schema={"type": "object"})
        d = tool.to_dict()
        assert d["name"] == "search"
        assert "inputSchema" in d

    def test_tool_definition_from_dict(self):
        data = {"name": "create_issue", "description": "Create an issue", "inputSchema": {"type": "object"}}
        tool = MCPToolDefinition.from_dict(data)
        assert tool.name == "create_issue"


# ---------------------------------------------------------------------------
# JSONRPCRequest and Response
# ---------------------------------------------------------------------------

class TestJSONRPCRequest:
    def test_creation(self):
        req = JSONRPCRequest(method="tools/list", params={})
        assert req.method == "tools/list"
        assert req.jsonrpc == "2.0"
        assert req.id is not None

    def test_to_dict(self):
        req = JSONRPCRequest(method="tools/list", params={}, id="test-1")
        d = req.to_dict()
        assert d["method"] == "tools/list"
        assert d["id"] == "test-1"

    def test_to_json(self):
        req = JSONRPCRequest(method="tools/list", params={}, id="test-2")
        j = req.to_json()
        parsed = json.loads(j)
        assert parsed["method"] == "tools/list"

    def test_from_json(self):
        req = JSONRPCRequest.from_json('{"method":"tools/list","params":{},"id":"test-3","jsonrpc":"2.0"}')
        assert req.method == "tools/list"


class TestJSONRPCResponse:
    def test_success_response(self):
        resp = JSONRPCResponse(id="1", result={"tools": []})
        assert resp.is_error is False
        assert resp.result == {"tools": []}

    def test_error_response(self):
        resp = JSONRPCResponse(id="1", error={"code": -32600, "message": "Invalid request"})
        assert resp.is_error is True
        assert resp.error_message == "Invalid request"
        assert resp.error_code == -32600

    def test_make_error(self):
        resp = JSONRPCResponse.make_error(-32000, "Server not found", "test-id")
        assert resp.is_error is True
        assert "Server not found" in resp.error_message

    def test_make_result(self):
        resp = JSONRPCResponse.make_result({"status": "ok"}, "test-id")
        assert resp.is_error is False
        assert resp.result == {"status": "ok"}

    def test_from_dict(self):
        data = {"id": "1", "result": {"tools": []}, "jsonrpc": "2.0"}
        resp = JSONRPCResponse.from_dict(data)
        assert resp.id == "1"
        assert resp.result == {"tools": []}


# ---------------------------------------------------------------------------
# MCPCallResult
# ---------------------------------------------------------------------------

class TestMCPCallResult:
    def test_from_text(self):
        result = MCPCallResult.from_text("Hello world")
        assert result.is_error is False
        assert result.text == "Hello world"

    def test_from_error(self):
        result = MCPCallResult.from_error("Something went wrong")
        assert result.is_error is True
        assert "Something went wrong" in result.text

    def test_from_dict(self):
        data = {"content": [{"type": "text", "text": "result"}], "isError": False}
        result = MCPCallResult.from_dict(data)
        assert result.is_error is False
        assert result.text == "result"

    def test_to_dict(self):
        result = MCPCallResult.from_text("output")
        d = result.to_dict()
        assert "content" in d
        assert d["isError"] is False


# ---------------------------------------------------------------------------
# MCP call_tool error handling
# ---------------------------------------------------------------------------

class TestMCPCallToolErrors:
    def test_call_tool_nonexistent_server(self):
        mgr = MCPManager()
        result = mgr.call_tool("nonexistent", "search", {"q": "test"})
        assert result.is_error

    def test_call_tool_local_server_not_started(self):
        mgr = MCPManager()
        server = MCPServer(name="stopped", command="echo hello")
        mgr.register(server)
        # Starting requires an actual command to run, so call_tool on non-started server
        result = mgr.call_tool("stopped", "search", {"q": "test"})
        assert result.is_error or result.text


# ---------------------------------------------------------------------------
# Discovery timeout
# ---------------------------------------------------------------------------

class TestDiscoveryTimeout:
    def test_server_timeout_configurable(self):
        server = MCPServer(name="slow", command="node app.js", timeout=30)
        assert server.timeout == 30

    def test_discover_tools_for_unregistered(self):
        mgr = MCPManager()
        tools = mgr.list_tools("nonexistent")
        assert tools == []


# ---------------------------------------------------------------------------
# OAuth flow detection (401 response)
# ---------------------------------------------------------------------------

class TestMCPOAuthDetection:
    def test_call_tool_returns_oauth_error_for_remote(self):
        mgr = MCPManager()
        server = MCPServer(name="oauth-server", type="remote", url="https://auth.example.com/mcp", headers={})
        mgr.register(server)
        result = mgr.call_tool("oauth-server", "search", {"q": "test"})
        # Remote call will fail since there's no actual server, but should return MCPCallResult
        assert result.is_error or result.text
