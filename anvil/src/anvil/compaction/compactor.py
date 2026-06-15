"""Context compaction — reduce token count by pruning and summarizing messages."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CompactResult:
    """Result of a compaction operation."""
    original_count: int
    compacted_count: int
    pruned_indices: list[int] = field(default_factory=list)
    summary: str = ""
    tokens_saved: int = 0


class ContextCompactor:
    """Compact a list of messages by pruning and summarizing.

    Strategies:
      - Prune old tool results past a retention window.
      - Preserve system messages, recent messages, and error results.
      - Reserve a token buffer so we never exceed context limits.
    """

    def __init__(
        self,
        max_context_tokens: int = 8192,
        reserved_buffer: int = 2048,
        recent_window: int = 4,
    ) -> None:
        self.max_context_tokens = max_context_tokens
        self.reserved_buffer = reserved_buffer
        self.recent_window = recent_window

    def estimate_tokens(self, messages: list[dict]) -> int:
        """Estimate token count for a list of messages.

        Uses a simple heuristic: ~4 chars per token.
        """
        total_chars = sum(len(m.get("content", "")) for m in messages)
        return total_chars // 4

    def compact(self, messages: list[dict], threshold: int | None = None) -> CompactResult:
        """Compact messages to fit within the token budget.

        Returns a CompactResult with metadata about what was pruned.
        """
        if not messages:
            return CompactResult(original_count=0, compacted_count=0)

        original_count = len(messages)
        original_tokens = self.estimate_tokens(messages)
        target = threshold or (self.max_context_tokens - self.reserved_buffer)

        if original_tokens <= target:
            return CompactResult(
                original_count=original_count,
                compacted_count=original_count,
                pruned_indices=[],
                summary="No compaction needed",
                tokens_saved=0,
            )

        preserve_indices = self._compute_preserve(messages)
        pruned_indices = self._compute_prune(messages, preserve_indices)
        compacted = [m for i, m in enumerate(messages) if i not in pruned_indices]
        compacted_tokens = self.estimate_tokens(compacted)

        return CompactResult(
            original_count=original_count,
            compacted_count=len(compacted),
            pruned_indices=pruned_indices,
            summary=f"Pruned {len(pruned_indices)} messages",
            tokens_saved=original_tokens - compacted_tokens,
        )

    def _compute_preserve(self, messages: list[dict]) -> set[int]:
        """Compute indices of messages that must be preserved.

        Always preserve: system messages, recent messages, error messages.
        """
        preserve = set()
        total = len(messages)

        for i, msg in enumerate(messages):
            role = msg.get("role", "")
            content = msg.get("content", "")

            if role == "system":
                preserve.add(i)

            if i >= total - self.recent_window:
                preserve.add(i)

            if "error" in content.lower() or "failed" in content.lower():
                preserve.add(i)

        return preserve

    def _compute_prune(self, messages: list[dict], preserve: set[int]) -> list[int]:
        """Determine which messages to prune, excluding preserve set."""
        prunable = []
        total = len(messages)
        target_tokens = self.max_context_tokens - self.reserved_buffer

        current_tokens = self.estimate_tokens(messages)
        if current_tokens <= target_tokens:
            return []

        for i, msg in enumerate(messages):
            if i in preserve:
                continue

            role = msg.get("role", "")
            content = msg.get("content", "")

            if role == "tool" and i < total - self.recent_window:
                prunable.append(i)
                current_tokens -= len(content) // 4
                if current_tokens <= target_tokens:
                    break

        if current_tokens > target_tokens:
            for i, msg in enumerate(messages):
                if i in preserve or i in prunable:
                    continue
                prunable.append(i)
                current_tokens -= len(msg.get("content", "")) // 4
                if current_tokens <= target_tokens:
                    break

        return sorted(prunable)

    def prune_old_tool_results(self, messages: list[dict], keep_last: int = 2) -> list[dict]:
        """Remove old tool results, keeping only the most recent ones."""
        if len(messages) <= keep_last:
            return list(messages)

        tool_indices = [(i, m) for i, m in enumerate(messages) if m.get("role") == "tool"]
        if len(tool_indices) <= keep_last:
            return list(messages)

        prunable = {idx for idx, _ in tool_indices[:-keep_last]}
        recent = {len(messages) - 1 - i for i in range(self.recent_window)}
        system = {i for i, m in enumerate(messages) if m.get("role") == "system"}
        preserve = recent | system

        prune = prunable - preserve
        return [m for i, m in enumerate(messages) if i not in prune]

    def should_compact(self, messages: list[dict]) -> bool:
        """Check if messages exceed the threshold for auto-compaction."""
        tokens = self.estimate_tokens(messages)
        threshold = self.max_context_tokens - self.reserved_buffer
        return tokens > threshold
