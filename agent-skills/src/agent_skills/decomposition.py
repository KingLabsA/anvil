"""Skill decomposition: extract skills from traces and cluster them into patterns."""

from __future__ import annotations

import json
import logging
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class Skill:
    """A discrete skill extracted from agent traces."""

    name: str
    description: str = ""
    tools: list[str] = field(default_factory=list)
    trigger_patterns: list[str] = field(default_factory=list)
    success_rate: float = 0.0
    occurrence_count: int = 0
    avg_tool_count: float = 0.0
    avg_error_rate: float = 0.0
    examples: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "tools": self.tools,
            "trigger_patterns": self.trigger_patterns,
            "success_rate": self.success_rate,
            "occurrence_count": self.occurrence_count,
            "avg_tool_count": self.avg_tool_count,
            "avg_error_rate": self.avg_error_rate,
        }


@dataclass
class SkillCluster:
    """A cluster of related skills."""

    cluster_id: str
    name: str
    description: str = ""
    skills: list[Skill] = field(default_factory=list)
    representative_tools: list[str] = field(default_factory=list)
    total_occurrences: int = 0
    avg_success_rate: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "cluster_id": self.cluster_id,
            "name": self.name,
            "description": self.description,
            "skills": [s.to_dict() for s in self.skills],
            "representative_tools": self.representative_tools,
            "total_occurrences": self.total_occurrences,
            "avg_success_rate": self.avg_success_rate,
        }


# Skill extraction patterns — tool sequences that indicate specific skills
SKILL_PATTERNS: dict[str, dict[str, Any]] = {
    "debug": {
        "required_tools": ["bash", "read"],
        "optional_tools": ["grep"],
        "indicators": ["error", "traceback", "debug", "fix", "bug"],
        "description": "Diagnose and fix errors in code",
    },
    "edit": {
        "required_tools": ["edit"],
        "optional_tools": ["read"],
        "indicators": ["change", "modify", "update", "refactor", "rename"],
        "description": "Make targeted edits to code files",
    },
    "verify": {
        "required_tools": ["bash"],
        "optional_tools": ["read", "grep"],
        "indicators": ["test", "verify", "check", "validate", "lint"],
        "description": "Run tests and verify code correctness",
    },
    "recover": {
        "required_tools": ["bash", "edit"],
        "optional_tools": ["read", "grep"],
        "indicators": ["recovery", "retry", "fallback", "exception", "catch"],
        "description": "Recover from errors and apply corrections",
    },
    "plan": {
        "required_tools": ["question", "glob"],
        "optional_tools": ["read"],
        "indicators": ["plan", "strategy", "approach", "first", "then"],
        "description": "Plan and coordinate multi-step tasks",
    },
    "bash": {
        "required_tools": ["bash"],
        "optional_tools": [],
        "indicators": ["install", "run", "execute", "command", "shell"],
        "description": "Execute shell commands and scripts",
    },
    "explore": {
        "required_tools": ["read", "glob"],
        "optional_tools": ["grep"],
        "indicators": ["explore", "understand", "investigate", "search", "find"],
        "description": "Explore and understand a codebase",
    },
    "implement": {
        "required_tools": ["edit", "write"],
        "optional_tools": ["read", "bash"],
        "indicators": ["implement", "create", "build", "add", "new"],
        "description": "Implement new features or files",
    },
}


