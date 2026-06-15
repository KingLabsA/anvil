"""Parse JSONL traces from multiple agent trace formats into unified TraceRecord objects.

Supported formats:
- Glint: uid, source_file, session, model, context, cot, output_type, output, completion, origin
- armand0e: type, message (with content array), parentUuid, uuid
- v-Fable: same as Glint format
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class TraceFormat(Enum):
    GLINT = "glint"
    ARMAND0E = "armand0e"
    VFABLE = "vfable"
    UNKNOWN = "unknown"


@dataclass
class ToolCall:
    name: str
    arguments: dict[str, Any]
    call_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"name": self.name, "arguments": self.arguments}
        if self.call_id is not None:
            d["call_id"] = self.call_id
        return d


@dataclass
class TraceRecord:
    role: str
    content: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    thinking: str | None = None
    source_format: TraceFormat = TraceFormat.UNKNOWN
    source_uid: str | None = None
    session: str | None = None
    model: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_chat_message(self) -> dict[str, Any]:
        msg: dict[str, Any] = {"role": self.role}
        parts: list[dict[str, Any]] = []
        if self.thinking:
            parts.append({"type": "thinking", "thinking": self.thinking})
        if self.content:
            parts.append({"type": "text", "text": self.content})
        for tc in self.tool_calls:
            parts.append({
                "type": "tool_use",
                "id": tc.call_id or "",
                "name": tc.name,
                "input": tc.arguments,
            })
        if len(parts) == 1 and parts[0]["type"] == "text":
            msg["content"] = parts[0]["text"]
        else:
            msg["content"] = parts
        return msg


def _detect_format(line: dict[str, Any]) -> TraceFormat:
    if "source_file" in line and "cot" in line:
        if line.get("origin", "") == "v-Fable":
            return TraceFormat.VFABLE
        return TraceFormat.GLINT
    if "parentUuid" in line or "message" in line:
        return TraceFormat.ARMAND0E
    if "source_file" in line and "context" in line:
        return TraceFormat.GLINT
    return TraceFormat.UNKNOWN


def _parse_glint_line(line: dict[str, Any], fmt: TraceFormat) -> list[TraceRecord]:
    records: list[TraceRecord] = []
    uid = line.get("uid", "")
    session = line.get("session", "")
    model = line.get("model", "")
    cot = line.get("cot", "")
    output = line.get("output", "")
    output_type = line.get("output_type", "")
    context = line.get("context", "")
    completion = line.get("completion", "")
    origin = line.get("origin", "")

    if context:
        records.append(TraceRecord(
            role="user",
            content=context,
            source_format=fmt,
            source_uid=uid,
            session=session,
            model=model,
            metadata={"origin": origin},
        ))

    assistant_content = completion if completion else output
    tool_calls: list[ToolCall] = []

    if output_type in ("tool_call", "tool_use") and isinstance(output, str):
        try:
            parsed = json.loads(output)
            tool_calls.append(ToolCall(
                name=parsed.get("name", "unknown"),
                arguments=parsed.get("arguments", parsed.get("input", {})),
                call_id=parsed.get("id"),
            ))
            assistant_content = ""
        except json.JSONDecodeError:
            pass

    if output_type in ("tool_result", "tool_response"):
        result_content = output if isinstance(output, str) else json.dumps(output)
        records.append(TraceRecord(
            role="tool",
            content=result_content,
            source_format=fmt,
            source_uid=uid,
            session=session,
            model=model,
            metadata={"origin": origin},
        ))
        return records

    records.append(TraceRecord(
        role="assistant",
        content=assistant_content,
        tool_calls=tool_calls,
        thinking=cot if cot else None,
        source_format=fmt,
        source_uid=uid,
        session=session,
        model=model,
        metadata={"output_type": output_type, "origin": origin},
    ))
    return records


def _parse_armand0e_line(line: dict[str, Any]) -> list[TraceRecord]:
    records: list[TraceRecord] = []
    msg_type = line.get("type", "")
    message = line.get("message", {})
    uuid = line.get("uuid", "")

    if isinstance(message, str):
        return [TraceRecord(
            role=_map_armand0e_type(msg_type),
            content=message,
            source_format=TraceFormat.ARMAND0E,
            source_uid=uuid,
        )]

    content_array = message.get("content", [])
    if isinstance(content_array, str):
        return [TraceRecord(
            role=_map_armand0e_type(msg_type),
            content=content_array,
            source_format=TraceFormat.ARMAND0E,
            source_uid=uuid,
        )]

    combined_text: list[str] = []
    thinking_text: list[str] = []
    tool_calls: list[ToolCall] = []
    model = message.get("model", "")

    for block in content_array:
        if not isinstance(block, dict):
            combined_text.append(str(block))
            continue

        block_type = block.get("type", "")

        if block_type == "thinking":
            thinking_text.append(block.get("thinking", block.get("content", "")))
        elif block_type == "text":
            combined_text.append(block.get("text", ""))
        elif block_type == "tool_use":
            tool_calls.append(ToolCall(
                name=block.get("name", "unknown"),
                arguments=block.get("input", block.get("arguments", {})),
                call_id=block.get("id"),
            ))
        elif block_type == "tool_result":
            result_content = block.get("content", "")
            if isinstance(result_content, list):
                result_content = " ".join(
                    r.get("text", "") if isinstance(r, dict) else str(r)
                    for r in result_content
                )
            records.append(TraceRecord(
                role="tool",
                content=str(result_content),
                source_format=TraceFormat.ARMAND0E,
                source_uid=uuid,
                model=model if model else None,
            ))
        elif block_type in ("image", "image_url"):
            pass

    role = _map_armand0e_type(msg_type)
    if records and not combined_text and not tool_calls and not thinking_text:
        return records

    record = TraceRecord(
        role=role,
        content="\n".join(combined_text),
        tool_calls=tool_calls,
        thinking="\n".join(thinking_text) if thinking_text else None,
        source_format=TraceFormat.ARMAND0E,
        source_uid=uuid,
        model=model if model else None,
    )
    return [record, *records]


def _map_armand0e_type(msg_type: str) -> str:
    mapping = {
        "human": "user",
        "user": "user",
        "ai": "assistant",
        "assistant": "assistant",
        "tool": "tool",
        "system": "system",
    }
    return mapping.get(msg_type, msg_type)


class TraceParser:
    def __init__(self) -> None:
        self._records: list[TraceRecord] = []

    @property
    def records(self) -> list[TraceRecord]:
        return list(self._records)

    def parse_file(self, path: Path | str) -> list[TraceRecord]:
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Trace file not found: {path}")
        return self.parse_text(path.read_text(encoding="utf-8"))

    def parse_text(self, text: str) -> list[TraceRecord]:
        results: list[TraceRecord] = []
        for line_num, raw in enumerate(text.splitlines(), 1):
            stripped = raw.strip()
            if not stripped:
                continue
            try:
                obj = json.loads(stripped)
            except json.JSONDecodeError:
                logger.warning("Skipping invalid JSON at line %d", line_num)
                continue
            records = self.parse_object(obj)
            results.extend(records)
        self._records.extend(results)
        return results

    def parse_object(self, obj: dict[str, Any]) -> list[TraceRecord]:
        fmt = _detect_format(obj)
        if fmt in (TraceFormat.GLINT, TraceFormat.VFABLE):
            return _parse_glint_line(obj, fmt)
        if fmt == TraceFormat.ARMAND0E:
            return _parse_armand0e_line(obj)
        logger.warning("Unknown trace format, attempting generic parse")
        return self._parse_generic(obj)

    def _parse_generic(self, obj: dict[str, Any]) -> list[TraceRecord]:
        role = obj.get("role", "unknown")
        content = obj.get("content", "")
        thinking = obj.get("thinking", obj.get("cot", None))
        tool_calls: list[ToolCall] = []
        for tc in obj.get("tool_calls", []):
            if isinstance(tc, dict):
                tool_calls.append(ToolCall(
                    name=tc.get("name", tc.get("function", {}).get("name", "unknown")),
                    arguments=tc.get("arguments", tc.get("function", {}).get("arguments", {})),
                    call_id=tc.get("id"),
                ))
        return [TraceRecord(
            role=role,
            content=content if isinstance(content, str) else json.dumps(content),
            tool_calls=tool_calls,
            thinking=thinking,
            source_format=TraceFormat.UNKNOWN,
            metadata=obj,
        )]

    def parse_multiple(self, paths: list[Path | str]) -> list[TraceRecord]:
        all_records: list[TraceRecord] = []
        for p in paths:
            all_records.extend(self.parse_file(p))
        return all_records
