"""Integrate Fable-5 dataset for agent and skill generation."""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class Fable5Trace:
    """A single trace from the Fable-5 dataset."""

    trace_id: str
    task: str
    steps: list[dict[str, Any]] = field(default_factory=list)
    success: bool = False
    duration_ms: float = 0.0
    tools_used: list[str] = field(default_factory=list)
    files_changed: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Fable5Blueprint:
    """An agent blueprint extracted from a Fable-5 pattern."""

    name: str
    description: str
    tools: list[str] = field(default_factory=list)
    decision_points: list[dict[str, Any]] = field(default_factory=list)
    error_handling: list[dict[str, Any]] = field(default_factory=list)
    verification_steps: list[str] = field(default_factory=list)
    source_trace_ids: list[str] = field(default_factory=list)
    confidence: float = 0.0


class Fable5Integrator:
    """Load and query the Fable-5 dataset for agent and skill generation.

    Provides pattern matching against 210K real agent traces to find
    similar workflows, extract blueprints, and recommend agent
    configurations based on proven execution patterns.
    """

    def __init__(self, dataset_path: str) -> None:
        self.dataset_path = Path(dataset_path)
        self.traces: list[Fable5Trace] = []
        self._embeddings: dict[str, list[float]] = {}
        self._index: dict[str, list[str]] = defaultdict(list)
        self._loaded = False

    def load(self) -> int:
        """Load Fable-5 traces from disk.

        Supports JSONL files (one trace per line) and JSON arrays.
        Scans the dataset directory recursively for ``*.jsonl`` and
        ``*.json`` files.

        Returns
        -------
        int
            Number of traces loaded.
        """
        if self._loaded:
            return len(self.traces)

        if not self.dataset_path.exists():
            return 0

        files: list[Path] = []
        if self.dataset_path.is_file():
            files = [self.dataset_path]
        else:
            files.extend(self.dataset_path.rglob("*.jsonl"))
            files.extend(self.dataset_path.rglob("*.json"))

        for filepath in sorted(files):
            self._load_file(filepath)

        self._build_index()
        self._loaded = True
        return len(self.traces)

    def find_similar_patterns(self, task: str, top_k: int = 5) -> list[Fable5Trace]:
        """Find traces similar to the given task description.

        Uses a combination of keyword overlap and tool-sequence matching
        to find the most relevant traces without requiring external
        embedding models.

        Parameters
        ----------
        task : str
            Task description to match against.
        top_k : int
            Maximum number of results to return.

        Returns
        -------
        list[Fable5Trace]
            Most similar traces, sorted by relevance descending.
        """
        if not self.traces:
            return []

        task_tokens = set(self._tokenize(task))
        task_type = self._classify_task(task)

        scored: list[tuple[float, Fable5Trace]] = []
        for trace in self.traces:
            score = self._compute_similarity(task, task_tokens, task_type, trace)
            if score > 0.0:
                scored.append((score, trace))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [t for _, t in scored[:top_k]]

    def extract_agent_blueprint(self, pattern: Fable5Trace | dict[str, Any]) -> Fable5Blueprint:
        """Extract an agent blueprint from a trace or pattern.

        Identifies tools used, decision points, error handling strategies,
        and verification steps from the trace's execution steps.

        Parameters
        ----------
        pattern : Fable5Trace or dict
            The trace to extract a blueprint from.

        Returns
        -------
        Fable5Blueprint
            Extracted blueprint with tools, decisions, and verification.
        """
        if isinstance(pattern, dict):
            trace = self._dict_to_trace(pattern)
        else:
            trace = pattern

        tools = list(dict.fromkeys(trace.tools_used))
        if not tools:
            tools = [s.get("tool", "") for s in trace.steps if s.get("tool")]
            tools = list(dict.fromkeys(tools))

        decision_points = self._extract_decision_points(trace.steps)
        error_handling = self._extract_error_handling(trace.steps)
        verification = self._extract_verification(trace.steps)

        confidence = 0.5
        if trace.success:
            confidence += 0.3
        if len(trace.steps) > 3:
            confidence += 0.1
        if verification:
            confidence += 0.1
        confidence = min(confidence, 1.0)

        return Fable5Blueprint(
            name=f"blueprint_{trace.trace_id[:8]}",
            description=trace.task[:200],
            tools=tools,
            decision_points=decision_points,
            error_handling=error_handling,
            verification_steps=verification,
            source_trace_ids=[trace.trace_id],
            confidence=round(confidence, 3),
        )

    def get_traces_by_tool(self, tool: str) -> list[Fable5Trace]:
        """Get all traces that use a specific tool.

        Parameters
        ----------
        tool : str
            Tool name to filter by.

        Returns
        -------
        list[Fable5Trace]
            Traces that used the specified tool.
        """
        return [t for t in self.traces if tool in t.tools_used]

    def get_successful_traces(self, task_type: str | None = None) -> list[Fable5Trace]:
        """Get successful traces, optionally filtered by task type.

        Parameters
        ----------
        task_type : str, optional
            Task type filter. If ``None``, returns all successful traces.

        Returns
        -------
        list[Fable5Trace]
            Successful traces matching the filter.
        """
        results = [t for t in self.traces if t.success]
        if task_type:
            results = [t for t in results if self._classify_task(t.task) == task_type]
        return results

    def get_task_type_distribution(self) -> dict[str, int]:
        """Get distribution of task types across loaded traces.

        Returns
        -------
        dict[str, int]
            Mapping of task type to count.
        """
        dist: dict[str, int] = defaultdict(int)
        for trace in self.traces:
            dist[self._classify_task(trace.task)] += 1
        return dict(sorted(dist.items(), key=lambda x: -x[1]))

    # ── private helpers ────────────────────────────────────────────────

    def _load_file(self, filepath: Path) -> None:
        try:
            content = filepath.read_text(encoding="utf-8", errors="ignore")
        except (OSError, PermissionError):
            return

        if filepath.suffix == ".jsonl":
            for line in content.split("\n"):
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    self.traces.append(self._dict_to_trace(data))
                except (json.JSONDecodeError, KeyError):
                    continue
        elif filepath.suffix == ".json":
            try:
                data = json.loads(content)
                if isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict):
                            self.traces.append(self._dict_to_trace(item))
                elif isinstance(data, dict):
                    self.traces.append(self._dict_to_trace(data))
            except (json.JSONDecodeError, KeyError):
                pass

    def _dict_to_trace(self, data: dict[str, Any]) -> Fable5Trace:
        steps = data.get("steps", data.get("actions", []))
        tools = list(dict.fromkeys(
            s.get("tool", "") for s in steps if isinstance(s, dict) and s.get("tool")
        ))
        files = list(dict.fromkeys(
            s.get("args", {}).get("path", "")
            for s in steps
            if isinstance(s, dict) and isinstance(s.get("args"), dict) and s["args"].get("path")
        ))

        return Fable5Trace(
            trace_id=data.get("trace_id", data.get("id", hashlib.md5(str(data).encode()).hexdigest()[:16])),
            task=data.get("task", data.get("description", data.get("prompt", ""))),
            steps=steps,
            success=data.get("success", data.get("completed", False)),
            duration_ms=float(data.get("duration_ms", data.get("duration", 0))),
            tools_used=tools,
            files_changed=[f for f in files if f],
            metadata={k: v for k, v in data.items() if k not in {
                "trace_id", "id", "task", "description", "prompt", "steps", "actions",
                "success", "completed", "duration_ms", "duration",
            }},
        )

    def _build_index(self) -> None:
        self._index.clear()
        for trace in self.traces:
            tokens = self._tokenize(trace.task)
            for token in tokens:
                self._index[token].append(trace.trace_id)

    def _tokenize(self, text: str) -> list[str]:
        return re.findall(r"[a-zA-Z_][a-zA-Z0-9_]{2,}", text.lower())

    def _classify_task(self, task: str) -> str:
        desc = task.lower()
        classifiers = [
            ("auth", ["auth", "login", "signin", "signup", "password", "jwt", "oauth"]),
            ("api", ["api", "endpoint", "route", "rest", "graphql", "webhook"]),
            ("database", ["database", "migration", "schema", "query", "sql", "table"]),
            ("testing", ["test", "spec", "coverage", "assert", "mock"]),
            ("deployment", ["deploy", "docker", "ci", "cd", "pipeline", "release"]),
            ("frontend", ["component", "ui", "css", "style", "layout", "page"]),
            ("refactoring", ["refactor", "clean", "restructure", "simplify"]),
            ("debugging", ["fix", "bug", "error", "debug", "crash", "broken"]),
            ("documentation", ["doc", "readme", "comment", "document"]),
            ("configuration", ["config", "setup", "install", "init", "env"]),
        ]
        for task_type, keywords in classifiers:
            if any(kw in desc for kw in keywords):
                return task_type
        return "general"

    def _compute_similarity(
        self,
        task: str,
        task_tokens: set[str],
        task_type: str,
        trace: Fable5Trace,
    ) -> float:
        trace_tokens = set(self._tokenize(trace.task))
        if not task_tokens or not trace_tokens:
            return 0.0

        overlap = task_tokens & trace_tokens
        jaccard = len(overlap) / len(task_tokens | trace_tokens) if (task_tokens | trace_tokens) else 0.0

        type_bonus = 0.2 if self._classify_task(trace.task) == task_type else 0.0
        success_bonus = 0.1 if trace.success else 0.0

        tool_overlap = 0.0
        if task_tokens and trace.tools_used:
            tool_keywords = set(self._tokenize(" ".join(trace.tools_used)))
            tool_overlap = len(task_tokens & tool_keywords) / len(task_tokens) * 0.1

        return jaccard * 0.6 + type_bonus + success_bonus + tool_overlap

    def _extract_decision_points(self, steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
        decisions: list[dict[str, Any]] = []
        for i, step in enumerate(steps):
            tool = step.get("tool", "")
            if tool in ("question", "bash"):
                args = step.get("args", {})
                if tool == "question":
                    decisions.append({
                        "step_index": i,
                        "type": "user_input",
                        "description": args.get("question", "User decision required"),
                    })
                elif tool == "bash":
                    cmd = args.get("command", "")
                    if any(kw in cmd for kw in ("||", "&&", "if ", "case ")):
                        decisions.append({
                            "step_index": i,
                            "type": "conditional",
                            "description": f"Branch on: {cmd[:80]}",
                        })
        return decisions

    def _extract_error_handling(self, steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
        handling: list[dict[str, Any]] = []
        for i, step in enumerate(steps):
            result = step.get("result", {})
            if isinstance(result, dict) and not result.get("success", True):
                error_msg = result.get("error", result.get("output", ""))
                next_step = steps[i + 1] if i + 1 < len(steps) else None
                recovery = ""
                if next_step:
                    recovery = str(next_step.get("args", {}))[:100]
                handling.append({
                    "step_index": i,
                    "error": str(error_msg)[:200],
                    "recovery_action": recovery,
                })
        return handling

    def _extract_verification(self, steps: list[dict[str, Any]]) -> list[str]:
        verify: list[str] = []
        for step in steps:
            tool = step.get("tool", "")
            args = step.get("args", {})
            if tool == "bash":
                cmd = args.get("command", "")
                if any(kw in cmd for kw in ("test", "lint", "check", "verify", "validate")):
                    verify.append(cmd[:200])
            elif tool == "read":
                path = args.get("path", "")
                if any(kw in path.lower() for kw in ("test", "spec")):
                    verify.append(f"Read test file: {path}")
        return list(dict.fromkeys(verify))[:10]
