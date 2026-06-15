"""Unit tests for trace_compiler.parser module."""

import json
import tempfile
from pathlib import Path

import pytest

from trace_compiler.parser import (
    ToolCall,
    TraceFormat,
    TraceParser,
    TraceRecord,
    _detect_format,
    _parse_armand0e_line,
    _parse_glint_line,
)


class TestToolCall:
    def test_to_dict_without_call_id(self):
        tc = ToolCall(name="bash", arguments={"command": "ls -la"})
        d = tc.to_dict()
        assert d == {"name": "bash", "arguments": {"command": "ls -la"}}
        assert "call_id" not in d

    def test_to_dict_with_call_id(self):
        tc = ToolCall(name="bash", arguments={"command": "ls"}, call_id="call_123")
        d = tc.to_dict()
        assert d["call_id"] == "call_123"


class TestTraceFormatDetection:
    def test_glint_format(self):
        line = {"uid": "1", "source_file": "test.py", "cot": "thinking...", "output_type": "text", "output": "hello"}
        assert _detect_format(line) == TraceFormat.GLINT

    def test_vfable_format(self):
        line = {"uid": "1", "source_file": "test.py", "cot": "thinking...", "output_type": "text", "output": "hello", "origin": "v-Fable"}
        assert _detect_format(line) == TraceFormat.VFABLE

    def test_armand0e_format(self):
        line = {"type": "human", "message": {"content": "hello"}, "uuid": "abc-123"}
        assert _detect_format(line) == TraceFormat.ARMAND0E

    def test_armand0e_with_parent_uuid(self):
        line = {"type": "ai", "parentUuid": "def-456", "uuid": "abc-123", "message": {}}
        assert _detect_format(line) == TraceFormat.ARMAND0E

    def test_unknown_format(self):
        line = {"random_key": "value"}
        assert _detect_format(line) == TraceFormat.UNKNOWN


class TestGlintParser:
    def test_parse_simple_glint(self):
        line = {
            "uid": "glint-001",
            "source_file": "main.py",
            "session": "session-1",
            "model": "claude-3-opus",
            "context": "Fix the bug in this code",
            "cot": "",
            "output_type": "text",
            "output": "The bug is on line 10.",
            "completion": "",
            "origin": "glint",
        }
        records = _parse_glint_line(line, TraceFormat.GLINT)
        assert len(records) == 2
        user_rec = records[0]
        assert user_rec.role == "user"
        assert user_rec.content == "Fix the bug in this code"
        assert user_rec.source_format == TraceFormat.GLINT
        assert user_rec.source_uid == "glint-001"

        asst_rec = records[1]
        assert asst_rec.role == "assistant"
        assert asst_rec.content == "The bug is on line 10."

    def test_parse_glint_with_thinking(self):
        line = {
            "uid": "glint-002",
            "source_file": "app.py",
            "session": "session-1",
            "model": "claude-3-opus",
            "context": "Debug this error",
            "cot": "Let me analyze this step by step...",
            "output_type": "text",
            "output": "Found the issue.",
            "completion": "",
            "origin": "glint",
        }
        records = _parse_glint_line(line, TraceFormat.GLINT)
        asst_rec = [r for r in records if r.role == "assistant"][0]
        assert asst_rec.thinking == "Let me analyze this step by step..."

    def test_parse_glint_with_completion(self):
        line = {
            "uid": "glint-003",
            "source_file": "app.py",
            "session": "session-1",
            "model": "claude-3-opus",
            "context": "Refactor this function",
            "cot": "",
            "output_type": "text",
            "output": "",
            "completion": "Here is the refactored version...",
            "origin": "glint",
        }
        records = _parse_glint_line(line, TraceFormat.GLINT)
        asst_rec = [r for r in records if r.role == "assistant"][0]
        assert asst_rec.content == "Here is the refactored version..."

    def test_parse_glint_tool_call(self):
        line = {
            "uid": "glint-004",
            "source_file": "app.py",
            "session": "session-1",
            "model": "claude-3-opus",
            "context": "Fix the error",
            "cot": "",
            "output_type": "tool_call",
            "output": json.dumps({"name": "bash", "arguments": {"command": "pytest"}, "id": "call_1"}),
            "completion": "",
            "origin": "glint",
        }
        records = _parse_glint_line(line, TraceFormat.GLINT)
        asst_rec = [r for r in records if r.role == "assistant"][0]
        assert len(asst_rec.tool_calls) == 1
        assert asst_rec.tool_calls[0].name == "bash"
        assert asst_rec.tool_calls[0].arguments == {"command": "pytest"}

    def test_parse_glint_tool_result(self):
        line = {
            "uid": "glint-005",
            "source_file": "",
            "session": "session-1",
            "model": "claude-3-opus",
            "context": "",
            "cot": "",
            "output_type": "tool_result",
            "output": "3 passed, 1 failed",
            "completion": "",
            "origin": "glint",
        }
        records = _parse_glint_line(line, TraceFormat.GLINT)
        assert len(records) == 1
        assert records[0].role == "tool"
        assert records[0].content == "3 passed, 1 failed"

    def test_parse_vfable_same_as_glint(self):
        line = {
            "uid": "vf-001",
            "source_file": "main.py",
            "session": "session-1",
            "model": "fable-model",
            "context": "Write a function",
            "cot": "I'll write a clean function...",
            "output_type": "text",
            "output": "def hello(): pass",
            "completion": "",
            "origin": "v-Fable",
        }
        records = _parse_glint_line(line, TraceFormat.VFABLE)
        assert records[0].source_format == TraceFormat.VFABLE


