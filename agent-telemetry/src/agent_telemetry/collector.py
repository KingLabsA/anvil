"""Trace data ingestion: parse multiple agent trace formats and extract spans."""

from __future__ import annotations

import json
import statistics
from datetime import datetime
from pathlib import Path
from typing import Any

from agent_telemetry.models import (
    SessionMetrics,
    Span,
    SpanStatus,
    ToolMetrics,
)
from agent_telemetry.token_tracker import estimate_cost


def parse_glint_trace(jsonl_path: str | Path) -> list[dict[str, Any]]:
    """Parse Glint-Research format trace files.

    Expected format per line:
    {
        "type": "tool_call" | "tool_result" | "message" | "error",
        "timestamp": "2025-01-15T10:30:00Z",
        "session_id": "...",
        "span_id": "...",
        "tool": "Bash" | "Read" | "Edit" | "Write" | ...,
        "input": { ... },
        "output": { ... },
        "usage": {
            "input_tokens": 1234,
            "output_tokens": 567,
            "cache_read_input_tokens": 100,
            "cache_creation_input_tokens": 50
        },
        "duration_ms": 1234.5,
        "model": "claude-3.5-sonnet",
        "error": null | "error message"
    }
    """
    spans: list[dict[str, Any]] = []
    path = Path(jsonl_path)

    with path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            if entry.get("type") not in ("tool_call", "message"):
                continue

            usage = entry.get("usage", {})
            span = {
                "span_id": entry.get("span_id", ""),
                "session_id": entry.get("session_id", "unknown"),
                "tool_name": entry.get("tool", entry.get("type", "unknown")),
                "input_tokens": usage.get("input_tokens", 0),
                "output_tokens": usage.get("output_tokens", 0),
                "cache_read": usage.get("cache_read_input_tokens", 0),
                "cache_creation": usage.get("cache_creation_input_tokens", 0),
                "duration_ms": entry.get("duration_ms", 0.0),
                "status": SpanStatus.ERROR if entry.get("error") else SpanStatus.OK,
                "error": entry.get("error"),
                "model": entry.get("model", "unknown"),
                "timestamp": entry.get("timestamp"),
                "metadata": {},
            }
            cost = estimate_cost(
                span["input_tokens"],
                span["output_tokens"],
                span["model"],
                span["cache_read"],
                span["cache_creation"],
            )
            span["cost_usd"] = cost.total_cost
            spans.append(span)

    return spans


def parse_armand0e_trace(jsonl_path: str | Path) -> list[dict[str, Any]]:
    """Parse armand0e format trace files.

    Expected format per line:
    {
        "event": "invocation" | "response" | "error",
        "id": "span-id",
        "session": "session-id",
        "timestamp": "2025-01-15T10:30:00Z",
        "tool": {"name": "Bash", "input": {...}},
        "result": {...},
        "tokens": {"in": 1234, "out": 567, "cached": 100},
        "latency_ms": 1234.5,
        "model": "gpt-4o",
        "error": null | "..."
    }
    """
    spans: list[dict[str, Any]] = []
    path = Path(jsonl_path)
    pending: dict[str, dict[str, Any]] = {}

    with path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            event = entry.get("event", "")
            span_id = entry.get("id", "")

            if event == "invocation":
                pending[span_id] = {
                    "span_id": span_id,
                    "session_id": entry.get("session", "unknown"),
                    "tool_name": entry.get("tool", {}).get("name", "unknown"),
                    "timestamp": entry.get("timestamp"),
                    "model": entry.get("model", "unknown"),
                    "metadata": {"input": entry.get("tool", {}).get("input", {})},
                }
            elif event in ("response", "error"):
                tokens = entry.get("tokens", {})
                span_data = pending.pop(span_id, {
                    "span_id": span_id,
                    "session_id": entry.get("session", "unknown"),
                    "tool_name": "unknown",
                    "model": entry.get("model", "unknown"),
                    "timestamp": entry.get("timestamp"),
                    "metadata": {},
                })

                span_data["input_tokens"] = tokens.get("in", 0)
                span_data["output_tokens"] = tokens.get("out", 0)
                span_data["cache_read"] = tokens.get("cached", 0)
                span_data["cache_creation"] = tokens.get("cache_write", 0)
                span_data["duration_ms"] = entry.get("latency_ms", 0.0)
                span_data["status"] = SpanStatus.ERROR if event == "error" else SpanStatus.OK
                span_data["error"] = entry.get("error")

                cost = estimate_cost(
                    span_data["input_tokens"],
                    span_data["output_tokens"],
                    span_data["model"],
                    span_data["cache_read"],
                    span_data["cache_creation"],
                )
                span_data["cost_usd"] = cost.total_cost
                spans.append(span_data)

    for span_data in pending.values():
        span_data.setdefault("input_tokens", 0)
        span_data.setdefault("output_tokens", 0)
        span_data.setdefault("cache_read", 0)
        span_data.setdefault("cache_creation", 0)
        span_data.setdefault("duration_ms", 0.0)
        span_data.setdefault("status", SpanStatus.OK)
        span_data.setdefault("error", None)
        span_data.setdefault("cost_usd", 0.0)
        spans.append(span_data)

    return spans


