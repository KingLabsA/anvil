"""Extract named skills from parsed agent traces.

Skill types:
- DEBUG: traces where error recovery happens
- EDIT: traces with Edit tool calls
- VERIFY: traces with verification reasoning
- RECOVER: traces with error -> recovery patterns
- PLAN: traces with planning reasoning
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from trace_compiler.parser import TraceRecord


class SkillType(Enum):
    DEBUG = "debug"
    EDIT = "edit"
    VERIFY = "verify"
    RECOVER = "recover"
    PLAN = "plan"


_SKILL_DETECTORS: dict[SkillType, list[str]] = {
    SkillType.DEBUG: [
        "error", "exception", "traceback", "bug", "debug", "fix",
        "stack trace", "traceback", "runtimeerror", "typeerror",
        "valueerror", "keyerror", "attributeerror", "importerror",
    ],
    SkillType.EDIT: [
        "edit", "replace", "modify", "update", "change", "insert",
        "delete", "refactor", "rewrite", "patch",
    ],
    SkillType.VERIFY: [
        "verify", "check", "confirm", "validate", "assert", "test",
        "coverage", "passing", "failing", "expected", "actual",
    ],
    SkillType.RECOVER: [
        "recover", "retry", "fallback", "handle", "catch", "rescue",
        "restore", "remediate", "workaround",
    ],
    SkillType.PLAN: [
        "plan", "strategy", "approach", "step", "first", "then",
        "next", "finally", "roadmap", "outline", "breakdown",
    ],
}

_EDIT_TOOL_NAMES = {
    "edit", "replace", "write", "create_file", "modify_file",
    "str_replace_editor", "apply_patch",
}

_VERIFY_TOOL_NAMES = {
    "bash", "shell", "terminal", "run_command", "execute",
}

_DEBUG_SIGNALS = {
    "error", "exception", "traceback", "failed", "failure",
    "stacktrace", "bug", "crash",
}

_PLAN_THINKING_PATTERNS = [
    r"(?i)(let me|I'll|I will|first,?\s*I|my (?:approach|plan|strategy))",
    r"(?i)(step\s*\d|first.*then|1\.\s|plan:|approach:)",
    r"(?i)(going to|gonna|will (?:start|begin|try|attempt))",
]


@dataclass
class SkillExample:
    skill_type: SkillType
    messages: list[dict[str, Any]]
    source_uid: str | None = None
    session: str | None = None
    model: str | None = None
    confidence: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_training_sample(self) -> dict[str, Any]:
        return {
            "messages": self.messages,
            "skill_type": self.skill_type.value,
            "source_uid": self.source_uid,
            "confidence": self.confidence,
        }


class SkillExtractor:
    def __init__(self, min_confidence: float = 0.5) -> None:
        self.min_confidence = min_confidence

    def extract(
        self,
        records: list[TraceRecord],
        skill_type: SkillType | None = None,
    ) -> list[SkillExample]:
        sessions = self._group_by_session(records)
        examples: list[SkillExample] = []
        for session_records in sessions:
            extracted = self._extract_from_session(session_records, skill_type)
            examples.extend(extracted)
        return [e for e in examples if e.confidence >= self.min_confidence]

    def _group_by_session(
        self, records: list[TraceRecord]
    ) -> list[list[TraceRecord]]:
        sessions: dict[str, list[TraceRecord]] = {}
        ungrouped: list[TraceRecord] = []
        for r in records:
            if r.session:
                sessions.setdefault(r.session, []).append(r)
            else:
                ungrouped.append(r)
        result: list[list[TraceRecord]] = list(sessions.values()) if sessions else []
        if ungrouped:
            result.append(ungrouped)
        return result if result else [records]

    def _extract_from_session(
        self,
        records: list[TraceRecord],
        skill_type: SkillType | None,
    ) -> list[SkillExample]:
        examples: list[SkillExample] = []
        target_types = [skill_type] if skill_type else list(SkillType)

        for st in target_types:
            detector = self._get_detector(st)
            for ex in detector(records):
                examples.append(ex)
        return examples

    def _get_detector(self, skill_type: SkillType):
        detectors = {
            SkillType.DEBUG: self._detect_debug,
            SkillType.EDIT: self._detect_edit,
            SkillType.VERIFY: self._detect_verify,
            SkillType.RECOVER: self._detect_recover,
            SkillType.PLAN: self._detect_plan,
        }
        return detectors[skill_type]

    def _detect_debug(self, records: list[TraceRecord]) -> list[SkillExample]:
        examples: list[SkillExample] = []
        for i, rec in enumerate(records):
            confidence = 0.0
            signals_found: list[str] = []

            if rec.thinking:
                thinking_lower = rec.thinking.lower()
                for signal in _DEBUG_SIGNALS:
                    if signal in thinking_lower:
                        signals_found.append(signal)

            content_lower = rec.content.lower()
            for signal in _DEBUG_SIGNALS:
                if signal in content_lower and signal not in signals_found:
                    signals_found.append(signal)

            if rec.role == "tool":
                for signal in _DEBUG_SIGNALS:
                    if signal in content_lower and signal not in signals_found:
                        signals_found.append(signal)

            has_error_then_fix = False
            if signals_found and i + 1 < len(records):
                next_rec = records[i + 1]
                next_tools = [tc.name for tc in next_rec.tool_calls]
                if next_tools or "edit" in next_rec.content.lower() or "fix" in next_rec.content.lower():
                    has_error_then_fix = True

            if signals_found:
                confidence = min(0.4 + len(signals_found) * 0.15, 1.0)
                if has_error_then_fix:
                    confidence = min(confidence + 0.2, 1.0)

                start = max(0, i - 2)
                end = min(len(records), i + 4)
                window = records[start:end]
                messages = [r.to_chat_message() for r in window]

                examples.append(SkillExample(
                    skill_type=SkillType.DEBUG,
                    messages=messages,
                    source_uid=rec.source_uid,
                    session=rec.session,
                    model=rec.model,
                    confidence=confidence,
                    metadata={"signals": signals_found, "has_fix": has_error_then_fix},
                ))

        return self._deduplicate_examples(examples)

    def _detect_edit(self, records: list[TraceRecord]) -> list[SkillExample]:
        examples: list[SkillExample] = []
        for i, rec in enumerate(records):
            edit_tools = [tc for tc in rec.tool_calls if tc.name.lower() in _EDIT_TOOL_NAMES]
            if not edit_tools and "edit" not in rec.content.lower()[:50]:
                content_lower = rec.content.lower()
                if "edit" not in content_lower and "replace" not in content_lower:
                    continue
                edit_tools_found = True
            else:
                edit_tools_found = bool(edit_tools)

            if not edit_tools_found and not edit_tools:
                continue

            confidence = 0.7 if edit_tools else 0.5

            start = max(0, i - 1)
            end = min(len(records), i + 2)
            window = records[start:end]
            messages = [r.to_chat_message() for r in window]

            examples.append(SkillExample(
                skill_type=SkillType.EDIT,
                messages=messages,
                source_uid=rec.source_uid,
                session=rec.session,
                model=rec.model,
                confidence=confidence,
                metadata={"edit_tool_names": [tc.name for tc in edit_tools]},
            ))

        return self._deduplicate_examples(examples)

    def _detect_verify(self, records: list[TraceRecord]) -> list[SkillExample]:
        examples: list[SkillExample] = []
        for i, rec in enumerate(records):
            verify_tools = [
                tc for tc in rec.tool_calls
                if tc.name.lower() in _VERIFY_TOOL_NAMES
            ]
            has_verify_keywords = False
            verify_keywords_found: list[str] = []
            if rec.thinking:
                thinking_lower = rec.thinking.lower()
                for kw in _SKILL_DETECTORS[SkillType.VERIFY]:
                    if kw in thinking_lower:
                        verify_keywords_found.append(kw)
                if verify_keywords_found:
                    has_verify_keywords = True

            content_lower = rec.content.lower()
            for kw in _SKILL_DETECTORS[SkillType.VERIFY]:
                if kw in content_lower and kw not in verify_keywords_found:
                    verify_keywords_found.append(kw)
            if verify_keywords_found and not has_verify_keywords:
                has_verify_keywords = True

            if not verify_tools and not has_verify_keywords:
                continue

            is_verification = False
            if verify_tools:
                for kw in ["test", "check", "verify", "assert", "run"]:
                    cmd_args = verify_tools[0].arguments
                    cmd_str = str(cmd_args).lower() if cmd_args else ""
                    if kw in cmd_str:
                        is_verification = True
                        break

            confidence = 0.8 if (verify_tools and (has_verify_keywords or is_verification)) else 0.5
            if verify_tools and is_verification:
                confidence = 0.9

            start = max(0, i - 1)
            end = min(len(records), i + 2)
            window = records[start:end]
            messages = [r.to_chat_message() for r in window]

            examples.append(SkillExample(
                skill_type=SkillType.VERIFY,
                messages=messages,
                source_uid=rec.source_uid,
                session=rec.session,
                model=rec.model,
                confidence=confidence,
                metadata={
                    "verify_tool_count": len(verify_tools),
                    "is_verification": is_verification,
                    "keywords": verify_keywords_found,
                },
            ))

        return self._deduplicate_examples(examples)

    def _detect_recover(self, records: list[TraceRecord]) -> list[SkillExample]:
        examples: list[SkillExample] = []
        i = 0
        while i < len(records) - 1:
            current = records[i]
            is_error = False
            error_signals: list[str] = []

            content_lower = current.content.lower()
            for signal in ["error", "exception", "failed", "traceback", "crash"]:
                if signal in content_lower:
                    error_signals.append(signal)
                    is_error = True

            if current.thinking:
                thinking_lower = current.thinking.lower()
                for signal in ["error", "exception", "failed", "bug"]:
                    if signal in thinking_lower and signal not in error_signals:
                        error_signals.append(signal)
                        is_error = True

            if current.role == "tool":
                for signal in _DEBUG_SIGNALS:
                    if signal in content_lower and signal not in error_signals:
                        error_signals.append(signal)
                        is_error = True

            if not is_error:
                i += 1
                continue

            recovery_window: list[TraceRecord] = []
            recovery_found = False
            for j in range(i + 1, min(len(records), i + 6)):
                next_rec = records[j]
                recovery_tools = [
                    tc.name for tc in next_rec.tool_calls
                    if tc.name.lower() in _EDIT_TOOL_NAMES
                ]
                recovery_keywords: list[str] = []
                next_lower = next_rec.content.lower()
                for kw in ["fix", "recover", "retry", "handle", "catch", "resolve", "workaround"]:
                    if kw in next_lower:
                        recovery_keywords.append(kw)

                if next_rec.thinking:
                    next_thinking_lower = next_rec.thinking.lower()
                    for kw in ["fix", "recover", "retry", "handle", "resolve"]:
                        if kw in next_thinking_lower and kw not in recovery_keywords:
                            recovery_keywords.append(kw)

                if recovery_tools or recovery_keywords:
                    recovery_found = True
                    recovery_window = records[i:j + 1]
                    break

            if recovery_found:
                confidence = 0.9 if recovery_tools else 0.7
                if len(error_signals) > 1:
                    confidence = min(confidence + 0.05, 1.0)

                messages = [r.to_chat_message() for r in recovery_window]
                examples.append(SkillExample(
                    skill_type=SkillType.RECOVER,
                    messages=messages,
                    source_uid=current.source_uid,
                    session=current.session,
                    model=current.model,
                    confidence=confidence,
                    metadata={
                        "error_signals": error_signals,
                        "has_tool_recovery": bool(recovery_tools),
                    },
                ))
                i = j + 1
            else:
                i += 1

        return examples

    def _detect_plan(self, records: list[TraceRecord]) -> list[SkillExample]:
        examples: list[SkillExample] = []
        for i, rec in enumerate(records):
            planning_signals: list[str] = []
            if rec.thinking:
                for pattern in _PLAN_THINKING_PATTERNS:
                    if re.search(pattern, rec.thinking):
                        planning_signals.append(pattern)

            content_lower = rec.content.lower()
            if any(
                kw in content_lower
                for kw in ["plan:", "approach:", "strategy:", "steps:", "first, i", "let me plan"]
            ):
                planning_signals.append("content_plan_keywords")

            if not planning_signals:
                continue

            confidence = min(0.5 + len(planning_signals) * 0.15, 1.0)

            start = max(0, i - 1)
            end = min(len(records), i + 3)
            window = records[start:end]
            messages = [r.to_chat_message() for r in window]

            examples.append(SkillExample(
                skill_type=SkillType.PLAN,
                messages=messages,
                source_uid=rec.source_uid,
                session=rec.session,
                model=rec.model,
                confidence=confidence,
                metadata={"planning_signals": planning_signals},
            ))

        return self._deduplicate_examples(examples)

    def _deduplicate_examples(self, examples: list[SkillExample]) -> list[SkillExample]:
        seen: set[str] = set()
        unique: list[SkillExample] = []
        for ex in examples:
            key = f"{ex.skill_type.value}:{ex.source_uid}:{len(ex.messages)}:{ex.metadata}"
            if key not in seen:
                seen.add(key)
                unique.append(ex)
        return unique
