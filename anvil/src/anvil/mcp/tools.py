"""Built-in MCP Tools — ready-to-use tools for common operations.

Provides database, filesystem, HTTP, git, Slack, and GitHub tools
that can be registered with an MCP server or tool registry.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

from anvil.mcp.protocol import CallResult, ToolDefinition


def _tool_def(name: str, description: str, schema: dict[str, Any]) -> ToolDefinition:
    return ToolDefinition(name=name, description=description, input_schema=schema)


DATABASE_QUERY_SCHEMA = {
    "type": "object",
    "properties": {
        "sql": {"type": "string", "description": "SQL query to execute"},
        "db_url": {"type": "string", "description": "Database connection URL"},
    },
    "required": ["sql", "db_url"],
}

READ_FILE_SCHEMA = {
    "type": "object",
    "properties": {
        "path": {"type": "string", "description": "File path to read"},
    },
    "required": ["path"],
}

WRITE_FILE_SCHEMA = {
    "type": "object",
    "properties": {
        "path": {"type": "string", "description": "File path to write"},
        "content": {"type": "string", "description": "Content to write"},
    },
    "required": ["path", "content"],
}

HTTP_REQUEST_SCHEMA = {
    "type": "object",
    "properties": {
        "url": {"type": "string", "description": "Request URL"},
        "method": {"type": "string", "description": "HTTP method", "default": "GET"},
        "headers": {"type": "object", "description": "Request headers"},
        "body": {"type": "object", "description": "Request body (JSON)"},
    },
    "required": ["url"],
}

GIT_STATUS_SCHEMA = {
    "type": "object",
    "properties": {
        "repo_path": {"type": "string", "description": "Repository path"},
    },
    "required": ["repo_path"],
}

GIT_DIFF_SCHEMA = {
    "type": "object",
    "properties": {
        "repo_path": {"type": "string", "description": "Repository path"},
    },
    "required": ["repo_path"],
}

SLACK_MESSAGE_SCHEMA = {
    "type": "object",
    "properties": {
        "channel": {"type": "string", "description": "Slack channel name or ID"},
        "message": {"type": "string", "description": "Message text"},
        "webhook_url": {"type": "string", "description": "Slack webhook URL"},
    },
    "required": ["channel", "message", "webhook_url"],
}

GITHUB_ISSUE_SCHEMA = {
    "type": "object",
    "properties": {
        "repo": {"type": "string", "description": "Repository (owner/name)"},
        "title": {"type": "string", "description": "Issue title"},
        "body": {"type": "string", "description": "Issue body"},
        "token": {"type": "string", "description": "GitHub token"},
    },
    "required": ["repo", "title", "body", "token"],
}

GITHUB_PR_SCHEMA = {
    "type": "object",
    "properties": {
        "repo": {"type": "string", "description": "Repository (owner/name)"},
        "title": {"type": "string", "description": "PR title"},
        "body": {"type": "string", "description": "PR body"},
        "head": {"type": "string", "description": "Head branch"},
        "base": {"type": "string", "description": "Base branch"},
        "token": {"type": "string", "description": "GitHub token"},
    },
    "required": ["repo", "title", "body", "head", "base", "token"],
}


def query_database(sql: str, db_url: str) -> CallResult:
    """Execute a SQL query against a database."""
    try:
        if db_url.startswith(("postgres://", "postgresql://")):
            try:
                import psycopg2
                conn = psycopg2.connect(db_url)
                cur = conn.cursor()
                cur.execute(sql)
                if cur.description:
                    columns = [desc[0] for desc in cur.description]
                    rows = cur.fetchall()
                    result = {"columns": columns, "rows": [list(r) for r in rows], "row_count": len(rows)}
                else:
                    conn.commit()
                    result = {"affected_rows": cur.rowcount}
                cur.close()
                conn.close()
                return CallResult.from_text(json.dumps(result, indent=2, default=str))
            except ImportError:
                return CallResult.from_error("psycopg2 not installed — run: pip install psycopg2-binary")
        elif db_url.startswith(("mysql://", "mariadb://")):
            try:
                import pymysql
                conn = pymysql.connect(host=db_url)
                cur = conn.cursor()
                cur.execute(sql)
                if cur.description:
                    columns = [desc[0] for desc in cur.description]
                    rows = cur.fetchall()
                    result = {"columns": columns, "rows": [list(r) for r in rows], "row_count": len(rows)}
                else:
                    conn.commit()
                    result = {"affected_rows": cur.rowcount}
                cur.close()
                conn.close()
                return CallResult.from_text(json.dumps(result, indent=2, default=str))
            except ImportError:
                return CallResult.from_error("pymysql not installed — run: pip install pymysql")
        elif db_url.startswith("sqlite"):
            import sqlite3
            db_path = db_url.replace("sqlite:///", "").replace("sqlite:", "")
            conn = sqlite3.connect(db_path)
            cur = conn.cursor()
            cur.execute(sql)
            if cur.description:
                columns = [desc[0] for desc in cur.description]
                rows = cur.fetchall()
                result = {"columns": columns, "rows": [list(r) for r in rows], "row_count": len(rows)}
            else:
                conn.commit()
                result = {"affected_rows": cur.rowcount}
            cur.close()
            conn.close()
            return CallResult.from_text(json.dumps(result, indent=2, default=str))
        else:
            return CallResult.from_error(f"Unsupported database URL scheme: {db_url}")
    except Exception as e:
        return CallResult.from_error(f"Database query failed: {e}")


def read_file(path: str) -> CallResult:
    """Read file contents."""
    try:
        p = Path(path).expanduser()
        if not p.exists():
            return CallResult.from_error(f"File not found: {path}")
        if not p.is_file():
            return CallResult.from_error(f"Not a file: {path}")
        content = p.read_text(encoding="utf-8", errors="replace")
        return CallResult.from_text(content)
    except Exception as e:
        return CallResult.from_error(f"Failed to read file: {e}")


def write_file(path: str, content: str) -> CallResult:
    """Write content to a file."""
    try:
        p = Path(path).expanduser()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return CallResult.from_text(f"Written {len(content)} bytes to {path}")
    except Exception as e:
        return CallResult.from_error(f"Failed to write file: {e}")


def http_request(
    url: str,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    body: dict[str, Any] | None = None,
) -> CallResult:
    """Make an HTTP request."""
    try:
        import urllib.request
        import urllib.error

        req_headers = headers or {}
        data = None
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            req_headers.setdefault("Content-Type", "application/json")

        req = urllib.request.Request(url, data=data, headers=req_headers, method=method.upper())
        with urllib.request.urlopen(req, timeout=30) as resp:
            resp_body = resp.read().decode("utf-8", errors="replace")
            resp_headers = dict(resp.headers)
            result = {
                "status": resp.status,
                "headers": resp_headers,
                "body": resp_body,
            }
            return CallResult.from_text(json.dumps(result, indent=2))
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8", errors="replace") if e.fp else ""
        result = {"status": e.code, "body": error_body}
        return CallResult.from_text(json.dumps(result, indent=2))
    except Exception as e:
        return CallResult.from_error(f"HTTP request failed: {e}")


def git_status(repo_path: str) -> CallResult:
    """Get git status for a repository."""
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return CallResult.from_error(f"git status failed: {result.stderr}")

        files: dict[str, list[str]] = {"modified": [], "added": [], "deleted": [], "untracked": []}
        for line in result.stdout.strip().split("\n"):
            if not line:
                continue
            status = line[:2]
            filepath = line[3:]
            if status == "??":
                files["untracked"].append(filepath)
            elif status[0] in ("M", "R", "C"):
                files["modified"].append(filepath)
            elif status[0] == "A":
                files["added"].append(filepath)
            elif status[0] == "D":
                files["deleted"].append(filepath)
            else:
                files["modified"].append(filepath)

        return CallResult.from_text(json.dumps(files, indent=2))
    except Exception as e:
        return CallResult.from_error(f"git status failed: {e}")


def git_diff(repo_path: str) -> CallResult:
    """Get git diff for a repository."""
    try:
        result = subprocess.run(
            ["git", "diff"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return CallResult.from_error(f"git diff failed: {result.stderr}")
        return CallResult.from_text(result.stdout or "(no changes)")
    except Exception as e:
        return CallResult.from_error(f"git diff failed: {e}")


def send_slack_message(channel: str, message: str, webhook_url: str) -> CallResult:
    """Send a message to Slack via webhook."""
    try:
        payload = json.dumps({"channel": channel, "text": message}).encode("utf-8")
        req = urllib.request.Request(
            webhook_url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return CallResult.from_text(f"Message sent to {channel} (status: {resp.status})")
    except Exception as e:
        return CallResult.from_error(f"Failed to send Slack message: {e}")


def create_github_issue(repo: str, title: str, body: str, token: str) -> CallResult:
    """Create a GitHub issue."""
    try:
        url = f"https://api.github.com/repos/{repo}/issues"
        payload = json.dumps({"title": title, "body": body}).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"token {token}",
                "Accept": "application/vnd.github.v3+json",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            result = {
                "number": data.get("number"),
                "url": data.get("html_url"),
                "title": data.get("title"),
            }
            return CallResult.from_text(json.dumps(result, indent=2))
    except Exception as e:
        return CallResult.from_error(f"Failed to create GitHub issue: {e}")


def create_github_pr(
    repo: str, title: str, body: str, head: str, base: str, token: str
) -> CallResult:
    """Create a GitHub pull request."""
    try:
        url = f"https://api.github.com/repos/{repo}/pulls"
        payload = json.dumps({
            "title": title, "body": body, "head": head, "base": base,
        }).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"token {token}",
                "Accept": "application/vnd.github.v3+json",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            result = {
                "number": data.get("number"),
                "url": data.get("html_url"),
                "title": data.get("title"),
            }
            return CallResult.from_text(json.dumps(result, indent=2))
    except Exception as e:
        return CallResult.from_error(f"Failed to create GitHub PR: {e}")


BUILTIN_TOOLS: list[tuple[ToolDefinition, Any]] = [
    (_tool_def("query_database", "Execute a SQL query against a database", DATABASE_QUERY_SCHEMA), query_database),
    (_tool_def("read_file", "Read file contents", READ_FILE_SCHEMA), read_file),
    (_tool_def("write_file", "Write content to a file", WRITE_FILE_SCHEMA), write_file),
    (_tool_def("http_request", "Make an HTTP request", HTTP_REQUEST_SCHEMA), http_request),
    (_tool_def("git_status", "Get git status for a repository", GIT_STATUS_SCHEMA), git_status),
    (_tool_def("git_diff", "Get git diff for a repository", GIT_DIFF_SCHEMA), git_diff),
    (_tool_def("send_slack_message", "Send a message to Slack via webhook", SLACK_MESSAGE_SCHEMA), send_slack_message),
    (_tool_def("create_github_issue", "Create a GitHub issue", GITHUB_ISSUE_SCHEMA), create_github_issue),
    (_tool_def("create_github_pr", "Create a GitHub pull request", GITHUB_PR_SCHEMA), create_github_pr),
]


def get_builtin_tool_definitions() -> list[ToolDefinition]:
    return [defn for defn, _ in BUILTIN_TOOLS]


def get_builtin_tool_handler(name: str) -> Any | None:
    for defn, handler in BUILTIN_TOOLS:
        if defn.name == name:
            return handler
    return None
