"""AgentSwarm integration — multi-agent coordination from real trace transitions."""

from __future__ import annotations

from dataclasses import dataclass

# Real transition probabilities from Fable-5 traces (87.7% planning rate)
TRANSITION_MATRIX = {
    "Bash": {"Bash": 0.59, "Edit": 0.18, "Read": 0.15, "Write": 0.05, "Grep": 0.02, "Glob": 0.01},
    "Edit": {"Bash": 0.34, "Read": 0.28, "Edit": 0.20, "Write": 0.10, "Grep": 0.05, "Glob": 0.03},
    "Read": {"Bash": 0.37, "Edit": 0.22, "Read": 0.25, "Write": 0.06, "Grep": 0.07, "Glob": 0.03},
    "Write": {"Read": 0.30, "Bash": 0.35, "Edit": 0.15, "Write": 0.10, "Grep": 0.05, "Glob": 0.05},
    "Grep": {"Read": 0.40, "Edit": 0.25, "Bash": 0.20, "Grep": 0.10, "Glob": 0.05},
    "Glob": {"Read": 0.50, "Edit": 0.15, "Bash": 0.15, "Glob": 0.10, "Grep": 0.10},
}


@dataclass
class SwarmConfig:
    max_agents: int = 5
    handoff_strategy: str = "transition_matrix"
    planning_rate: float = 0.877
    error_recovery_rate: float = 0.395


@dataclass
class AgentHandoff:
    from_tool: str
    to_tool: str
    probability: float
    context_size: int = 0


class AgentSwarmIntegration:
    """Multi-agent coordination powered by FableForge's AgentSwarm.

    Uses real transition matrices from 210K agent traces to predict
    which agent/tool should handle the next step.

    When AgentSwarm is installed, delegates to its full orchestrator.
    Falls back to built-in transition-matrix routing otherwise.
    """

    def __init__(self, config: SwarmConfig | None = None):
        self.config = config or SwarmConfig()
        self._swarm = None
        self._available = False
        self._try_import()

    def _try_import(self) -> None:
        try:
            from agent_swarm.orchestrator import SwarmOrchestrator
            self._swarm = SwarmOrchestrator
            self._available = True
        except ImportError:
            self._available = False

    @property
    def available(self) -> bool:
        return self._available

    def predict_next_tool(self, current_tool: str) -> str:
        transitions = TRANSITION_MATRIX.get(current_tool, {})
        if not transitions:
            return "Read"
        return max(transitions, key=transitions.get)

    def get_handoff_probability(self, from_tool: str, to_tool: str) -> float:
        transitions = TRANSITION_MATRIX.get(from_tool, {})
        return transitions.get(to_tool, 0.0)

    def plan_agent_sequence(self, task: str, current_step: int = 0) -> list[str]:
        if self._available:
            try:
                orchestrator = self._swarm()
                result = orchestrator.coordinate(task)
                if hasattr(result, "steps"):
                    return [s.tool for s in result.steps]
            except Exception:
                pass

        sequence = []
        tools = ["Read"]
        for i in range(min(self.config.max_agents, 5)):
            next_tool = self.predict_next_tool(tools[-1])
            sequence.append(next_tool)
            tools.append(next_tool)
        return sequence

    def should_plan_before_execute(self, task_complexity: str = "medium") -> bool:
        thresholds = {"simple": 0.7, "medium": 0.877, "complex": 0.95}
        import random
        return random.random() < thresholds.get(task_complexity, self.config.planning_rate)

    def get_transition_matrix(self) -> dict:
        return TRANSITION_MATRIX.copy()
