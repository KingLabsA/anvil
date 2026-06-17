"""LSP client for code intelligence."""

from __future__ import annotations

import subprocess
import json
import logging
from pathlib import Path
from typing import Optional, Any

logger = logging.getLogger(__name__)


class LSPClient:
    """Client for Language Server Protocol."""
    
    def __init__(self, language: str, workspace_root: Path):
        self.language = language
        self.workspace_root = workspace_root
        self.process: Optional[subprocess.Popen] = None
        self.request_id = 0
        self.capabilities = {}
    
    def start(self):
        """Start LSP server for language."""
        servers = {
            'python': ['pylsp', '--stdio'],
            'typescript': ['typescript-language-server', '--stdio'],
            'javascript': ['typescript-language-server', '--stdio'],
            'rust': ['rust-analyzer'],
            'go': ['gopls'],
            'java': ['jdtls'],
            'c': ['clangd'],
            'cpp': ['clangd'],
        }
        
        if self.language not in servers:
            raise ValueError(f"No LSP server configured for {self.language}")
        
        try:
            self.process = subprocess.Popen(
                servers[self.language],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            self._initialize()
        except FileNotFoundError as e:
            raise RuntimeError(f"LSP server not found for {self.language}: {e}")
        except Exception as e:
            raise RuntimeError(f"Failed to start LSP server: {e}")
    
    def _initialize(self):
        """Send initialize request."""
        params = {
            "processId": None,
            "rootUri": f"file://{self.workspace_root}",
            "capabilities": {
                "textDocument": {
                    "completion": {"completionItem": {"snippetSupport": True}},
                    "hover": {},
                    "definition": {},
                    "references": {},
                    "documentSymbol": {},
                    "codeAction": {},
                }
            }
        }
        
        response = self._send_request("initialize", params)
        self.capabilities = response.get("capabilities", {})
    
    def _send_request(self, method: str, params: dict) -> dict:
        """Send JSON-RPC request to LSP server."""
        if not self.process or not self.process.stdin or not self.process.stdout:
            raise RuntimeError("LSP server not running")
        
        self.request_id += 1
        
        message = {
            "jsonrpc": "2.0",
            "id": self.request_id,
            "method": method,
            "params": params,
        }
        
        try:
            content = json.dumps(message)
            header = f"Content-Length: {len(content)}\r\n\r\n"
            self.process.stdin.write(header.encode() + content.encode())
            self.process.stdin.flush()
            
            return self._read_response()
        except Exception as e:
            logger.error(f"LSP request failed: {e}")
            return {}
    
    def _read_response(self) -> dict:
        """Read and parse LSP response."""
        if not self.process or not self.process.stdout:
            return {}
        
        try:
            headers = {}
            while True:
                line = self.process.stdout.readline().decode('utf-8')
                if line == '\r\n':
                    break
                if ':' in line:
                    key, value = line.split(':', 1)
                    headers[key.strip()] = value.strip()
            
            content_length = int(headers.get('Content-Length', 0))
            if content_length == 0:
                return {}
            
            content = self.process.stdout.read(content_length).decode('utf-8')
            response = json.loads(content)
            
            return response.get('result', {})
        except Exception as e:
            logger.error(f"Failed to read LSP response: {e}")
            return {}
    
    def get_completions(self, file_path: str, line: int, column: int) -> list[dict]:
        """Get code completions."""
        params = {
            "textDocument": {"uri": f"file://{file_path}"},
            "position": {"line": line, "character": column}
        }
        response = self._send_request("textDocument/completion", params)
        return response.get("items", [])
    
    def get_definition(self, file_path: str, line: int, column: int) -> Optional[dict]:
        """Get definition location."""
        params = {
            "textDocument": {"uri": f"file://{file_path}"},
            "position": {"line": line, "character": column}
        }
        return self._send_request("textDocument/definition", params)
    
    def get_references(self, file_path: str, line: int, column: int) -> list[dict]:
        """Get all references."""
        params = {
            "textDocument": {"uri": f"file://{file_path}"},
            "position": {"line": line, "character": column},
            "context": {"includeDeclaration": True}
        }
        return self._send_request("textDocument/references", params)
    
    def get_hover(self, file_path: str, line: int, column: int) -> Optional[str]:
        """Get hover information."""
        params = {
            "textDocument": {"uri": f"file://{file_path}"},
            "position": {"line": line, "character": column}
        }
        response = self._send_request("textDocument/hover", params)
        return response.get("contents")
    
    def get_symbols(self, file_path: str) -> list[dict]:
        """Get document symbols."""
        params = {
            "textDocument": {"uri": f"file://{file_path}"}
        }
        return self._send_request("textDocument/documentSymbol", params)
    
    def get_code_actions(self, file_path: str, range: dict, context: dict) -> list[dict]:
        """Get code actions."""
        params = {
            "textDocument": {"uri": f"file://{file_path}"},
            "range": range,
            "context": context
        }
        return self._send_request("textDocument/codeAction", params)
    
    def shutdown(self):
        """Shutdown LSP server."""
        if self.process:
            try:
                self._send_request("shutdown", {})
                self.process.terminate()
                self.process.wait(timeout=5)
            except Exception as e:
                logger.warning(f"Error shutting down LSP server: {e}")
            finally:
                if self.process.poll() is None:
                    self.process.kill()
                self.process = None
