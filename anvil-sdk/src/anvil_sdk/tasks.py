"""Task execution for SDK."""

from __future__ import annotations

import json
from typing import Any, Iterator, Optional

from .types import StreamChunk


class TaskManager:
    """Execute tasks via the Anvil API.

    Supports synchronous execution, streaming via WebSocket,
    and code verification/explanation/refactoring helpers.
    """

    def __init__(self, client: Any) -> None:
        self.client = client

    def run(self, task: str, model: str = "local", **kwargs: Any) -> dict:
        """Run a task synchronously.

        Args:
            task: Task description.
            model: Model identifier to use.
            **kwargs: Additional task parameters.

        Returns:
            Task result dictionary.
        """
        response = self.client.http_client.post(
            "/api/run",
            json={"task": task, "model": model, **kwargs},
        )
        response.raise_for_status()
        return response.json()

    def run_stream(
        self,
        task: str,
        model: str = "local",
        **kwargs: Any,
    ) -> Iterator[StreamChunk]:
        """Run a task with streaming response via WebSocket.

        Yields :class:`StreamChunk` instances as they arrive from the server.
        The iterator ends when a final ``result`` or ``error`` chunk is received.

        Args:
            task: Task description.
            model: Model identifier to use.
            **kwargs: Additional task parameters.

        Yields:
            StreamChunk objects from the server.
        """
        import websockets

        ws_url = self.client.api_url.replace("http", "ws") + "/ws/stream"

        with websockets.connect(ws_url) as ws:
            ws.send(json.dumps({"task": task, "model": model, **kwargs}))

            for message in ws:
                chunk = StreamChunk.from_dict(json.loads(message))
                yield chunk
                if chunk.is_final:
                    break

    def verify(self, code: str, file_path: str, language: str = "python") -> dict:
        """Verify code for correctness.

        Args:
            code: Source code to verify.
            file_path: File path context for the code.
            language: Programming language.

        Returns:
            Verification result dictionary.
        """
        response = self.client.http_client.post(
            "/api/verify",
            json={"code": code, "file_path": file_path, "language": language},
        )
        response.raise_for_status()
        return response.json()

    def explain(self, code: str) -> dict:
        """Explain what code does.

        Args:
            code: Source code to explain.

        Returns:
            Explanation result dictionary.
        """
        response = self.client.http_client.post(
            "/api/explain",
            json={"code": code},
        )
        response.raise_for_status()
        return response.json()

    def refactor(self, code: str, suggestion: str) -> dict:
        """Refactor code based on a suggestion.

        Args:
            code: Source code to refactor.
            suggestion: Refactoring suggestion or instruction.

        Returns:
            Refactored code result dictionary.
        """
        response = self.client.http_client.post(
            "/api/refactor",
            json={"code": code, "suggestion": suggestion},
        )
        response.raise_for_status()
        return response.json()