class TestArmand0eParser:
    def test_parse_simple_human_message(self):
        line = {
            "type": "human",
            "message": {"content": [{"type": "text", "text": "Hello world"}]},
            "uuid": "msg-001",
        }
        records = _parse_armand0e_line(line)
        assert len(records) == 1
        assert records[0].role == "user"
        assert records[0].content == "Hello world"

    def test_parse_ai_with_text(self):
        line = {
            "type": "ai",
            "message": {
                "content": [{"type": "text", "text": "I can help with that."}],
                "model": "claude-3-opus",
            },
            "uuid": "msg-002",
        }
        records = _parse_armand0e_line(line)
        assert len(records) == 1
        assert records[0].role == "assistant"
        assert records[0].content == "I can help with that."
        assert records[0].model == "claude-3-opus"

    def test_parse_ai_with_thinking(self):
        line = {
            "type": "ai",
            "message": {
                "content": [
                    {"type": "thinking", "thinking": "Let me analyze..."},
                    {"type": "text", "text": "Here's the answer."},
                ],
            },
            "uuid": "msg-003",
        }
        records = _parse_armand0e_line(line)
        assert len(records) == 1
        assert records[0].thinking == "Let me analyze..."
        assert records[0].content == "Here's the answer."

    def test_parse_ai_with_tool_use(self):
        line = {
            "type": "ai",
            "message": {
                "content": [
                    {"type": "text", "text": "Let me run the tests."},
                    {"type": "tool_use", "id": "call_1", "name": "bash", "input": {"command": "pytest"}},
                ],
            },
            "uuid": "msg-004",
        }
        records = _parse_armand0e_line(line)
        assert len(records) == 1
        assert records[0].role == "assistant"
        assert len(records[0].tool_calls) == 1
        assert records[0].tool_calls[0].name == "bash"
        assert records[0].tool_calls[0].arguments == {"command": "pytest"}

    def test_parse_tool_result(self):
        line = {
            "type": "tool",
            "message": {
                "content": [
                    {"type": "tool_result", "tool_use_id": "call_1", "content": "3 passed"},
                ],
            },
            "uuid": "msg-005",
        }
        records = _parse_armand0e_line(line)
        tool_record = [r for r in records if r.role == "tool"]
        assert len(tool_record) >= 1

    def test_parse_string_message(self):
        line = {
            "type": "human",
            "message": "Simple string message",
            "uuid": "msg-006",
        }
        records = _parse_armand0e_line(line)
        assert len(records) == 1
        assert records[0].content == "Simple string message"