class SkillDecomposer:
    """Extract skills from agent traces and cluster them into patterns.

    The decomposer analyzes traces of agent-tool interactions to identify
    recurring skill patterns — sequences of tool calls that form coherent
    skills like debugging, editing, verifying, recovering from errors, etc.
    """

    def __init__(self, min_occurrences: int = 3, min_success_rate: float = 0.5):
        self.min_occurrences = min_occurrences
        self.min_success_rate = min_success_rate
        self.skills: list[Skill] = []
        self.clusters: list[SkillCluster] = []

    def extract_skills_from_trace(self, trace_path: str | Path) -> list[Skill]:
        """Extract skills from a JSONL trace file.

        Each trace should contain a sequence of tool calls and their outcomes.

        Args:
            trace_path: Path to JSONL file with agent traces.

        Returns:
            List of extracted Skill objects.
        """
        trace_path = Path(trace_path)
        if not trace_path.exists():
            logger.warning(f"Trace file not found: {trace_path}")
            return []

        raw_sessions: list[dict[str, Any]] = []
        with open(trace_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    raw_sessions.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

        logger.info(f"Loaded {len(raw_sessions)} trace sessions from {trace_path}")
        return self._extract_skills_from_sessions(raw_sessions)

    def extract_skills_from_sessions(self, sessions: list[dict[str, Any]]) -> list[Skill]:
        """Extract skills from a list of session dictionaries.

        Args:
            sessions: List of session dicts with 'tool_calls' and optional 'errors'.

        Returns:
            List of extracted Skill objects.
        """
        return self._extract_skills_from_sessions(sessions)

    def _extract_skills_from_sessions(self, sessions: list[dict[str, Any]]) -> list[Skill]:
        """Internal method to extract skills from sessions."""
        extracted: dict[str, Skill] = {}

        for session in sessions:
            tool_calls = session.get("tool_calls", [])
            if not tool_calls:
                continue

            # Determine which skills are present in this session
            tool_sequence = [tc.get("name", "") for tc in tool_calls if tc.get("name")]
            errors = session.get("errors", [])
            success = session.get("success", True)
            session_tools = set(tool_sequence)

            for pattern_name, pattern in SKILL_PATTERNS.items():
                required = set(pattern["required_tools"])
                if not required.issubset(session_tools):
                    continue

                if pattern_name not in extracted:
                    extracted[pattern_name] = Skill(
                        name=pattern_name,
                        description=pattern["description"],
                        tools=list(required | set(pattern.get("optional_tools", []))),
                        trigger_patterns=pattern["indicators"],
                    )

                skill = extracted[pattern_name]
                skill.occurrence_count += 1
                skill.avg_tool_count = (
                    (skill.avg_tool_count * (skill.occurrence_count - 1) + len(tool_sequence))
                    / skill.occurrence_count
                )
                skill.avg_error_rate = (
                    (skill.avg_error_rate * (skill.occurrence_count - 1) + len(errors))
                    / skill.occurrence_count
                )
                if success:
                    skill.success_rate = (
                        (skill.success_rate * (skill.occurrence_count - 1) + 1.0)
                        / skill.occurrence_count
                    )

                # Keep a few examples
                if len(skill.examples) < 5:
                    skill.examples.append({
                        "tool_sequence": tool_sequence,
                        "errors": errors,
                        "success": success,
                    })

        # Filter by minimum occurrences and success rate
        self.skills = [
            s for s in extracted.values()
            if s.occurrence_count >= self.min_occurrences
            and s.success_rate >= self.min_success_rate
        ]

        logger.info(f"Extracted {len(self.skills)} skills from {len(sessions)} sessions")
        return self.skills

    def cluster_skills(self, skills: list[Skill] | None = None) -> list[SkillCluster]:
        """Cluster skills into groups based on tool overlap and behavior similarity.

        Uses a simple distance-based clustering where skills share at least
        one core tool or have overlapping trigger patterns.

        Args:
            skills: Optional list of skills to cluster. Uses self.skills if None.

        Returns:
            List of SkillCluster objects.
        """
        skills = skills or self.skills
        if not skills:
            return []

        # Build adjacency based on tool overlap
        clusters: dict[str, list[Skill]] = {}
        assigned: dict[str, str] = {}

        for skill in skills:
            # Find an existing cluster with significant overlap
            best_cluster = None
            best_overlap = 0.0

            for cluster_name, cluster_skills in clusters.items():
                cluster_tools = set()
                for cs in cluster_skills:
                    cluster_tools.update(cs.tools)

                overlap = len(set(skill.tools) & cluster_tools) / max(len(set(skill.tools) | cluster_tools), 1)
                if overlap > best_overlap:
                    best_overlap = overlap
                    best_cluster = cluster_name

            if best_cluster and best_overlap > 0.3:
                clusters[best_cluster].append(skill)
                assigned[skill.name] = best_cluster
            else:
                # Create new cluster
                cluster_name = f"cluster_{len(clusters)}"
                clusters[cluster_name] = [skill]
                assigned[skill.name] = cluster_name

        # Build SkillCluster objects
        self.clusters = []
        for cluster_id, cluster_skills in clusters.items():
            all_tools: Counter[str] = Counter()
            for s in cluster_skills:
                all_tools.update(s.tools)

            avg_success = sum(s.success_rate for s in cluster_skills) / len(cluster_skills)
            total_occ = sum(s.occurrence_count for s in cluster_skills)
            representative = [tool for tool, count in all_tools.most_common(5)]

            # Find or derive cluster name
            name_parts = set()
            for s in cluster_skills:
                name_parts.add(s.name)
            cluster_name = "_".join(sorted(name_parts)[:3])

            self.clusters.append(SkillCluster(
                cluster_id=cluster_id,
                name=cluster_name,
                description=f"Cluster of {len(cluster_skills)} related skills",
                skills=cluster_skills,
                representative_tools=representative,
                total_occurrences=total_occ,
                avg_success_rate=avg_success,
            ))

        logger.info(f"Clustered {len(skills)} skills into {len(self.clusters)} clusters")
        return self.clusters
