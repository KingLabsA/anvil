"""Extract patterns from Fable-5 dataset for agent and skill generation."""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ToolUsagePattern:
    """A pattern of tool usage extracted from traces."""

    tool_sequence: list[str]
    frequency: int = 0
    success_rate: float = 0.0
    avg_duration_ms: float = 0.0
    context_tags: list[str] = field(default_factory=list)


@dataclass
class TaskPattern:
    """A recurring task pattern from agent traces."""

    description: str
    task_type: str
    tool_patterns: list[ToolUsagePattern] = field(default_factory=list)
    required_tools: list[str] = field(default_factory=list)
    error_recovery_steps: list[str] = field(default_factory=list)
    verification_steps: list[str] = field(default_factory=list)
    example_traces: list[str] = field(default_factory=list)
    frequency: int = 0
    success_rate: float = 0.0


@dataclass
class PatternCluster:
    """A cluster of similar task patterns."""

    cluster_id: str
    label: str
    patterns: list[TaskPattern] = field(default_factory=list)
    dominant_task_type: str = ""
    required_tools: list[str] = field(default_factory=list)
    avg_success_rate: float = 0.0
    total_frequency: int = 0


class PatternExtractor:
    """Extract common patterns from Fable-5 agent traces.

    Analyzes execution traces to identify recurring task sequences,
    tool usage patterns, error recovery strategies, and successful
    workflows. These patterns drive automatic agent and skill creation.
    """

    def __init__(self) -> None:
        self.patterns: dict[str, TaskPattern] = {}
        self._tool_sequences: list[ToolUsagePattern] = []
        self._clusters: dict[str, PatternCluster] = {}

    def extract_from_traces(self, traces: list[dict[str, Any]]) -> list[TaskPattern]:
        """Extract common patterns from agent traces.

        Parameters
        ----------
        traces : list[dict]
            List of trace dicts, each containing at minimum:
            - ``task``: str — task description
            - ``steps``: list[dict] — execution steps with ``tool`` and ``args``
            - ``success``: bool — whether the trace completed successfully
            - ``duration_ms``: float — total execution time

        Returns
        -------
        list[TaskPattern]
            Extracted patterns sorted by frequency descending.
        """
        raw_patterns: dict[str, list[dict[str, Any]]] = defaultdict(list)

        for trace in traces:
            task_desc = trace.get("task", "")
            task_type = self._classify_task(task_desc)
            steps = trace.get("steps", [])
            success = trace.get("success", False)
            duration = trace.get("duration_ms", 0.0)

            tool_seq = [s.get("tool", "") for s in steps if s.get("tool")]
            seq_hash = self._hash_sequence(tool_seq)

            raw_patterns[seq_hash].append({
                "task_desc": task_desc,
                "task_type": task_type,
                "steps": steps,
                "success": success,
                "duration_ms": duration,
                "tool_sequence": tool_seq,
            })

        extracted: list[TaskPattern] = []
        for seq_hash, group in raw_patterns.items():
            pattern = self._build_pattern(seq_hash, group)
            if pattern.frequency >= 1:
                extracted.append(pattern)
                self.patterns[pattern.description[:80]] = pattern

        extracted.sort(key=lambda p: p.frequency, reverse=True)
        return extracted

    def cluster_patterns(self, patterns: list[TaskPattern]) -> dict[str, PatternCluster]:
        """Cluster similar patterns together using task type and tool overlap.

        Groups patterns by their task type, then merges clusters where
        tool overlap exceeds 60%.

        Returns
        -------
        dict[str, PatternCluster]
            Mapping of cluster ID to cluster.
        """
        by_type: dict[str, list[TaskPattern]] = defaultdict(list)
        for p in patterns:
            by_type[p.task_type].append(p)

        clusters: dict[str, PatternCluster] = {}
        for task_type, type_patterns in by_type.items():
            merged = self._merge_by_tool_overlap(type_patterns)
            for i, group in enumerate(merged):
                cluster_id = f"{task_type}_{i}"
                all_tools: list[str] = []
                for p in group:
                    all_tools.extend(p.required_tools)
                tool_counts = Counter(all_tools)
                required = [t for t, c in tool_counts.items() if c >= len(group) * 0.5]

                total_freq = sum(p.frequency for p in group)
                avg_success = (
                    sum(p.success_rate * p.frequency for p in group) / total_freq
                    if total_freq > 0 else 0.0
                )
                label = group[0].description[:60] if group else task_type

                clusters[cluster_id] = PatternCluster(
                    cluster_id=cluster_id,
                    label=label,
                    patterns=group,
                    dominant_task_type=task_type,
                    required_tools=sorted(set(required)),
                    avg_success_rate=round(avg_success, 3),
                    total_frequency=total_freq,
                )

        self._clusters = clusters
        return clusters

    def generate_agent_spec(self, cluster: PatternCluster) -> dict[str, Any]:
        """Generate an agent specification from a pattern cluster.

        The spec includes required tools, suggested model parameters,
        and verification rules derived from the cluster's patterns.

        Parameters
        ----------
        cluster : PatternCluster
            The pattern cluster to generate a spec for.

        Returns
        -------
        dict[str, Any]
            Agent specification ready for ``AgentGenerator``.
        """
        all_tools: set[str] = set()
        all_verify: list[str] = []
        all_recovery: list[str] = []

        for pattern in cluster.patterns:
            all_tools.update(pattern.required_tools)
            all_verify.extend(pattern.verification_steps)
            all_recovery.extend(pattern.error_recovery_steps)

        max_steps = max(
            (len(p.tool_patterns[0].tool_sequence) if p.tool_patterns else 10)
            for p in cluster.patterns
        )
        max_steps = min(max(max_steps * 2, 10), 50)

        temp = 0.1 if cluster.avg_success_rate > 0.8 else 0.2

        spec: dict[str, Any] = {
            "name": f"auto_{cluster.dominant_task_type}",
            "description": f"Auto-generated agent for {cluster.label}",
            "mode": "subagent",
            "model": "local",
            "temperature": temp,
            "top_p": 1.0,
            "max_steps": max_steps,
            "tools_whitelist": sorted(all_tools),
            "tools_blacklist": [],
            "hidden": False,
            "color": "white",
            "prompt_template": self._generate_prompt(cluster),
            "verification_rules": list(dict.fromkeys(all_verify))[:10],
            "recovery_rules": list(dict.fromkeys(all_recovery))[:5],
            "source_cluster": cluster.cluster_id,
        }
        return spec

    def generate_skill_from_examples(self, examples: list[str]) -> dict[str, Any]:
        """Generate a skill specification from example task descriptions.

        Extracts common structure, identifies inputs and outputs,
        and generates an implementation template.

        Parameters
        ----------
        examples : list[str]
            Example task descriptions or prompts.

        Returns
        -------
        dict[str, Any]
            Skill specification with name, description, steps, and template.
        """
        if not examples:
            return {"name": "empty_skill", "description": "", "steps": [], "template": ""}

        common_words = self._extract_common_words(examples)
        task_type = self._classify_task(examples[0])

        name = self._generate_skill_name(common_words, task_type)
        description = f"Auto-generated skill for {task_type} tasks"

        steps = self._extract_common_steps(examples)
        template = self._generate_skill_template(name, description, steps)

        return {
            "name": name,
            "description": description,
            "task_type": task_type,
            "steps": steps,
            "template": template,
            "examples": examples[:5],
            "common_keywords": common_words[:15],
        }

    # ── private helpers ────────────────────────────────────────────────

    def _classify_task(self, task_desc: str) -> str:
        desc = task_desc.lower()
        classifiers = [
            ("auth", ["auth", "login", "signin", "signup", "password", "jwt", "oauth", "session"]),
            ("api", ["api", "endpoint", "route", "rest", "graphql", "webhook"]),
            ("database", ["database", "migration", "schema", "query", "sql", "table", "model"]),
            ("testing", ["test", "spec", "coverage", "assert", "mock"]),
            ("deployment", ["deploy", "docker", "ci", "cd", "pipeline", "build", "release"]),
            ("frontend", ["component", "ui", "css", "style", "layout", "responsive", "page"]),
            ("refactoring", ["refactor", "clean", "restructure", "reorganize", "simplify"]),
            ("debugging", ["fix", "bug", "error", "debug", "crash", "broken", "issue"]),
            ("documentation", ["doc", "readme", "comment", "document", "explain"]),
            ("configuration", ["config", "setup", "install", "init", "environment", "env"]),
            ("security", ["security", "vulnerability", "sanitize", "encrypt", "permission"]),
            ("performance", ["optimize", "performance", "speed", "cache", "lazy", "memo"]),
        ]
        for task_type, keywords in classifiers:
            if any(kw in desc for kw in keywords):
                return task_type
        return "general"

    def _hash_sequence(self, tools: list[str]) -> str:
        return hashlib.md5("|".join(tools).encode()).hexdigest()[:12]

    def _build_pattern(self, seq_hash: str, group: list[dict[str, Any]]) -> TaskPattern:
        desc = group[0]["task_desc"][:120]
        task_type = group[0]["task_type"]
        successes = sum(1 for g in group if g["success"])
        total = len(group)
        durations = [g["duration_ms"] for g in group]

        tool_seq = group[0]["tool_sequence"]
        tool_pattern = ToolUsagePattern(
            tool_sequence=tool_seq,
            frequency=total,
            success_rate=successes / total if total > 0 else 0.0,
            avg_duration_ms=sum(durations) / len(durations) if durations else 0.0,
        )

        all_tools: list[str] = []
        for g in group:
            all_tools.extend(g["tool_sequence"])
        required = [t for t, c in Counter(all_tools).items() if c >= total * 0.3]

        error_steps: list[str] = []
        verify_steps: list[str] = []
        for g in group:
            for step in g["steps"]:
                tool = step.get("tool", "")
                if tool == "bash":
                    cmd = step.get("args", {}).get("command", "")
                    if any(kw in cmd for kw in ("test", "lint", "check", "verify")):
                        verify_steps.append(cmd)
                    if any(kw in cmd for kw in ("fix", "retry", "recover")):
                        error_steps.append(cmd)

        return TaskPattern(
            description=desc,
            task_type=task_type,
            tool_patterns=[tool_pattern],
            required_tools=sorted(set(required)),
            error_recovery_steps=list(dict.fromkeys(error_steps))[:5],
            verification_steps=list(dict.fromkeys(verify_steps))[:5],
            example_traces=[g["task_desc"][:100] for g in group[:3]],
            frequency=total,
            success_rate=successes / total if total > 0 else 0.0,
        )

    def _merge_by_tool_overlap(self, patterns: list[TaskPattern]) -> list[list[TaskPattern]]:
        if len(patterns) <= 1:
            return [patterns]

        groups: list[list[TaskPattern]] = [[patterns[0]]]
        for pattern in patterns[1:]:
            placed = False
            for group in groups:
                overlap = self._tool_overlap(pattern, group[0])
                if overlap > 0.6:
                    group.append(pattern)
                    placed = True
                    break
            if not placed:
                groups.append([pattern])
        return groups

    def _tool_overlap(self, a: TaskPattern, b: TaskPattern) -> float:
        set_a = set(a.required_tools)
        set_b = set(b.required_tools)
        if not set_a or not set_b:
            return 0.0
        intersection = set_a & set_b
        union = set_a | set_b
        return len(intersection) / len(union) if union else 0.0

    def _generate_prompt(self, cluster: PatternCluster) -> str:
        tools = ", ".join(cluster.required_tools) if cluster.required_tools else "{tools}"
        lines = [
            f"You are an auto-generated Anvil agent specialized in {cluster.label}.",
            f"Available tools: {tools}",
            "",
            "Follow these steps:",
        ]
        for i, pattern in enumerate(cluster.patterns[:3], 1):
            lines.append(f"{i}. {pattern.description}")
            if pattern.verification_steps:
                lines.append(f"   Verify: {'; '.join(pattern.verification_steps[:2])}")
        lines.append("")
        lines.append("Always verify your work after making changes.")
        return "\n".join(lines)

    def _extract_common_words(self, examples: list[str]) -> list[str]:
        stop_words = {
            "the", "a", "an", "to", "for", "in", "on", "at", "is", "it",
            "of", "and", "or", "my", "i", "we", "you", "that", "this",
            "with", "from", "by", "as", "be", "are", "was", "were", "has",
            "have", "had", "do", "does", "did", "will", "would", "can",
            "could", "should", "may", "might", "not", "no", "but", "if",
            "so", "up", "out", "about", "into", "over", "after", "then",
        }
        word_counts: Counter = Counter()
        for ex in examples:
            words = re.findall(r"[a-zA-Z_]+", ex.lower())
            word_counts.update(w for w in words if w not in stop_words and len(w) > 2)
        return [w for w, _ in word_counts.most_common(20)]

    def _generate_skill_name(self, keywords: list[str], task_type: str) -> str:
        if keywords:
            name = "_".join(keywords[:3])
        else:
            name = task_type
        return f"auto_{name}"[:40]

    def _extract_common_steps(self, examples: list[str]) -> list[str]:
        step_patterns = [
            "Analyze the current codebase",
            "Identify relevant files and dependencies",
            "Implement the changes",
            "Run tests to verify",
            "Check for lint errors",
            "Update documentation if needed",
        ]
        return step_patterns

    def _generate_skill_template(self, name: str, description: str, steps: list[str]) -> str:
        lines = [
            f"# {name}",
            "",
            description,
            "",
            "## Steps",
            "",
        ]
        for i, step in enumerate(steps, 1):
            lines.append(f"{i}. {step}")
        lines.extend([
            "",
            "## Verification",
            "",
            "- Run relevant tests",
            "- Check lint/typecheck passes",
            "- Verify no regressions",
        ])
        return "\n".join(lines)
