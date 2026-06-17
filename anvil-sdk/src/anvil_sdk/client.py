"""Main SDK client for Anvil."""

from __future__ import annotations

from typing import Optional

import httpx

from .agents import AgentManager
from .events import EventManager
from .tasks import TaskManager


class AnvilClientError(Exception):
    """Raised when the Anvil server returns an error."""

    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"Anvil error {status_code}: {detail}")


class AnvilConnectionError(Exception):
    """Raised when the SDK cannot connect to the Anvil server."""


class AnvilClient:
    """Main client for Anvil SDK.

    Provides access to agent management, task execution, and event streaming.

    Args:
        api_url: Base URL of the Anvil server.
        api_key: Optional API key for authentication.
        timeout: Request timeout in seconds.

    Example::

        with AnvilClient("http://localhost:8000") as client:
            result = client.tasks.run("Create a fibonacci function")
            print(result)
    """

    def __init__(
        self,
        api_url: str = "http://localhost:8000",
        api_key: Optional[str] = None,
        timeout: float = 30.0,
    ):
        self.api_url = api_url.rstrip("/")
        self.api_key = api_key

        headers: dict[str, str] = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        self.http_client = httpx.Client(
            base_url=self.api_url,
            headers=headers,
            timeout=timeout,
        )

        self.agents = AgentManager(self)
        self.tasks = TaskManager(self)
        self.events = EventManager(self)

    def health_check(self) -> dict:
        """Check if the Anvil server is healthy.

        Returns:
            Dictionary with server health status.

        Raises:
            AnvilConnectionError: If the server is unreachable.
        """
        try:
            response = self.http_client.get("/api/health")
            response.raise_for_status()
            return response.json()
        except httpx.ConnectError as exc:
            raise AnvilConnectionError(
                f"Cannot connect to Anvil at {self.api_url}"
            ) from exc

    def close(self) -> None:
        """Close the underlying HTTP client and release resources."""
        self.http_client.close()

    def __enter__(self) -> AnvilClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def __repr__(self) -> str:
        return f"AnvilClient(api_url={self.api_url!r})"