def parse_vfable_trace(jsonl_path: str | Path) -> list[dict[str, Any]]:
    """Parse v-Fable format trace files.

    Expected format per line:
    {
        "kind": "tool_use" | "tool_result" | "message_start" | "message_end",
        "timestamp": "2025-01-15T10:30:00Z",
        "session_id": "...",
        "span_id": "...",
        "parent_span_id": null | "...",
        "tool_name": "Bash",
        "tokens": {"prompt": 1234, "completion": 567, "cache_read": 100, "cache_write": 50},
        "duration_ms": 1234.5,
        "cost_usd": 0.0234,
        "model": "claude-3.5-sonnet",
        "status": "success" | "error" | "timeout",
        "error_message": null | "..."
    }
    """
    spans: list[dict[str, Any]] = []
    path = Path(jsonl_path)

    with path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            if entry.get("kind") not in ("tool_use", "tool_result", "message_end"):
                continue

            tokens = entry.get("tokens", {})
            status_str = entry.get("status", "success")

            if status_str == "error":
                status = SpanStatus.ERROR
            elif status_str == "timeout":
                status = SpanStatus.TIMEOUT
            else:
                status = SpanStatus.OK

            span = {
                "span_id": entry.get("span_id", ""),
                "session_id": entry.get("session_id", "unknown"),
                "tool_name": entry.get("tool_name", "unknown"),
                "input_tokens": tokens.get("prompt", 0),
                "output_tokens": tokens.get("completion", 0),
                "cache_read": tokens.get("cache_read", 0),
                "cache_creation": tokens.get("cache_write", 0),
                "duration_ms": entry.get("duration_ms", 0.0),
                "cost_usd": entry.get("cost_usd", 0.0),
                "status": status,
                "error": entry.get("error_message"),
                "model": entry.get("model", "unknown"),
                "timestamp": entry.get("timestamp"),
                "metadata": {"parent_span_id": entry.get("parent_span_id")},
            }
            spans.append(span)

    return spans


def extract_spans(trace_data: list[dict[str, Any]]) -> list[Span]:
    """Convert raw trace dicts into validated Span objects."""
    spans = []
    for d in trace_data:
        ts = d.get("timestamp")
        if isinstance(ts, str):
            try:
                ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                ts = None
        elif not isinstance(ts, datetime):
            ts = None

        status_val = d.get("status", "ok")
        if isinstance(status_val, str):
            try:
                status_val = SpanStatus(status_val)
            except ValueError:
                status_val = SpanStatus.OK

        span = Span(
            span_id=d.get("span_id", ""),
            session_id=d.get("session_id", "unknown"),
            tool_name=d.get("tool_name", "unknown"),
            input_tokens=d.get("input_tokens", 0),
            output_tokens=d.get("output_tokens", 0),
            cache_read=d.get("cache_read", 0),
            cache_creation=d.get("cache_creation", 0),
            duration_ms=d.get("duration_ms", 0.0),
            cost_usd=d.get("cost_usd", 0.0),
            status=status_val,
            error=d.get("error"),
            model=d.get("model", "unknown"),
            timestamp=ts,
            metadata=d.get("metadata", {}),
        )
        spans.append(span)
    return spans


def _percentile(data: list[float], p: float) -> float:
    if not data:
        return 0.0
    sorted_data = sorted(data)
    k = (len(sorted_data) - 1) * p
    f = int(k)
    c = f + 1
    if c >= len(sorted_data):
        return sorted_data[-1]
    return sorted_data[f] + (k - f) * (sorted_data[c] - sorted_data[f])


