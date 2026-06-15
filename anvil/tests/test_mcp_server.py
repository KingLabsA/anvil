"""Tests for MCP server."""

import pytest
from unittest.mock import Mock, patch
from anvil.mcp.server import AnvilMCPServer


@pytest.fixture
def mcp_server():
    """Create an MCP server instance with mocked engine."""
    with patch('anvil.mcp.server.AnvilEngine') as MockEngine:
        mock_engine = Mock()
        MockEngine.return_value = mock_engine
        server = AnvilMCPServer()
        server.engine = mock_engine
        yield server


class TestMCPServer:
    """Test MCP server functionality."""
    
    def test_initialize(self, mcp_server):
        """Test initialize request."""
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {},
        }
        response = mcp_server.handle_request(request)
        
        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 1
        assert "result" in response
        assert response["result"]["protocolVersion"] == "2024-11-05"
        assert response["result"]["serverInfo"]["name"] == "anvil"
    
    def test_tools_list(self, mcp_server):
        """Test tools/list request."""
        request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {},
        }
        response = mcp_server.handle_request(request)
        
        assert "result" in response
        assert "tools" in response["result"]
        assert len(response["result"]["tools"]) > 0
        
        tool_names = [t["name"] for t in response["result"]["tools"]]
        assert "run_task" in tool_names
        assert "verify_code" in tool_names
        assert "recall_memory" in tool_names
        assert "add_memory" in tool_names
    
    def test_tools_call_run_task(self, mcp_server):
        """Test tools/call with run_task."""
        # Mock the engine run result
        mock_result = Mock()
        mock_result.success = True
        mock_result.output = "Task completed"
        mock_result.error = None
        mcp_server.engine.run.return_value = mock_result
        
        request = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "run_task",
                "arguments": {
                    "task": "Create a simple Python file",
                },
            },
        }
        response = mcp_server.handle_request(request)
        
        assert "result" in response
        assert "content" in response["result"]
        assert len(response["result"]["content"]) > 0
    
    def test_tools_call_recall_memory(self, mcp_server):
        """Test tools/call with recall_memory."""
        # First add a memory
        add_request = {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {
                "name": "add_memory",
                "arguments": {
                    "category": "fact",
                    "content": "Test memory for MCP",
                },
            },
        }
        mcp_server.handle_request(add_request)
        
        # Then recall it
        request = {
            "jsonrpc": "2.0",
            "id": 5,
            "method": "tools/call",
            "params": {
                "name": "recall_memory",
                "arguments": {
                    "query": "MCP",
                },
            },
        }
        response = mcp_server.handle_request(request)
        
        assert "result" in response
        assert "content" in response["result"]
    
    def test_resources_list(self, mcp_server):
        """Test resources/list request."""
        request = {
            "jsonrpc": "2.0",
            "id": 6,
            "method": "resources/list",
            "params": {},
        }
        response = mcp_server.handle_request(request)
        
        assert "result" in response
        assert "resources" in response["result"]
        assert len(response["result"]["resources"]) > 0
        
        resource_uris = [r["uri"] for r in response["result"]["resources"]]
        assert "anvil://config" in resource_uris
        assert "anvil://memories" in resource_uris
    
    def test_resources_read_config(self, mcp_server):
        """Test resources/read for config."""
        request = {
            "jsonrpc": "2.0",
            "id": 7,
            "method": "resources/read",
            "params": {
                "uri": "anvil://config",
            },
        }
        response = mcp_server.handle_request(request)
        
        assert "result" in response
        assert "contents" in response["result"]
        assert len(response["result"]["contents"]) > 0
        assert response["result"]["contents"][0]["uri"] == "anvil://config"
    
    def test_prompts_list(self, mcp_server):
        """Test prompts/list request."""
        request = {
            "jsonrpc": "2.0",
            "id": 8,
            "method": "prompts/list",
            "params": {},
        }
        response = mcp_server.handle_request(request)
        
        assert "result" in response
        assert "prompts" in response["result"]
        assert len(response["result"]["prompts"]) > 0
        
        prompt_names = [p["name"] for p in response["result"]["prompts"]]
        assert "coding_task" in prompt_names
        assert "code_review" in prompt_names
    
    def test_prompts_get(self, mcp_server):
        """Test prompts/get request."""
        request = {
            "jsonrpc": "2.0",
            "id": 9,
            "method": "prompts/get",
            "params": {
                "name": "coding_task",
                "arguments": {
                    "task": "Fix the bug",
                },
            },
        }
        response = mcp_server.handle_request(request)
        
        assert "result" in response
        assert "messages" in response["result"]
        assert len(response["result"]["messages"]) > 0
    
    def test_unknown_method(self, mcp_server):
        """Test unknown method returns error."""
        request = {
            "jsonrpc": "2.0",
            "id": 10,
            "method": "unknown/method",
            "params": {},
        }
        response = mcp_server.handle_request(request)
        
        assert "error" in response
        assert response["error"]["code"] == -32601
        assert "Method not found" in response["error"]["message"]
    
    def test_unknown_tool(self, mcp_server):
        """Test unknown tool returns error."""
        request = {
            "jsonrpc": "2.0",
            "id": 11,
            "method": "tools/call",
            "params": {
                "name": "unknown_tool",
                "arguments": {},
            },
        }
        response = mcp_server.handle_request(request)
        
        assert "error" in response
        assert "Unknown tool" in response["error"]["message"]
