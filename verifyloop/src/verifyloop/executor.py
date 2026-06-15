"""Execute phase: run tools with structured results."""

from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Any

import httpx

from verifyloop.models import ExecuteStep


class Executor:
    def __init__(
        self,
        working_dir: str = ".",
        sandbox: bool = False,
        sandbox_image: str = "python:3.11-slim",
        timeout: int = 120,
    ) -> None:
        self.working_dir = Path(working_dir).resolve()
        self.sandbox = sandbox
        self.sandbox_image = sandbox_image
        self.timeout = timeout
        self._file_history: dict[str, list[str]] = {}

    async def execute(self, tool: str, arguments: dict[str, Any]) -> ExecuteStep:
        handlers: dict[str, Any] = {
            "bash": self.bash,
            "edit": self.edit,
            "read": self.read,
            "write": self.write,
            "web_search": self.web_search,
            "web_fetch": self.web_fetch,
        }
        handler = handlers.get(tool)
        if handler is None:
            return ExecuteStep(
                tool=tool,
                arguments=arguments,
                result=f"Unknown tool: {tool}",
                success=False,
                error=f"Unknown tool: {tool}",
            )
        try:
            return await handler(**arguments)
        except Exception as exc:
            return ExecuteStep(
                tool=tool,
                arguments=arguments,
                result="",
                success=False,
                error=str(exc),
            )

    async def bash(
        self,
        command: str,
        working_dir: str | None = None,
        timeout: int | None = None,
    ) -> ExecuteStep:
        start = time.monotonic()
        cwd = str(Path(working_dir).resolve()) if working_dir else str(self.working_dir)
        exec_timeout = timeout or self.timeout

        try:
            if self.sandbox:
                result = await self._bash_docker(command, cwd, exec_timeout)
            else:
                proc = await asyncio.create_subprocess_shell(
                    command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=cwd,
                )
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(), timeout=exec_timeout
                )
                result = ExecuteStep(
                    tool="bash",
                    arguments={"command": command, "working_dir": cwd},
                    result=stdout.decode(errors="replace"),
                    success=proc.returncode == 0,
                    duration_seconds=time.monotonic() - start,
                    exit_code=proc.returncode,
                    error=stderr.decode(errors="replace") if proc.returncode else None,
                )

            result.duration_seconds = time.monotonic() - start
            return result

        except TimeoutError:
            return ExecuteStep(
                tool="bash",
                arguments={"command": command},
                result="",
                success=False,
                duration_seconds=time.monotonic() - start,
                error=f"Command timed out after {exec_timeout}s",
            )
        except Exception as exc:
            return ExecuteStep(
                tool="bash",
                arguments={"command": command},
                result="",
                success=False,
                duration_seconds=time.monotonic() - start,
                error=str(exc),
            )

    async def _bash_docker(
        self, command: str, working_dir: str, timeout: int
    ) -> ExecuteStep:
        start = time.monotonic()
        docker_cmd = [
            "docker", "run", "--rm",
            "-v", f"{working_dir}:/workspace",
            "-w", "/workspace",
            self.sandbox_image,
            "sh", "-c", command,
        ]
        proc = await asyncio.create_subprocess_exec(
            *docker_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        return ExecuteStep(
            tool="bash",
            arguments={"command": command, "working_dir": working_dir, "sandbox": True},
            result=stdout.decode(errors="replace"),
            success=proc.returncode == 0,
            duration_seconds=time.monotonic() - start,
            exit_code=proc.returncode,
            error=stderr.decode(errors="replace") if proc.returncode else None,
        )

    async def edit(
        self,
        file_path: str,
        old_content: str,
        new_content: str,
    ) -> ExecuteStep:
        start = time.monotonic()
        target = Path(file_path)
        if not target.is_absolute():
            target = self.working_dir / target

        try:
            content = target.read_text()
            if old_content not in content:
                return ExecuteStep(
                    tool="edit",
                    arguments={"file_path": str(target), "old_content": old_content, "new_content": new_content},
                    result=f"old_content not found in {target}",
                    success=False,
                    duration_seconds=time.monotonic() - start,
                    error=f"old_content not found in {target}",
                )

            self._file_history.setdefault(str(target), []).append(content)
            updated = content.replace(old_content, new_content, 1)
            target.write_text(updated)

            return ExecuteStep(
                tool="edit",
                arguments={"file_path": str(target), "old_content": old_content, "new_content": new_content},
                result=f"Edited {target}: replaced 1 occurrence",
                success=True,
                duration_seconds=time.monotonic() - start,
            )
        except FileNotFoundError:
            return ExecuteStep(
                tool="edit",
                arguments={"file_path": str(target)},
                result="",
                success=False,
                duration_seconds=time.monotonic() - start,
                error=f"File not found: {target}",
            )
        except Exception as exc:
            return ExecuteStep(
                tool="edit",
                arguments={"file_path": str(target)},
                result="",
                success=False,
                duration_seconds=time.monotonic() - start,
                error=str(exc),
            )

    async def read(self, file_path: str) -> ExecuteStep:
        start = time.monotonic()
        target = Path(file_path)
        if not target.is_absolute():
            target = self.working_dir / target

        try:
            content = target.read_text()
            self._file_history.setdefault(str(target), []).append(content)
            return ExecuteStep(
                tool="read",
                arguments={"file_path": str(target)},
                result=content,
                success=True,
                duration_seconds=time.monotonic() - start,
            )
        except FileNotFoundError:
            return ExecuteStep(
                tool="read",
                arguments={"file_path": str(target)},
                result="",
                success=False,
                duration_seconds=time.monotonic() - start,
                error=f"File not found: {target}",
            )
        except Exception as exc:
            return ExecuteStep(
                tool="read",
                arguments={"file_path": str(target)},
                result="",
                success=False,
                duration_seconds=time.monotonic() - start,
                error=str(exc),
            )

    async def write(
        self,
        file_path: str,
        content: str,
    ) -> ExecuteStep:
        start = time.monotonic()
        target = Path(file_path)
        if not target.is_absolute():
            target = self.working_dir / target

        try:
            target.parent.mkdir(parents=True, exist_ok=True)

            if target.exists():
                self._file_history.setdefault(str(target), []).append(target.read_text())

            target.write_text(content)
            return ExecuteStep(
                tool="write",
                arguments={"file_path": str(target), "content_length": len(content)},
                result=f"Wrote {len(content)} chars to {target}",
                success=True,
                duration_seconds=time.monotonic() - start,
            )
        except Exception as exc:
            return ExecuteStep(
                tool="write",
                arguments={"file_path": str(target)},
                result="",
                success=False,
                duration_seconds=time.monotonic() - start,
                error=str(exc),
            )

    async def web_search(self, query: str) -> ExecuteStep:
        start = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(
                    "https://api.duckduckgo.com/",
                    params={"q": query, "format": "json", "no_html": 1},
                )
                data = resp.json()
                results = []
                for key in ("AbstractText", "Answer", "Definition"):
                    if data.get(key):
                        results.append(data[key])
                for topic in data.get("RelatedTopics", [])[:5]:
                    if isinstance(topic, dict) and topic.get("Text"):
                        results.append(topic["Text"])
                result_text = "\n".join(results) if results else "No results found"
                return ExecuteStep(
                    tool="web_search",
                    arguments={"query": query},
                    result=result_text,
                    success=True,
                    duration_seconds=time.monotonic() - start,
                )
        except Exception as exc:
            return ExecuteStep(
                tool="web_search",
                arguments={"query": query},
                result="",
                success=False,
                duration_seconds=time.monotonic() - start,
                error=str(exc),
            )

    async def web_fetch(self, url: str) -> ExecuteStep:
        start = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                return ExecuteStep(
                    tool="web_fetch",
                    arguments={"url": url},
                    result=resp.text[:50000],
                    success=True,
                    duration_seconds=time.monotonic() - start,
                )
        except Exception as exc:
            return ExecuteStep(
                tool="web_fetch",
                arguments={"url": url},
                result="",
                success=False,
                duration_seconds=time.monotonic() - start,
                error=str(exc),
            )

    def get_file_history(self, file_path: str) -> list[str]:
        return self._file_history.get(file_path, [])

    def rollback_file(self, file_path: str) -> bool:
        history = self._file_history.get(file_path, [])
        if not history:
            return False
        Path(file_path).write_text(history.pop())
        return True