def calculate_metrics(spans: list[Span]) -> dict[str, SessionMetrics | dict[str, ToolMetrics]]:
    """Calculate session-level and per-tool metrics from spans."""
    if not spans:
        return {
            "session": SessionMetrics(session_id="unknown"),
            "tools": {},
        }

    session_id = spans[0].session_id
    models = {s.model for s in spans}
    primary_model = next(iter(models)) if len(models) == 1 else "mixed"

    total_input = sum(s.input_tokens for s in spans)
    total_output = sum(s.output_tokens for s in spans)
    total_cache_read = sum(s.cache_read for s in spans)
    total_cache_creation = sum(s.cache_creation for s in spans)
    total_tokens = total_input + total_output
    total_cost = sum(s.cost_usd for s in spans)
    error_count = sum(1 for s in spans if s.status == SpanStatus.ERROR)
    durations = [s.duration_ms for s in spans if s.duration_ms > 0]

    cache_hit_rate = total_cache_read / total_input if total_input > 0 else 0.0

    timestamps = [s.timestamp for s in spans if s.timestamp]
    started_at = min(timestamps) if timestamps else None
    ended_at = max(timestamps) if timestamps else None
    duration_seconds = 0.0
    if started_at and ended_at:
        duration_seconds = (ended_at - started_at).total_seconds()

    session_metrics = SessionMetrics(
        session_id=session_id,
        total_tokens=total_tokens,
        total_cost=total_cost,
        tool_calls=len(spans),
        error_count=error_count,
        recovery_count=0,
        duration_seconds=duration_seconds,
        avg_tool_duration_ms=statistics.mean(durations) if durations else 0.0,
        p50_duration_ms=_percentile(durations, 0.50),
        p95_duration_ms=_percentile(durations, 0.95),
        p99_duration_ms=_percentile(durations, 0.99),
        cache_hit_rate=cache_hit_rate,
        model=primary_model,
        started_at=started_at,
        ended_at=ended_at,
    )

    tools_by_name: dict[str, list[Span]] = {}
    for s in spans:
        tools_by_name.setdefault(s.tool_name, []).append(s)

    tool_metrics: dict[str, ToolMetrics] = {}
    for tool_name, tool_spans in tools_by_name.items():
        t_durations = [s.duration_ms for s in tool_spans if s.duration_ms > 0]
        t_errors = sum(1 for s in tool_spans if s.status == SpanStatus.ERROR)

        tool_metrics[tool_name] = ToolMetrics(
            tool_name=tool_name,
            call_count=len(tool_spans),
            avg_duration_ms=statistics.mean(t_durations) if t_durations else 0.0,
            p50_duration_ms=_percentile(t_durations, 0.50),
            p95_duration_ms=_percentile(t_durations, 0.95),
            error_rate=t_errors / len(tool_spans) if tool_spans else 0.0,
            total_input_tokens=sum(s.input_tokens for s in tool_spans),
            total_output_tokens=sum(s.output_tokens for s in tool_spans),
            total_cache_read=sum(s.cache_read for s in tool_spans),
            total_cache_creation=sum(s.cache_creation for s in tool_spans),
            total_cost_usd=sum(s.cost_usd for s in tool_spans),
            token_distribution={
                "input": sum(s.input_tokens for s in tool_spans),
                "output": sum(s.output_tokens for s in tool_spans),
                "cache_read": sum(s.cache_read for s in tool_spans),
                "cache_creation": sum(s.cache_creation for s in tool_spans),
            },
        )

    return {"session": session_metrics, "tools": tool_metrics}


def auto_detect_format(jsonl_path: str | Path) -> str:
    """Auto-detect the trace format from the first few lines."""
    path = Path(jsonl_path)
    with path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            if "type" in entry and entry.get("type") in ("tool_call", "message", "tool_result"):
                return "glint"
            if "event" in entry and entry.get("event") in ("invocation", "response", "error"):
                return "armand0e"
            if "kind" in entry and entry.get("kind") in ("tool_use", "tool_result", "message_start", "message_end"):
                return "vfable"
            break
    return "unknown"


def ingest_trace(jsonl_path: str | Path, fmt: str | None = None) -> list[Span]:
    """Ingest a trace file, auto-detecting format if not specified."""
    if fmt is None:
        fmt = auto_detect_format(jsonl_path)

    parsers = {
        "glint": parse_glint_trace,
        "armand0e": parse_armand0e_trace,
        "vfable": parse_vfable_trace,
    }

    parser = parsers.get(fmt)
    if parser is None:
        raise ValueError(f"Unknown trace format: {fmt}. Supported: {list(parsers.keys())}")

    raw_spans = parser(jsonl_path)
    return extract_spans(raw_spans)
