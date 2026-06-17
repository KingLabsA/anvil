"""Agent management for SDK."""

from __future__ import annotations

from typing import Any, Optional

from .types import AgentConfig


class AgentManager:
    """Manage agents via the Anvil API.

    Provides CRUD operations and invocation for agents registered
    on the Anvil server.
    """

    def __init__(self, client: Any) -> None:
        self.client = client

    def list(self) -> list[dict]:
        """List all available agents.

        Returns:
            List of agent descriptor dictionaries.
        """
        response = self.client.http_client.get("/api/agents")
        response.raise_for_status()
        return response.json()

    def get(self, agent_id: str) -> dict:
        """Get details for a specific agent.

        Args:
            agent_id: Unique identifier of the agent.

        Returns:
            Agent descriptor dictionary.
        """
        response = self.client.http_client.get(f"/api/agents/{agent_id}")
        response.raise_for_status()
        return response.json()

    def create(self, config: AgentConfig) -> dict:
        """Create a new agent.

        Args:
            config: Agent configuration.

        Returns:
            Created agent descriptor.
        """
        response = self.client.http_client.post(
            "/api/agents",
            json=config.to_dict(),
        )
        response.raise_for_status()
        return response.json()

    def invoke(
        self,
        agent_id: str,
        task: str,
        context: Optional[dict] = None,
    ) -> dict:
        """Invoke an agent with a task.

        Args:
            agent_id: Agent to invoke.
            task: Task description for the agent.
            context: Optional context dictionary.

        Returns:
            Agent response dictionary.
        """
        response = self.client.http_client.post(
            f"/api/agents/{agent_id}/invoke",
            json={"task": task, "context": context or {}},
        )
        response.raise_for_status()
        return response.json()

    def delete(self, agent_id: str) -> None:
        """Delete an agent.

        Args:
            agent_id: Agent to delete.
        """
        response = self.client.http_client.delete(f"/api/agents/{agent_id}")
        response.raise_for_status()
