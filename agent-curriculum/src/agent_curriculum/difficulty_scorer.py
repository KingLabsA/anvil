"""Score trace difficulty based on tool count, error count, reasoning length, and session duration."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class DifficultyScore:
    """Composite difficulty score for an agent trace."""

    trace_id: str
    tool_count: int = 0
    error_count: int = 0
    reasoning_length: int = 0
    session_duration: float = 0.0
    unique_tools: int = 0
    retry_count: int = 0
    branch_count: int = 0

    # Computed scores
    tool_complexity: float = 0.0
    error_complexity: float = 0.0
    reasoning_complexity: float = 0.0
    duration_complexity: float = 0.0
    overall_difficulty: float = 0.0
    difficulty_level: str = "basic"

    def to_dict(self) -> dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "tool_count": self.tool_count,
            "error_count": self.error_count,
            "reasoning_length": self.reasoning_length,
            "session_duration": self.session_duration,
            "unique_tools": self.unique_tools,
            "retry_count": self.retry_count,
            "branch_count": self.branch_count,
            "tool_complexity": round(self.tool_complexity, 3),
            "error_complexity": round(self.error_complexity, 3),
            "reasoning_complexity": round(self.reasoning_complexity, 3),
            "duration_complexity": round(self.duration_complexity, 3),
            "overall_difficulty": round(self.overall_difficulty, 3),
            "difficulty_level": self.difficulty_level,
        }


class DifficultyScorer:
    """Score agent traces by difficulty to build curriculum training stages.

    Scoring factors:
    - Tool count: More tool calls = harder
    - Error count: More errors = harder, but retries show recovery skill
    - Reasoning length: Longer reasoning = harder
    - Session duration: Longer sessions = harder
    - Unique tools: More diverse tool use = harder
    - Branch count: More decision branches = harder
    """

    def __init__(
        self,
        tool_weight: float = 0.25,
        error_weight: float = 0.20,
        reasoning_weight: float = 0.20,
        duration_weight: float = 0.15,
        diversity_weight: float = 0.10,
        branch_weight: float = 0.10,
        max_tool_count: int = 100,
        max_reasoning_length: int = 50000,
        max_session_duration: float = 3600.0,
    ):
        self.tool_weight = tool_weight
        self.error_weight = error_weight
        self.reasoning_weight = reasoning_weight
        self.duration_weight = duration_weight
        self.diversity_weight = diversity_weight
        self.branch_weight = branch_weight
        self.max_tool_count = max_tool_count
        self.max_reasoning_length = max_reasoning_length
        self.max_session_duration = max_session_duration

    def score_trace(self, trace: dict[str, Any]) -> DifficultyScore:
        """Score an individual trace for difficulty.

        Args:
            trace: Dictionary with trace data including tool_calls, errors, etc.

        Returns:
            DifficultyScore with computed difficulty metrics.
        """
        trace_id = trace.get("id", trace.get("trace_id", "unknown"))
        tool_calls = trace.get("tool_calls", [])
        errors = trace.get("errors", [])
        reasoning = trace.get("reasoning", "")
        duration = trace.get("duration", trace.get("session_duration", 0.0))

        # Extract metrics
        tool_count = len(tool_calls)
        error_count = len(errors)
        unique_tools = len(set(tc.get("name", "") for tc in tool_calls if tc.get("name")))
        retry_count = sum(1 for e in errors if e.get("type") == "retry" or "retry" in str(e).lower())
        branch_count = trace.get("branch_count", len(set(tc.get("name", "") for tc in tool_calls[:5])))
        reasoning_length = len(reasoning) if isinstance(reasoning, str) else sum(len(r) for r in reasoning) if isinstance(reasoning, list) else 0

        # Compute normalized sub-scores (0-1)
        tool_complexity = min(tool_count / self.max_tool_count, 1.0) if self.max_tool_count > 0 else 0.0
        error_complexity = 1.0 - math.exp(-error_count / 3.0)  # exponential decay
        reasoning_complexity = min(reasoning_length / self.max_reasoning_length, 1.0) if self.max_reasoning_length > 0 else 0.0
        duration_complexity = min(duration / self.max_session_duration, 1.0) if self.max_session_duration > 0 else 0.0
        diversity_score = min(unique_tools / 6.0, 1.0)  # 6 = max unique tool types
        branch_complexity = min(branch_count / 10.0, 1.0) if branch_count > 0 else 0.0

        # Weighted overall difficulty
        overall = (
            tool_complexity * self.tool_weight
            + error_complexity * self.error_weight
            + reasoning_complexity * self.reasoning_weight
            + duration_complexity * self.duration_weight
            + diversity_score * self.diversity_weight
            + branch_complexity * self.branch_weight
        )

        # Classify difficulty level
        if overall < 0.2:
            level = "basic"
        elif overall < 0.4:
            level = "intermediate"
        elif overall < 0.6:
            level = "advanced"
        elif overall < 0.8:
            level = "expert"
        else:
            level = "master"

        return DifficultyScore(
            trace_id=trace_id,
            tool_count=tool_count,
            error_count=error_count,
            reasoning_length=reasoning_length,
            session_duration=duration,
            unique_tools=unique_tools,
            retry_count=retry_count,
            branch_count=branch_count,
            tool_complexity=tool_complexity,
            error_complexity=error_complexity,
            reasoning_complexity=reasoning_complexity,
            duration_complexity=duration_complexity,
            overall_difficulty=overall,
            difficulty_level=level,
        )

    def score_file(self, path: str | Path) -> list[DifficultyScore]:
        """Score all traces in a JSONL file.

        Args:
            path: Path to JSONL file with traces.

        Returns:
            List of DifficultyScore objects.
        """
        path = Path(path)
        scores = []
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    trace = json.loads(line)
                    scores.append(self.score_trace(trace))
                except json.JSONDecodeError:
                    continue
        return scores
