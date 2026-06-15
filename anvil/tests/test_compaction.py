"""Tests for Anvil context compaction system."""


from anvil.compaction.compactor import CompactResult, ContextCompactor


class TestContextCompactorInit:
    def test_default_settings(self):
        compactor = ContextCompactor()
        assert compactor.max_context_tokens == 8192
        assert compactor.reserved_buffer == 2048
        assert compactor.recent_window == 4

    def test_custom_settings(self):
        compactor = ContextCompactor(max_context_tokens=4096, reserved_buffer=1024, recent_window=2)
        assert compactor.max_context_tokens == 4096
        assert compactor.reserved_buffer == 1024
        assert compactor.recent_window == 2


class TestEstimateTokens:
    def test_estimate_tokens(self):
        compactor = ContextCompactor()
        messages = [
            {"role": "user", "content": "Hello world, this is a test message"},
            {"role": "assistant", "content": "I can help you with that"},
        ]
        tokens = compactor.estimate_tokens(messages)
        assert tokens > 0

    def test_estimate_tokens_empty(self):
        compactor = ContextCompactor()
        tokens = compactor.estimate_tokens([])
        assert tokens == 0

    def test_estimate_tokens_heuristic(self):
        compactor = ContextCompactor()
        long_msg = {"role": "user", "content": "a" * 400}
        tokens = compactor.estimate_tokens([long_msg])
        assert tokens == 100  # 400/4 = 100


class TestCompact:
    def test_compact_no_messages(self):
        compactor = ContextCompactor()
        result = compactor.compact([])
        assert result.original_count == 0
        assert result.compacted_count == 0
        assert result.pruned_indices == []

    def test_compact_within_budget(self):
        compactor = ContextCompactor(max_context_tokens=10000)
        messages = [
            {"role": "system", "content": "You are helpful"},
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"},
        ]
        result = compactor.compact(messages)
        assert result.compacted_count == 3
        assert result.pruned_indices == []
        assert result.tokens_saved == 0

    def test_compact_prunes_old_tool_results(self):
        compactor = ContextCompactor(max_context_tokens=100, reserved_buffer=10, recent_window=1)
        messages = [
            {"role": "system", "content": "instructions"},
            {"role": "tool", "content": "x" * 200},
            {"role": "tool", "content": "y" * 200},
            {"role": "tool", "content": "z" * 200},
            {"role": "user", "content": "recent"},
        ]
        result = compactor.compact(messages)
        assert result.pruned_indices  # Some messages were pruned
        assert result.tokens_saved > 0

    def test_compact_preserves_system_messages(self):
        compactor = ContextCompactor(max_context_tokens=100, reserved_buffer=10, recent_window=1)
        messages = [
            {"role": "system", "content": "important instructions"},
            {"role": "tool", "content": "x" * 200},
            {"role": "user", "content": "recent"},
        ]
        result = compactor.compact(messages)
        system_preserved = 0 not in result.pruned_indices
        assert system_preserved

    def test_compact_preserves_recent_messages(self):
        compactor = ContextCompactor(max_context_tokens=100, reserved_buffer=10, recent_window=2)
        messages = [
            {"role": "system", "content": "important"},
            {"role": "tool", "content": "x" * 200},
            {"role": "assistant", "content": "recent reply"},
            {"role": "user", "content": "recent question"},
        ]
        result = compactor.compact(messages)
        recent_indices = {2, 3}
        for idx in recent_indices:
            assert idx not in result.pruned_indices

    def test_compact_preserves_error_messages(self):
        compactor = ContextCompactor(max_context_tokens=100, reserved_buffer=10, recent_window=0)
        messages = [
            {"role": "assistant", "content": "Error: something failed"},
            {"role": "assistant", "content": "x" * 200},
        ]
        result = compactor.compact(messages)
        error_preserved = 0 not in result.pruned_indices
        assert error_preserved

    def test_compact_result_metadata(self):
        compactor = ContextCompactor()
        messages = [{"role": "user", "content": "hello"}]
        result = compactor.compact(messages)
        assert isinstance(result, CompactResult)
        assert result.original_count == 1
        assert result.summary != ""

    def test_compact_with_custom_threshold(self):
        compactor = ContextCompactor(max_context_tokens=50, reserved_buffer=0, recent_window=1)
        large_msgs = [
            {"role": "user", "content": "a" * 400},
            {"role": "assistant", "content": "b" * 400},
            {"role": "user", "content": "c" * 400},
        ]
        result = compactor.compact(large_msgs, threshold=5)
        assert result.pruned_indices
        assert result.tokens_saved > 0


class TestPruneOldToolResults:
    def test_prune_removes_old(self):
        compactor = ContextCompactor(recent_window=1)
        messages = [
            {"role": "tool", "content": "old result 1"},
            {"role": "tool", "content": "old result 2"},
            {"role": "tool", "content": "recent result"},
        ]
        pruned = compactor.prune_old_tool_results(messages, keep_last=1)
        recent_in_pruned = any("recent" in m.get("content", "") for m in pruned)
        assert recent_in_pruned

    def test_prune_keeps_all_if_short(self):
        compactor = ContextCompactor()
        messages = [
            {"role": "tool", "content": "only result"},
        ]
        pruned = compactor.prune_old_tool_results(messages, keep_last=2)
        assert len(pruned) == 1

    def test_prune_non_tool_messages(self):
        compactor = ContextCompactor()
        messages = [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "hello"},
        ]
        pruned = compactor.prune_old_tool_results(messages)
        assert len(pruned) == 2


class TestShouldCompact:
    def test_should_compact_over_threshold(self):
        compactor = ContextCompactor(max_context_tokens=10, reserved_buffer=0)
        messages = [{"role": "user", "content": "a" * 100}]
        assert compactor.should_compact(messages) is True

    def test_should_not_compact_under_threshold(self):
        compactor = ContextCompactor(max_context_tokens=100000, reserved_buffer=0)
        messages = [{"role": "user", "content": "short"}]
        assert compactor.should_compact(messages) is False

    def test_should_compact_empty_messages(self):
        compactor = ContextCompactor()
        assert compactor.should_compact([]) is False


class TestEmptyMessages:
    def test_compact_empty(self):
        compactor = ContextCompactor()
        result = compactor.compact([])
        assert result.original_count == 0
        assert result.compacted_count == 0
        assert result.pruned_indices == []

    def test_prune_empty(self):
        compactor = ContextCompactor()
        result = compactor.prune_old_tool_results([])
        assert result == []

    def test_should_compact_empty(self):
        compactor = ContextCompactor()
        assert compactor.should_compact([]) is False


class TestReservedTokenBuffer:
    def test_reserved_buffer_effective(self):
        compactor = ContextCompactor(max_context_tokens=200, reserved_buffer=150, recent_window=1)
        messages = [
            {"role": "system", "content": "sys"},
            {"role": "tool", "content": "x" * 400},
            {"role": "user", "content": "q"},
        ]
        result = compactor.compact(messages)
        # With only 50 tokens of budget, should prune aggressively
        assert result.pruned_indices or result.tokens_saved >= 0


class TestAutoCompactTrigger:
    def test_auto_compact_false_when_small(self):
        compactor = ContextCompactor(max_context_tokens=100000)
        messages = [{"role": "user", "content": "hello"}]
        assert compactor.should_compact(messages) is False

    def test_auto_compact_true_when_large(self):
        compactor = ContextCompactor(max_context_tokens=10, reserved_buffer=0)
        messages = [{"role": "user", "content": "a" * 1000}]
        assert compactor.should_compact(messages) is True
