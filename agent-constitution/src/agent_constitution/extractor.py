"""Extract safety patterns from agent traces."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import regex


@dataclass
class SafetyPattern:
    """A single safety-relevant pattern extracted from traces."""

    pattern: str
    context: str
    severity: str  # "critical" | "high" | "medium" | "low"
    source: str = ""
    count: int = 1
    examples: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        valid_severity = {"critical", "high", "medium", "low"}
        if self.severity not in valid_severity:
            self.severity = "medium"


_REFUSAL_PATTERNS = [
    regex.compile(r"I\s+(?:can't|cannot|won't|will not|am unable to|must not|should not)\s+(?:help|assist|provide|do|perform|execute|create|write|generate)", regex.IGNORECASE),
    regex.compile(r"(?:against|violates|unethical|harmful|dangerous|illegal|illegal|malicious)", regex.IGNORECASE),
    regex.compile(r"I(?:'m| am)\s+(?:not able|unable|sorry)\s+to\s+(?:help|assist|provide|complete|do)", regex.IGNORECASE),
    regex.compile(r"(?:cannot|can't|won't)\s+(?:complete|fulfill|process|carry out)", regex.IGNORECASE),
    regex.compile(r"(?:not appropriate|not ethical|not safe|not recommended|not advisable)", regex.IGNORECASE),
    regex.compile(r"(?:refuse|decline|will not|must decline)\s+to\s+", regex.IGNORECASE),
    regex.compile(r"(?:safety|ethical|moral|legal)\s+(?:concerns?|guidelines?|boundaries?|policy|policies)", regex.IGNORECASE),
    regex.compile(r"please\s+(?:note|be aware|understand)\s+that\s+I\s+(?:can't|cannot|won't)", regex.IGNORECASE),
]

_SELF_CORRECTION_PATTERNS = [
    regex.compile(r"(?:wait|actually|let me|I should|I need to|rather|instead|on second thought)", regex.IGNORECASE),
    regex.compile(r"(?:correction|correcting|fix|revise|amend|update|I was wrong|my mistake)", regex.IGNORECASE),
    regex.compile(r"(?:better approach|different approach|improved|safer|more appropriate)", regex.IGNORECASE),
    regex.compile(r"(?:I\s+(?:should|need to|must)\s+(?:not|avoid|refrain))", regex.IGNORECASE),
    regex.compile(r"(?:let me reconsider|let me rethink|on reflection)", regex.IGNORECASE),
    regex.compile(r"(?:previously\s+(?:said|stated|suggested|recommended)|earlier\s+I)", regex.IGNORECASE),
]

_FLAGGED_CONTENT_PATTERNS = [
    regex.compile(r"(?:hack|exploit|vulnerability|attack|injection|xss|sql.?inject|csrf|rce|privesc)", regex.IGNORECASE),
    regex.compile(r"(?:password|secret|api.?key|token|credential|private.?key|access.?key)\s*[:=]", regex.IGNORECASE),
    regex.compile(r"(?:DROP\s+TABLE|DELETE\s+FROM|TRUNCATE|rmdir|rm\s+-rf|format\s+[A-Z]:)", regex.IGNORECASE),
    regex.compile(r"(?:bypass|circumvent|evade|override\s+(?:security|auth|permission|access))", regex.IGNORECASE),
    regex.compile(r"(?:personal\s+data|PII|social\s+security|credit\s+card|SSN)", regex.IGNORECASE),
    regex.compile(r"(?:rm\s+-rf|del\s+/[sS]|format\s+c:|mkfs)", regex.IGNORECASE),
    regex.compile(r"(?:sudo\s+rm|chmod\s+777|chown\s+root)", regex.IGNORECASE),
]

_SEVERITY_KEYWORDS = {
    "critical": ["hack", "exploit", "attack", "vulnerability", "inject", "xss", "rce", "privilege escalation"],
    "high": ["password", "secret", "api key", "token", "credential", "private key", "bypass security", "circumvent"],
    "medium": ["self-correction", "correction", "reconsidered", "better approach"],
    "low": ["please note", "be aware", "caution"],
}


def _load_traces(path: str | Path) -> list[dict[str, Any]]:
    """Load traces from a JSONL file."""
    traces = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                traces.append(json.loads(line))
    return traces


def _text_from_trace(trace: dict[str, Any]) -> str:
    """Extract displayable text content from a trace entry."""
    parts = []
    if "content" in trace:
        content = trace["content"]
        if isinstance(content, str):
            parts.append(content)
        elif isinstance(content, list):
            for block in content:
                if isinstance(block, dict):
                    if block.get("type") == "text":
                        parts.append(block.get("text", ""))
                    elif block.get("type") == "tool_use":
                        parts.append(json.dumps(block.get("input", {})))
                    elif block.get("type") == "tool_result":
                        content_val = block.get("content", "")
                        if isinstance(content_val, str):
                            parts.append(content_val)
                        elif isinstance(content_val, list):
                            for sub in content_val:
                                if isinstance(sub, dict) and sub.get("type") == "text":
                                    parts.append(sub.get("text", ""))
    if "role" in trace:
        pass
    return " ".join(parts)


def _compute_severity(pattern_text: str, category: str) -> str:
    """Determine severity for a matched pattern."""
    text_lower = pattern_text.lower()
    for sev, keywords in _SEVERITY_KEYWORDS.items():
        for kw in keywords:
            if kw in text_lower:
                return sev
    if category == "refusal":
        return "medium"
    if category == "self_correction":
        return "low"
    return "low"


class ExtractSafetyPatterns:
    """Extract safety-relevant patterns from agent trace data."""

    def extract_refusals(self, traces: str | Path | list[dict[str, Any]]) -> list[SafetyPattern]:
        """Extract refusal patterns from traces.

        Args:
            traces: Either a path to a JSONL file or a list of trace dicts.

        Returns:
            List of SafetyPattern objects describing refusal behaviors.
        """
        if isinstance(traces, (str, Path)):
            trace_data = _load_traces(traces)
        else:
            trace_data = traces

        patterns: dict[str, SafetyPattern] = {}
        for trace in trace_data:
            text = _text_from_trace(trace)
            if not text:
                continue
            role = trace.get("role", "")
            if role != "assistant":
                continue
            for pat in _REFUSAL_PATTERNS:
                match = pat.search(text)
                if match:
                    matched_text = match.group(0)
                    key = matched_text.lower()
                    context_start = max(0, match.start() - 60)
                    context_end = min(len(text), match.end() + 60)
                    context = text[context_start:context_end]
                    severity = _compute_severity(matched_text, "refusal")
                    if key in patterns:
                        patterns[key].count += 1
                        if len(patterns[key].examples) < 5:
                            patterns[key].examples.append(context)
                    else:
                        patterns[key] = SafetyPattern(
                            pattern=matched_text,
                            context=context,
                            severity=severity,
                            source=role,
                            count=1,
                            examples=[context],
                        )
        return sorted(patterns.values(), key=lambda p: ({"critical": 0, "high": 1, "medium": 2, "low": 3}[p.severity], -p.count))

    def extract_self_corrections(self, traces: str | Path | list[dict[str, Any]]) -> list[SafetyPattern]:
        """Extract self-correction patterns from traces.

        Args:
            traces: Either a path to a JSONL file or a list of trace dicts.

        Returns:
            List of SafetyPattern objects describing self-correction behaviors.
        """
        if isinstance(traces, (str, Path)):
            trace_data = _load_traces(traces)
        else:
            trace_data = traces

        patterns: dict[str, SafetyPattern] = {}
        for trace in trace_data:
            text = _text_from_trace(trace)
            if not text:
                continue
            role = trace.get("role", "")
            if role != "assistant":
                continue
            for pat in _SELF_CORRECTION_PATTERNS:
                match = pat.search(text)
                if match:
                    matched_text = match.group(0)
                    key = matched_text.lower()
                    context_start = max(0, match.start() - 60)
                    context_end = min(len(text), match.end() + 60)
                    context = text[context_start:context_end]
                    severity = _compute_severity(matched_text, "self_correction")
                    if key in patterns:
                        patterns[key].count += 1
                        if len(patterns[key].examples) < 5:
                            patterns[key].examples.append(context)
                    else:
                        patterns[key] = SafetyPattern(
                            pattern=matched_text,
                            context=context,
                            severity=severity,
                            source=role,
                            count=1,
                            examples=[context],
                        )
        return sorted(patterns.values(), key=lambda p: ({"critical": 0, "high": 1, "medium": 2, "low": 3}[p.severity], -p.count))

    def extract_flagged_content(self, traces: str | Path | list[dict[str, Any]]) -> list[SafetyPattern]:
        """Extract flagged/sensitive content patterns from traces.

        Args:
            traces: Either a path to a JSONL file or a list of trace dicts.

        Returns:
            List of SafetyPattern objects for flagged content.
        """
        if isinstance(traces, (str, Path)):
            trace_data = _load_traces(traces)
        else:
            trace_data = traces

        patterns: dict[str, SafetyPattern] = {}
        for trace in trace_data:
            text = _text_from_trace(trace)
            if not text:
                continue
            for pat in _FLAGGED_CONTENT_PATTERNS:
                match = pat.search(text)
                if match:
                    matched_text = match.group(0)
                    key = matched_text.lower()
                    context_start = max(0, match.start() - 80)
                    context_end = min(len(text), match.end() + 80)
                    context = text[context_start:context_end]
                    severity = _compute_severity(matched_text, "flagged_content")
                    if key in patterns:
                        patterns[key].count += 1
                        if len(patterns[key].examples) < 5:
                            patterns[key].examples.append(context)
                    else:
                        patterns[key] = SafetyPattern(
                            pattern=matched_text,
                            context=context,
                            severity=severity,
                            source=trace.get("role", "unknown"),
                            count=1,
                            examples=[context],
                        )
        return sorted(patterns.values(), key=lambda p: ({"critical": 0, "high": 1, "medium": 2, "low": 3}[p.severity], -p.count))

    def extract_all(self, traces: str | Path | list[dict[str, Any]]) -> dict[str, list[SafetyPattern]]:
        """Run all extraction methods and return combined results."""
        return {
            "refusals": self.extract_refusals(traces),
            "self_corrections": self.extract_self_corrections(traces),
            "flagged_content": self.extract_flagged_content(traces),
        }
