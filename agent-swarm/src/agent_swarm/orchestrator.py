"""Swarm orchestrator that coordinates micro-agents using transition matrix handoffs."""

from __future__ import annotations

import asyncio
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from agent_swarm.agents import (
    AgentRole,
    AgentMessage as AgentsAgentMessage,
    BaseAgent,
    create_agent,
)
import numpy as np

from agent_swarm.models import (
    HandoffEvent,
    SwarmResult,
)
from agent_swarm.transition_matrix import TransitionMatrix


class SwarmStatus(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    WAITING = "waiting"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class HandoffRecord:
    """Record of an agent handoff event."""

    from_role: str
    to_role: str
    context: dict[str, Any]
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "from_role": self.from_role,
            "to_role": self.to_role,
            "context": self.context,
            "timestamp": self.timestamp,
        }


@dataclass
class SwarmTask:
    """A task for the swarm to execute."""

    description: str
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    status: SwarmStatus = SwarmStatus.IDLE
    current_agent: str = "planner"
    history: list[dict[str, Any]] = field(default_factory=list)
    result: str | None = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    completed_at: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "description": self.description,
            "status": self.status.value,
            "current_agent": self.current_agent,
            "history": self.history,
            "result": self.result,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "metadata": self.metadata,
        }


class SwarmOrchestrator:
    """Orchestrates micro-agent swarms using Markov transition matrices.

    The orchestrator uses real trace transition data to predict which agent
    should handle the next step, and provides structured handoff mechanisms
    so agents can pass context to each other.

    Key transition probabilities from Fable5 analysis:
        Bash→Bash = 0.59, Bash→Edit = 0.18
        Read→Bash = 0.37, Read→Edit = 0.22
        Edit→Bash = 0.34, Edit→Read = 0.28

    Attributes:
        transition_matrix: The Markov transition matrix for tool predictions.
        agents: Dictionary of active agents keyed by role.
        tasks: Dictionary of tasks keyed by ID.
        handoff_log: Log of all handoff events.
        max_handoffs: Maximum handoffs before forcing completion.

    Example:
        >>> orchestrator = SwarmOrchestrator()
        >>> task = orchestrator.coordinate("Fix the login bug")
        >>> result = orchestrator.run("Fix the login bug")
        >>> print(result.summary())
    """

    def __init__(
        self,
        transition_matrix: TransitionMatrix | None = None,
        max_handoffs: int = 20,
    ) -> None:
        self.transition_matrix = transition_matrix or TransitionMatrix()
        self.agents: dict[str, BaseAgent] = {}
        self.tasks: dict[str, SwarmTask] = {}
        self.handoff_log: list[HandoffRecord] = []
        self.max_handoffs = max_handoffs
        self._active_tasks: dict[str, asyncio.Task] = {}

    def spawn_agent(self, role: str) -> BaseAgent:
        """Spawn a new micro-agent with the given role.

        Args:
            role: The role for the new agent (reader, editor, bash, verifier, planner).

        Returns:
            The newly created agent.

        Raises:
            ValueError: If the role is not recognized.
        """
        agent = create_agent(role)
        self.agents[agent.role.value] = agent
        return agent

    def _ensure_agents(self) -> None:
        """Ensure all agent roles have been spawned."""
        for role in AgentRole:
            if role.value not in self.agents:
                self.spawn_agent(role.value)

    def coordinate(self, task_description: str, metadata: dict[str, Any] | None = None) -> SwarmTask:
        """Coordinate a swarm to execute a task.

        Creates a new task, starts with the Planner agent, and uses
        transition matrix data to predict handoffs.

        Args:
            task_description: Natural language description of the task.
            metadata: Optional metadata to attach to the task.

        Returns:
            The SwarmTask with execution context.
        """
        self._ensure_agents()
        task = SwarmTask(
            description=task_description,
            metadata=metadata or {},
        )
        self.tasks[task.id] = task
        task.status = SwarmStatus.RUNNING
        task.current_agent = "planner"
        task.history.append({
            "event": "task_created",
            "agent": "planner",
            "description": task_description,
        })
        return task

    async def coordinate_async(self, task_description: str, metadata: dict[str, Any] | None = None) -> SwarmTask:
        """Async version of coordinate for use with asyncio event loops."""
        return self.coordinate(task_description, metadata)

    def handoff(
        self,
        from_agent: str,
        to_agent: str,
        context: dict[str, Any],
    ) -> HandoffRecord:
        """Execute a handoff from one agent to another.

        Args:
            from_agent: The role of the agent handing off.
            to_agent: The role of the agent receiving the handoff.
            context: Context dict to pass to the next agent.

        Returns:
            A HandoffRecord documenting the handoff.

        Raises:
            ValueError: If either agent role is not recognized.
        """
        valid_roles = {r.value for r in AgentRole}
        if from_agent not in valid_roles:
            raise ValueError(f"Unknown from_agent role: {from_agent}")
        if to_agent not in valid_roles:
            raise ValueError(f"Unknown to_agent role: {to_agent}")

        handoff_pattern = self.transition_matrix.get_handoff_pattern(from_agent, to_agent)
        handoff_probability = self.transition_matrix.get_handoff_probability(from_agent, to_agent)

        enriched_context = {
            **context,
            "handoff_pattern": [tc.to_dict() for tc in handoff_pattern],
            "handoff_probability": handoff_probability,
        }

        if to_agent in self.agents:
            msg = AgentsAgentMessage(
                role="system",
                content=f"Handoff from {from_agent} agent",
                metadata=enriched_context,
            )
            self.agents[to_agent].add_message(msg)

        record = HandoffRecord(
            from_role=from_agent,
            to_role=to_agent,
            context=enriched_context,
        )
        self.handoff_log.append(record)

        # Update current task if one is active
        for task in self.tasks.values():
            if task.status == SwarmStatus.RUNNING and task.current_agent == from_agent:
                task.current_agent = to_agent
                task.history.append({
                    "event": "handoff",
                    "from": from_agent,
                    "to": to_agent,
                    "probability": handoff_probability,
                })
                break

        return record

    def run(self, task_description: str, metadata: dict[str, Any] | None = None) -> SwarmResult:
        """Execute a task through the full swarm pipeline and return a SwarmResult.

        The swarm follows this flow:
        1. Planner analyzes the task and determines the approach
        2. Reader gathers context from the codebase
        3. Editor makes changes based on context
        4. Verifier checks the changes
        5. Loop back if verification fails, otherwise complete

        Args:
            task_description: Natural language description of the task.
            metadata: Optional metadata to attach to the result.

        Returns:
            A SwarmResult with execution details, handoff history, and output.
        """
        self._ensure_agents()
        task = self.coordinate(task_description, metadata)

        handoff_events: list[HandoffEvent] = []
        agent_history: list[dict[str, Any]] = []
        current_role = "planner"

        # Phase 1: Planner analyzes
        planner = self.agents["planner"]
        planner.add_message(AgentsAgentMessage(
            role="user",
            content=task_description,
        ))
        agent_history.append({
            "agent": "planner",
            "action": "analyze",
            "description": task_description,
        })

        # Phase 2: Planner → Reader (gather context)
        record = self.handoff("planner", "reader", {
            "task": task_description,
            "phase": "exploration",
        })
        handoff_events.append(HandoffEvent(
            from_role=AgentRole.PLANNER,
            to_role=AgentRole.READER,
            context={"task": task_description, "phase": "exploration"},
            probability=self.transition_matrix.get_handoff_probability("planner", "reader"),
            pattern=[tc.to_dict() for tc in self.transition_matrix.get_handoff_pattern("planner", "reader")],
        ))
        current_role = "reader"
        reader = self.agents["reader"]
        reader.add_message(AgentsAgentMessage(
            role="system",
            content=f"Explore codebase for: {task_description}",
        ))
        agent_history.append({
            "agent": "reader",
            "action": "explore",
            "description": f"Reading codebase to understand: {task_description}",
        })

        # Phase 3: Reader → Editor (implement changes)
        record = self.handoff("reader", "editor", {
            "task": task_description,
            "phase": "implementation",
            "findings": "Context gathered from codebase",
        })
        handoff_events.append(HandoffEvent(
            from_role=AgentRole.READER,
            to_role=AgentRole.EDITOR,
            context={"task": task_description, "phase": "implementation"},
            probability=self.transition_matrix.get_handoff_probability("reader", "editor"),
            pattern=[tc.to_dict() for tc in self.transition_matrix.get_handoff_pattern("reader", "editor")],
        ))
        current_role = "editor"
        editor = self.agents["editor"]
        editor.add_message(AgentsAgentMessage(
            role="system",
            content=f"Implement changes for: {task_description}",
        ))
        agent_history.append({
            "agent": "editor",
            "action": "edit",
            "description": f"Implementing solution for: {task_description}",
        })

        # Phase 4: Editor → Verifier (validate changes)
        record = self.handoff("editor", "verifier", {
            "task": task_description,
            "phase": "verification",
        })
        handoff_events.append(HandoffEvent(
            from_role=AgentRole.EDITOR,
            to_role=AgentRole.VERIFIER,
            context={"task": task_description, "phase": "verification"},
            probability=self.transition_matrix.get_handoff_probability("editor", "verifier"),
            pattern=[tc.to_dict() for tc in self.transition_matrix.get_handoff_pattern("editor", "verifier")],
        ))
        current_role = "verifier"
        verifier = self.agents["verifier"]
        verifier.add_message(AgentsAgentMessage(
            role="system",
            content=f"Verify changes for: {task_description}",
        ))
        agent_history.append({
            "agent": "verifier",
            "action": "verify",
            "description": f"Verifying solution for: {task_description}",
        })

        # Determine final state — use transition matrix to check if we should loop
        # In a real implementation, the verifier result would determine this.
        # Here we follow the common pattern: verifier → done (or back to editor)
        verify_to_editor_prob = self.transition_matrix.get_handoff_probability("verifier", "editor")

        # If verification loops back to editor, record that cycle
        iterations = 1
        max_verify_loops = min(self.max_handoffs - len(handoff_events), 3)
        while iterations <= max_verify_loops:
            if verify_to_editor_prob > 0.25 and iterations < 2:
                # Simulate a verification loop
                record = self.handoff("verifier", "editor", {
                    "task": task_description,
                    "phase": "fix",
                    "iteration": iterations,
                })
                handoff_events.append(HandoffEvent(
                    from_role=AgentRole.VERIFIER,
                    to_role=AgentRole.EDITOR,
                    context={"task": task_description, "phase": "fix", "iteration": iterations},
                    probability=verify_to_editor_prob,
                    pattern=[tc.to_dict() for tc in self.transition_matrix.get_handoff_pattern("verifier", "editor")],
                ))
                current_role = "editor"
                agent_history.append({
                    "agent": "editor",
                    "action": "fix",
                    "description": f"Fix issues found in verification pass {iterations}",
                })
                iterations += 1
                break  # Only loop once in the simulated flow
            break

        # Mark task complete
        task.status = SwarmStatus.COMPLETED
        task.result = f"Task completed via swarm coordination ({iterations} verification iterations)"
        task.completed_at = datetime.now(timezone.utc).isoformat()

        return SwarmResult(
            task_id=task.id,
            task_description=task_description,
            status="completed",
            final_agent=current_role,
            final_output=task.result or "Task completed",
            handoffs=handoff_events,
            agent_history=agent_history,
            total_handoffs=len(handoff_events),
            created_at=task.created_at,
            completed_at=task.completed_at,
            metadata=metadata or {},
        )

    async def run_async(self, task_description: str, metadata: dict[str, Any] | None = None) -> SwarmResult:
        """Async version of run for use with asyncio event loops."""
        return self.run(task_description, metadata)

    def predict_next_agent(self, current_agent: str, current_tool: str | None = None) -> str:
        """Predict which agent should handle the next step.

        Uses the transition matrix to determine the most likely next agent.

        Args:
            current_agent: The current agent's role.
            current_tool: Optional current tool for finer-grained prediction.

        Returns:
            The predicted next agent role.
        """
        if current_tool:
            next_tools = self.transition_matrix.next_tool(current_tool, top_k=5)
            tool_to_role = {
                "read": "reader",
                "edit": "editor",
                "write": "editor",
                "bash": "bash",
                "grep": "reader",
                "glob": "reader",
                "question": "planner",
            }
            for tc in next_tools:
                mapped_role = tool_to_role.get(tc.name, current_agent)
                if mapped_role != current_agent:
                    return mapped_role

        probabilities = self.transition_matrix.get_all_handoff_probabilities(current_agent)
        if not probabilities:
            return current_agent

        sorted_roles = sorted(probabilities.items(), key=lambda x: x[1], reverse=True)
        for role, prob in sorted_roles:
            if role != current_agent:
                return role

        return current_agent

    def get_status(self, task_id: str | None = None) -> dict[str, Any]:
        """Get the current status of the swarm or a specific task.

        Args:
            task_id: Optional task ID to get specific status.

        Returns:
            Status dictionary with task info and agent states.
        """
        if task_id and task_id in self.tasks:
            task = self.tasks[task_id]
            return {
                "task": task.to_dict(),
                "active_agents": list(self.agents.keys()),
                "total_handoffs": len(self.handoff_log),
            }

        return {
            "total_tasks": len(self.tasks),
            "active_agents": list(self.agents.keys()),
            "total_handoffs": len(self.handoff_log),
            "tasks": {
                tid: {
                    "status": t.status.value,
                    "current_agent": t.current_agent,
                    "description": t.description[:100],
                }
                for tid, t in self.tasks.items()
            },
        }

    def visualize(self) -> str:
        """Generate a text-based visualization of the swarm state.

        Returns:
            A formatted string showing agents, transitions, and task status.
        """
        lines = ["=== AgentSwarm Visualization ===", ""]

        lines.append("Active Agents:")
        for role, agent in self.agents.items():
            lines.append(f"  [{role}] tools={agent.tool_names()} handoff_to={[r.value for r in agent.can_handoff_to]}")
        lines.append("")

        lines.append("Transition Matrix (tool → tool):")
        for tool in self.transition_matrix.tools:
            next_tc = self.transition_matrix.next_tool(tool, top_k=3)
            next_str = ", ".join(f"{tc.name}({tc.confidence:.2f})" for tc in next_tc)
            lines.append(f"  {tool} → {next_str}")
        lines.append("")

        lines.append("Key Fable5 Transitions:")
        key_transitions = [
            ("bash", "bash"), ("bash", "edit"), ("read", "bash"),
            ("read", "edit"), ("edit", "bash"), ("edit", "read"),
        ]
        for from_t, to_t in key_transitions:
            prob = self.transition_matrix.get_transition_prob(from_t, to_t)
            bar = "█" * int(prob * 40)
            lines.append(f"  {from_t:8s} → {to_t:8s} {prob:.2f} {bar}")
        lines.append("")

        lines.append("Handoff Probabilities:")
        for from_role in sorted(set(r.value for r in AgentRole)):
            probs = self.transition_matrix.get_all_handoff_probabilities(from_role)
            for to_role, prob in sorted(probs.items(), key=lambda x: x[1], reverse=True):
                if prob > 0.05:
                    bar = "█" * int(prob * 40)
                    lines.append(f"  {from_role:10s} → {to_role:10s} {prob:.2f} {bar}")
        lines.append("")

        if self.tasks:
            lines.append("Tasks:")
            for task_id, task in self.tasks.items():
                lines.append(f"  [{task_id}] {task.status.value} - {task.description[:80]}")
                lines.append(f"    current_agent: {task.current_agent}, handoffs: {len(task.history)}")

        return "\n".join(lines)

    def save_state(self, path: str | Path) -> None:
        """Save the orchestrator state to a JSON file."""
        path = Path(path)
        data = {
            "agents": {role: agent.to_dict() for role, agent in self.agents.items()},
            "tasks": {tid: task.to_dict() for tid, task in self.tasks.items()},
            "handoff_log": [r.to_dict() for r in self.handoff_log],
            "transition_matrix": {
                "tools": self.transition_matrix.tools,
                "matrix": self.transition_matrix.matrix.tolist(),
            },
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    def load_state(self, path: str | Path) -> None:
        """Load the orchestrator state from a JSON file."""
        path = Path(path)
        with open(path) as f:
            data = json.load(f)

        for role_str, agent_data in data["agents"].items():
            agent = self.spawn_agent(role_str)
            agent._context = [
                AgentsAgentMessage(
                    role=m.get("role", "system"),
                    content=m.get("content", ""),
                    metadata=m.get("metadata", {}),
                )
                for m in agent_data.get("context", [])
            ]

        for tid, task_data in data["tasks"].items():
            task = SwarmTask(
                description=task_data["description"],
                id=tid,
                status=SwarmStatus(task_data["status"]),
                current_agent=task_data["current_agent"],
                history=task_data["history"],
                result=task_data.get("result"),
                created_at=task_data["created_at"],
                completed_at=task_data.get("completed_at"),
                metadata=task_data.get("metadata", {}),
            )
            self.tasks[tid] = task

        self.handoff_log = [
            HandoffRecord(
                from_role=h["from_role"],
                to_role=h["to_role"],
                context=h["context"],
                timestamp=h["timestamp"],
                id=h["id"],
            )
            for h in data["handoff_log"]
        ]

        tm_data = data["transition_matrix"]
        self.transition_matrix = TransitionMatrix(
            matrix=np.array(tm_data["matrix"]),
            tools=tm_data["tools"],
        )
