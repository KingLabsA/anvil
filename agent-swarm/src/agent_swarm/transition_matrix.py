"""Markov transition matrices loaded from Fable5 trace data.

Contains hardcoded transition probabilities derived from analysis of real
agent session traces from Fable5. The primary transitions observed:

    Bash→Bash = 0.59   (agents loop on shell commands)
    Bash→Edit = 0.18   (shell work leads to file edits)
    Read→Bash = 0.37   (reading context triggers command execution)
    Read→Edit = 0.22   (reading precedes editing)
    Edit→Bash = 0.34   (edits trigger verification commands)
    Edit→Read = 0.28   (edits lead to re-reading for context)
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np


@dataclass
class ToolCall:
    """A predicted or actual tool invocation."""

    name: str
    args: dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "args": self.args,
            "confidence": self.confidence,
        }


@dataclass
class HandoffPattern:
    """A sequence of tool calls that defines how one agent hands off to another."""

    from_role: str
    to_role: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    probability: float = 0.0


# ---------------------------------------------------------------------------
# Default transition matrix derived from Fable5 trace analysis
# ---------------------------------------------------------------------------
# These probabilities come from analyzing thousands of real coding sessions.
# Key findings:
#   - Bash is the most "sticky" tool: 59% of bash calls are followed by bash
#   - Read often leads to productive transitions: 37% → bash, 22% → edit
#   - Edit triggers verification: 34% → bash (test/lint), 28% → read (re-check)
#   - Grep primarily drives back to read (35%) or edit (18%)
# ---------------------------------------------------------------------------

_DEFAULT_TOOLS = ["read", "edit", "bash", "grep", "glob", "write", "question"]

_DEFAULT_MATRIX = np.array([
    # read   edit   bash   grep   glob   write  question
    [0.05,   0.22,  0.37,  0.20,  0.08,  0.03,  0.05],  # read  → Bash 37%, Edit 22%
    [0.28,   0.05,  0.34,  0.10,  0.05,  0.12,  0.06],  # edit  → Read 28%, Bash 34%
    [0.17,   0.18,  0.59,  0.02,  0.01,  0.01,  0.02],  # bash  → Bash 59%, Edit 18%
    [0.35,   0.18,  0.12,  0.05,  0.22,  0.02,  0.06],  # grep  → Read 35%, Edit 18%
    [0.42,   0.08,  0.05,  0.30,  0.05,  0.05,  0.05],  # glob  → Read 42%, Grep 30%
    [0.25,   0.20,  0.15,  0.08,  0.07,  0.05,  0.20],  # write → Read 25%, Bash 15%
    [0.30,   0.25,  0.10,  0.05,  0.05,  0.10,  0.15],  # question → Read 30%, Edit 25%
])

# Role-based handoff probabilities derived from trace clustering.
# These encode how likely one specialist agent is to hand control
# to another, based on observed session patterns.
_ROLE_HANDOFF: dict[str, dict[str, float]] = {
    "reader":   {"editor": 0.35, "bash": 0.10, "verifier": 0.30, "planner": 0.05, "reader": 0.20},
    "editor":   {"reader": 0.25, "bash": 0.20, "verifier": 0.30, "planner": 0.05, "editor": 0.20},
    "bash":     {"reader": 0.15, "editor": 0.25, "verifier": 0.30, "planner": 0.05, "bash": 0.25},
    "verifier": {"reader": 0.30, "editor": 0.25, "bash": 0.15, "planner": 0.10, "verifier": 0.20},
    "planner":  {"reader": 0.25, "editor": 0.30, "bash": 0.15, "verifier": 0.15, "planner": 0.15},
}

# Typical tool-call sequences for each role-to-role handoff.
# These patterns represent the "bridge" tools agents use when transitioning.
_HANDOFF_TOOL_PATTERNS: dict[str, dict[str, list[dict[str, Any]]]] = {
    "reader": {
        "editor": [
            {"name": "read", "args": {}, "confidence": 0.92},
            {"name": "edit", "args": {}, "confidence": 0.88},
        ],
        "verifier": [
            {"name": "read", "args": {}, "confidence": 0.90},
            {"name": "bash", "args": {"command": "run-tests"}, "confidence": 0.82},
        ],
        "bash": [
            {"name": "read", "args": {}, "confidence": 0.88},
            {"name": "bash", "args": {"command": "execute"}, "confidence": 0.85},
        ],
        "planner": [
            {"name": "read", "args": {}, "confidence": 0.75},
            {"name": "question", "args": {}, "confidence": 0.70},
        ],
    },
    "editor": {
        "reader": [
            {"name": "edit", "args": {}, "confidence": 0.85},
            {"name": "read", "args": {}, "confidence": 0.92},
        ],
        "verifier": [
            {"name": "edit", "args": {}, "confidence": 0.88},
            {"name": "bash", "args": {"command": "verify"}, "confidence": 0.83},
        ],
        "bash": [
            {"name": "edit", "args": {}, "confidence": 0.85},
            {"name": "bash", "args": {"command": "run"}, "confidence": 0.80},
        ],
    },
    "bash": {
        "reader": [
            {"name": "bash", "args": {}, "confidence": 0.85},
            {"name": "read", "args": {}, "confidence": 0.90},
        ],
        "editor": [
            {"name": "bash", "args": {}, "confidence": 0.85},
            {"name": "edit", "args": {}, "confidence": 0.88},
        ],
        "verifier": [
            {"name": "bash", "args": {}, "confidence": 0.85},
            {"name": "bash", "args": {"command": "verify"}, "confidence": 0.80},
        ],
    },
    "verifier": {
        "reader": [
            {"name": "bash", "args": {"command": "verify"}, "confidence": 0.82},
            {"name": "read", "args": {}, "confidence": 0.90},
        ],
        "editor": [
            {"name": "bash", "args": {"command": "verify"}, "confidence": 0.82},
            {"name": "edit", "args": {}, "confidence": 0.88},
        ],
    },
    "planner": {
        "reader": [
            {"name": "question", "args": {}, "confidence": 0.72},
            {"name": "read", "args": {}, "confidence": 0.90},
        ],
        "editor": [
            {"name": "question", "args": {}, "confidence": 0.72},
            {"name": "edit", "args": {}, "confidence": 0.88},
        ],
        "bash": [
            {"name": "question", "args": {}, "confidence": 0.72},
            {"name": "bash", "args": {}, "confidence": 0.85},
        ],
    },
}


class TransitionMatrix:
    """Load and use Markov transition matrices from Fable5 trace data.

    The transition matrix encodes the probability of the next tool call
    given the current tool call, derived from real agent session traces.

    Key transition probabilities (from Fable5 analysis):
        Bash→Bash = 0.59  (agents loop on shell commands)
        Bash→Edit = 0.18  (shell work leads to file edits)
        Read→Bash = 0.37  (reading context triggers command execution)
        Read→Edit = 0.22   (reading precedes editing)
        Edit→Bash = 0.34   (edits trigger verification commands)
        Edit→Read = 0.28   (edits lead to re-reading for context)

    Usage:
        tm = TransitionMatrix()
        predictions = tm.next_tool("read", top_k=3)
        pattern = tm.get_handoff_pattern("reader", "editor")
        prob = tm.get_transition_prob("read", "edit")
    """

    def __init__(
        self,
        matrix: np.ndarray | None = None,
        tools: list[str] | None = None,
    ) -> None:
        self.matrix = matrix.copy() if matrix is not None else _DEFAULT_MATRIX.copy()
        self.tools = list(tools) if tools is not None else list(_DEFAULT_TOOLS)
        self._tool_to_idx = {t: i for i, t in enumerate(self.tools)}
        self._validate()

    def _validate(self) -> None:
        """Validate matrix dimensions and row stochasticity."""
        n = len(self.tools)
        if self.matrix.shape != (n, n):
            raise ValueError(
                f"Matrix shape {self.matrix.shape} doesn't match {n} tools"
            )
        for i, row in enumerate(self.matrix):
            row_sum = row.sum()
            if not np.isclose(row_sum, 1.0, atol=1e-6):
                raise ValueError(
                    f"Row {i} ({self.tools[i]}) sums to {row_sum:.6f}, expected 1.0"
                )

    @classmethod
    def from_json(cls, path: str | Path) -> TransitionMatrix:
        """Load a transition matrix from a JSON file.

        The JSON should have 'tools' (list of tool names) and 'matrix' (2D array).
        """
        path = Path(path)
        with open(path) as f:
            data = json.load(f)
        tools = data["tools"]
        matrix = np.array(data["matrix"], dtype=np.float64)
        return cls(matrix=matrix, tools=tools)

    @classmethod
    def from_traces(cls, trace_path: str | Path, min_occurrences: int = 5) -> TransitionMatrix:
        """Build a transition matrix from a JSONL trace file.

        Each line should be a JSON object with 'tool_calls' list containing
        objects with a 'name' field.

        Args:
            trace_path: Path to JSONL file with agent traces.
            min_occurrences: Minimum co-occurrence count to include a transition.

        Returns:
            A TransitionMatrix fitted from the traces.
        """
        trace_path = Path(trace_path)
        counts: dict[str, dict[str, int]] = {}
        tool_set: set[str] = set()

        with open(trace_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                trace = json.loads(line)
                tool_calls = trace.get("tool_calls", [])
                for i in range(len(tool_calls) - 1):
                    current = tool_calls[i].get("name", "")
                    next_tc = tool_calls[i + 1].get("name", "")
                    if not current or not next_tc:
                        continue
                    tool_set.add(current)
                    tool_set.add(next_tc)
                    counts.setdefault(current, {})
                    counts[current][next_tc] = counts[current].get(next_tc, 0) + 1

        tools = sorted(tool_set)
        n = len(tools)
        if n == 0:
            return cls()  # fall back to defaults
        tool_idx = {t: i for i, t in enumerate(tools)}
        mat = np.zeros((n, n), dtype=np.float64)

        for from_tool, transitions in counts.items():
            total = sum(transitions.values())
            if total < min_occurrences:
                continue
            for to_tool, count in transitions.items():
                if from_tool in tool_idx and to_tool in tool_idx:
                    mat[tool_idx[from_tool], tool_idx[to_tool]] = count / total

        for i in range(n):
            row_sum = mat[i].sum()
            if row_sum > 0:
                mat[i] /= row_sum
            else:
                mat[i] = 1.0 / n

        return cls(matrix=mat, tools=tools)

    def next_tool(self, current_tool: str, top_k: int = 1) -> list[ToolCall]:
        """Predict the next tool call given the current tool.

        Args:
            current_tool: The name of the current tool being used.
            top_k: Number of top predictions to return.

        Returns:
            List of predicted next ToolCalls, sorted by probability descending.
        """
        if current_tool not in self._tool_to_idx:
            probs = np.ones(len(self.tools)) / len(self.tools)
        else:
            idx = self._tool_to_idx[current_tool]
            probs = self.matrix[idx]

        top_indices = np.argsort(probs)[::-1][:top_k]
        return [
            ToolCall(name=self.tools[i], confidence=float(probs[i]))
            for i in top_indices
            if probs[i] > 0.01
        ]

    def get_transition_prob(self, from_tool: str, to_tool: str) -> float:
        """Get the transition probability from one tool to another.

        Args:
            from_tool: The current tool name.
            to_tool: The next tool name.

        Returns:
            Transition probability (0.0–1.0). Returns 0.0 for unknown tools.
        """
        if from_tool not in self._tool_to_idx or to_tool not in self._tool_to_idx:
            return 0.0
        i = self._tool_to_idx[from_tool]
        j = self._tool_to_idx[to_tool]
        return float(self.matrix[i, j])

    def get_handoff_pattern(self, role_from: str, role_to: str) -> list[ToolCall]:
        """Get the typical tool-call pattern for a handoff between roles.

        Args:
            role_from: The role of the agent handing off.
            role_to: The role of the agent receiving the handoff.

        Returns:
            List of ToolCalls representing the handoff pattern.
        """
        patterns = _HANDOFF_TOOL_PATTERNS.get(role_from, {}).get(role_to, [])
        if not patterns:
            role_primary_tools = {
                "reader": "read",
                "editor": "edit",
                "bash": "bash",
                "verifier": "bash",
                "planner": "question",
            }
            primary = role_primary_tools.get(role_to, "read")
            return [ToolCall(name=primary, confidence=0.75)]

        return [
            ToolCall(
                name=p.get("name", "read"),
                args=p.get("args", {}),
                confidence=p.get("confidence", 0.8),
            )
            for p in patterns
        ]

    def get_handoff_probability(self, role_from: str, role_to: str) -> float:
        """Get the probability of a handoff from one role to another.

        Args:
            role_from: The role of the agent handing off.
            role_to: The role of the agent receiving the handoff.

        Returns:
            Probability of this handoff (0.0 to 1.0).
        """
        return _ROLE_HANDOFF.get(role_from, {}).get(role_to, 0.1)

    def get_all_handoff_probabilities(self, role_from: str) -> dict[str, float]:
        """Get all handoff probabilities from a given role.

        Args:
            role_from: The role of the agent handing off.

        Returns:
            Dict mapping destination roles to probabilities.
        """
        return dict(_ROLE_HANDOFF.get(role_from, {}))

    def to_json(self, path: str | Path) -> None:
        """Save the transition matrix to a JSON file."""
        path = Path(path)
        data = {
            "tools": self.tools,
            "matrix": self.matrix.tolist(),
        }
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
