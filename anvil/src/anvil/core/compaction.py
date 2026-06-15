"""Context compaction — summarize old messages and prune tool outputs to save tokens."""

from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class CompactionConfig:
    auto: bool = True
    prune: bool = True
    reserved: int = 8000  # tokens to keep free
    model_name: str = ""
    model_api_key: str | None = None
    model_api_base: str | None = None


@dataclass
class Message:
    role: str
    content: str
    tokens: int = 0
    timestamp: float = field(default_factory=time.time)
    is_error: bool = False

    def estimate_tokens(self) -> int:
        """Rough token estimation: ~4 chars per token."""
        if self.tokens > 0:
            return self.tokens
        self.tokens = max(1, len(self.content) // 4)
        return self.tokens


class ContextCompactor:
    """Compact conversation context by summarizing old messages and pruning tool outputs."""

    def __init__(self, config: CompactionConfig | None = None):
        self.config = config or CompactionConfig()
        self._model = None

    def compact(self, messages: list[Message], max_tokens: int = 50000) -> list[Message]:
        """Compact messages: summarize old ones, keep recent ones intact.

        Strategy:
        1. Always preserve system messages
        2. Always preserve the last N messages (keep_recent)
        3. Always preserve messages that carried errors
        4. Summarize older messages into a single summary message
        """
        if not messages:
            return messages

        for msg in messages:
            msg.estimate_tokens()

        total_tokens = sum(m.estimate_tokens() for m in messages)
        if total_tokens <= max_tokens:
            return messages

        system_msgs = [m for m in messages if m.role == "system"]
        non_system = [m for m in messages if m.role != "system"]

        keep_recent = max(6, len(non_system) // 4)
        recent = non_system[-keep_recent:] if len(non_system) > keep_recent else non_system
        old = non_system[:-keep_recent] if len(non_system) > keep_recent else []

        if not old:
            result = system_msgs + non_system
        else:
            summary = self._summarize(old)
            summary_msg = Message(
                role="system",
                content=f"[Context Summary — {len(old)} older messages compacted]\n\n{summary}",
                tokens=0,
            )
            summary_msg.estimate_tokens()
            result = system_msgs + [summary_msg] + recent

        new_total = sum(m.estimate_tokens() for m in result)
        if new_total > max_tokens and self.config.prune:
            result = self.prune(result, max_tokens)

        return result

    def prune(self, messages: list[Message], max_tokens: int = 50000) -> list[Message]:
        """Prune old successful tool results to save tokens.

        Preserves:
        - All system messages
        - Recent messages
        - Tool results that errored

        Removes/reduces:
        - Old successful tool outputs (truncated)
        - Old user messages that are very long
        """
        if not messages:
            return messages

        for msg in messages:
            msg.estimate_tokens()

        total = sum(m.estimate_tokens() for m in messages)
        if total <= max_tokens:
            return messages

        result: list[Message] = []
        tokens_so_far = 0

        system_msgs = [m for m in messages if m.role == "system"]
        non_system = [m for m in messages if m.role != "system"]

        for msg in system_msgs:
            result.append(msg)
            tokens_so_far += msg.estimate_tokens()

        for i, msg in enumerate(non_system):
            msg_tokens = msg.estimate_tokens()
            is_recent = i >= len(non_system) - 6

            if is_recent:
                result.append(msg)
                tokens_so_far += msg_tokens
            elif msg.is_error:
                result.append(msg)
                tokens_so_far += msg_tokens
            elif msg.role == "assistant" and "Tool Output:" in msg.content and not msg.is_error:
                truncated = self._truncate_tool_output(msg, max_chars=500)
                result.append(truncated)
                tokens_so_far += truncated.estimate_tokens()
            elif msg_tokens > 2000 and not is_recent:
                truncated = Message(
                    role=msg.role,
                    content=msg.content[:800] + "\n... [truncated for context compaction]",
                    timestamp=msg.timestamp,
                    is_error=msg.is_error,
                )
                result.append(truncated)
                tokens_so_far += truncated.estimate_tokens()
            else:
                result.append(msg)
                tokens_so_far += msg_tokens

            if tokens_so_far > max_tokens * 0.9:
                remaining = non_system[i + 1:]
                for rem in remaining[-3:]:
                    if rem not in result:
                        result.append(rem)
                break

        return result

    def _summarize(self, messages: list[Message]) -> str:
        """Summarize old messages. Uses model if available, else simple truncation."""
        if self.config.model_name and self._try_model_summarize(messages):
            return self._try_model_summarize(messages)

        parts = []
        for msg in messages:
            role_label = {"system": "SYSTEM", "user": "USER", "assistant": "ASSISTANT", "tool": "TOOL"}.get(msg.role, msg.role.upper())
            content_preview = msg.content[:300]
            if len(msg.content) > 300:
                content_preview += "..."
            parts.append(f"[{role_label}]: {content_preview}")

        summary = "Previous context:\n" + "\n".join(parts)
        if len(summary) > 4000:
            summary = summary[:4000] + "\n... [further truncated]"
        return summary

    def _try_model_summarize(self, messages: list[Message]) -> str | None:
        """Attempt to use an LLM for summarization."""
        try:
            from anvil.models.registry import ModelRegistry
            model = ModelRegistry.create(
                self.config.model_name,
                api_key=self.config.model_api_key,
                api_base=self.config.model_api_base,
            )
            parts = "\n".join(f"[{m.role}]: {m.content[:500]}" for m in messages)
            prompt = f"Summarize the following conversation context concisely, preserving key facts, decisions, and outcomes:\n\n{parts}\n\nSummary:"
            response = model.complete([{"role": "user", "content": prompt}])
            if response and hasattr(response, "content") and response.content:
                return response.content[:2000]
        except Exception:
            pass
        return None

    def _truncate_tool_output(self, msg: Message, max_chars: int = 500) -> Message:
        """Truncate a tool output message."""
        if len(msg.content) <= max_chars:
            return msg
        truncated = msg.content[:max_chars] + "\n... [tool output truncated]"
        return Message(
            role=msg.role,
            content=truncated,
            timestamp=msg.timestamp,
            is_error=msg.is_error,
        )