class TestTraceParser:
    def test_parse_file(self):
        glint_line = json.dumps({
            "uid": "1", "source_file": "test.py", "session": "s1",
            "model": "claude", "context": "hello", "cot": "",
            "output_type": "text", "output": "world", "completion": "", "origin": "glint",
        })
        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write(glint_line + "\n")
            f.flush()
            parser = TraceParser()
            records = parser.parse_file(Path(f.name))
            assert len(records) == 2
            assert records[0].content == "hello"
            assert records[1].content == "world"

    def test_parse_text_multiple_lines(self):
        text = json.dumps({
            "uid": "1", "source_file": "a.py", "session": "s1",
            "model": "m", "context": "q1", "cot": "", "output_type": "text",
            "output": "a1", "completion": "", "origin": "glint",
        }) + "\n" + json.dumps({
            "uid": "2", "source_file": "b.py", "session": "s1",
            "model": "m", "context": "q2", "cot": "", "output_type": "text",
            "output": "a2", "completion": "", "origin": "glint",
        })
        parser = TraceParser()
        records = parser.parse_text(text)
        assert len(records) == 4

    def test_parse_mixed_formats(self):
        glint_line = json.dumps({
            "uid": "g1", "source_file": "a.py", "session": "s1",
            "model": "m", "context": "glint question", "cot": "",
            "output_type": "text", "output": "glint answer", "completion": "", "origin": "glint",
        })
        armand_line = json.dumps({
            "type": "human",
            "message": {"content": [{"type": "text", "text": "armand question"}]},
            "uuid": "a1",
        })
        text = glint_line + "\n" + armand_line
        parser = TraceParser()
        records = parser.parse_text(text)
        assert len(records) >= 3
        glint_records = [r for r in records if r.source_format == TraceFormat.GLINT]
        armand_records = [r for r in records if r.source_format == TraceFormat.ARMAND0E]
        assert len(glint_records) >= 2
        assert len(armand_records) >= 1

    def test_parse_file_not_found(self):
        parser = TraceParser()
        with pytest.raises(FileNotFoundError):
            parser.parse_file(Path("/nonexistent/file.jsonl"))

    def test_parse_skips_invalid_json(self):
        text = 'not valid json\n{"uid": "1", "source_file": "a.py", "session": "s1", "model": "m", "context": "q", "cot": "", "output_type": "text", "output": "a", "completion": "", "origin": "glint"}'
        parser = TraceParser()
        records = parser.parse_text(text)
        assert len(records) == 2

    def test_parse_multiple_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            f1 = Path(tmpdir) / "file1.jsonl"
            f2 = Path(tmpdir) / "file2.jsonl"
            f1.write_text(json.dumps({
                "uid": "1", "source_file": "a.py", "session": "s1",
                "model": "m", "context": "q1", "cot": "", "output_type": "text",
                "output": "a1", "completion": "", "origin": "glint",
            }) + "\n")
            f2.write_text(json.dumps({
                "uid": "2", "source_file": "b.py", "session": "s2",
                "model": "m", "context": "q2", "cot": "", "output_type": "text",
                "output": "a2", "completion": "", "origin": "glint",
            }) + "\n")
            parser = TraceParser()
            records = parser.parse_multiple([f1, f2])
            assert len(records) == 4

    def test_generic_fallback(self):
        parser = TraceParser()
        record = parser.parse_object({
            "role": "assistant",
            "content": "generic message",
            "thinking": "some thinking",
        })
        assert len(record) == 1
        assert record[0].content == "generic message"
        assert record[0].thinking == "some thinking"
        assert record[0].source_format == TraceFormat.UNKNOWN


class TestTraceRecord:
    def test_to_chat_message_simple(self):
        rec = TraceRecord(role="user", content="Hello")
        msg = rec.to_chat_message()
        assert msg == {"role": "user", "content": "Hello"}

    def test_to_chat_message_with_thinking(self):
        rec = TraceRecord(role="assistant", content="Answer", thinking="My reasoning")
        msg = rec.to_chat_message()
        assert msg["role"] == "assistant"
        assert isinstance(msg["content"], list)

    def test_to_chat_message_with_tool_calls(self):
        tc = ToolCall(name="bash", arguments={"command": "ls"}, call_id="call_1")
        rec = TraceRecord(role="assistant", content="", tool_calls=[tc])
        msg = rec.to_chat_message()
        assert msg["role"] == "assistant"
        assert isinstance(msg["content"], list)
