"""Unit tests for token counting and cost estimation."""

from __future__ import annotations


from agent_telemetry.token_tracker import (
    CostBreakdown,
    PRICING,
    count_tokens,
    estimate_cost,
    format_cost_table,
)


class TestCountTokens:
    def test_basic_token_count(self):
        result = count_tokens("Hello, world!", model="gpt-4")
        assert isinstance(result, int)
        assert result > 0

    def test_empty_string(self):
        result = count_tokens("", model="gpt-4")
        assert result == 0

    def test_unknown_model_uses_default(self):
        result = count_tokens("Hello, world!", model="unknown-model-xyz")
        assert result > 0

    def test_different_models_same_text(self):
        text = "The quick brown fox jumps over the lazy dog."
        gpt4_count = count_tokens(text, model="gpt-4")
        gpt4o_count = count_tokens(text, model="gpt-4o")
        assert gpt4_count > 0
        assert gpt4o_count > 0

    def test_longer_text_more_tokens(self):
        short = "Hi"
        long = "This is a much longer sentence that should contain more tokens than the short one."
        assert count_tokens(long, model="gpt-4") > count_tokens(short, model="gpt-4")


class TestEstimateCost:
    def test_basic_cost_estimation(self):
        result = estimate_cost(1000, 500, model="gpt-4")
        assert isinstance(result, CostBreakdown)
        assert result.input_tokens == 1000
        assert result.output_tokens == 500
        assert result.total_cost > 0

    def test_gpt4_pricing(self):
        pricing = PRICING["gpt-4"]
        result = estimate_cost(1_000_000, 1_000_000, model="gpt-4")
        assert abs(result.input_cost - pricing.input_per_million) < 0.01
        assert abs(result.output_cost - pricing.output_per_million) < 0.01

    def test_claude_35_sonnet_pricing(self):
        result = estimate_cost(1_000_000, 1_000_000, model="claude-3.5-sonnet")
        pricing = PRICING["claude-3.5-sonnet"]
        assert abs(result.input_cost - pricing.input_per_million) < 0.01
        assert abs(result.output_cost - pricing.output_per_million) < 0.01

    def test_claude_3_opus_pricing(self):
        result = estimate_cost(100_000, 50_000, model="claude-3-opus")
        assert result.input_cost > 0
        assert result.output_cost > 0
        assert result.output_cost > result.input_cost  # Opus output is 5x input

    def test_gpt4o_pricing(self):
        result = estimate_cost(100_000, 100_000, model="gpt-4o")
        assert result.input_cost > 0
        assert result.output_cost > 0

    def test_qwen3_coder_pricing(self):
        result = estimate_cost(100_000, 100_000, model="qwen3-coder")
        assert result.input_cost > 0
        assert result.output_cost > 0

    def test_cache_read_cost(self):
        no_cache = estimate_cost(1_000_000, 0, model="claude-3.5-sonnet", cache_read=0, cache_creation=0)
        with_cache = estimate_cost(1_000_000, 0, model="claude-3.5-sonnet", cache_read=1_000_000, cache_creation=0)
        assert with_cache.cache_read_cost > 0
        assert with_cache.total_cost > no_cache.total_cost

    def test_cache_creation_cost(self):
        result = estimate_cost(1_000_000, 0, model="claude-3.5-sonnet", cache_read=0, cache_creation=500_000)
        assert result.cache_creation_cost > 0
        assert result.cache_cost > 0

    def test_unknown_model_falls_back_to_gpt4(self):
        result = estimate_cost(1000, 500, model="totally-unknown-model")
        gpt4_result = estimate_cost(1000, 500, model="gpt-4")
        assert abs(result.total_cost - gpt4_result.total_cost) < 0.0001

    def test_zero_tokens(self):
        result = estimate_cost(0, 0, model="gpt-4")
        assert result.total_cost == 0.0
        assert result.input_cost == 0.0
        assert result.output_cost == 0.0

    def test_cost_breakdown_str(self):
        result = estimate_cost(1000, 500, model="gpt-4")
        s = str(result)
        assert "gpt-4" in s
        assert "$" in s
        assert "Input tokens" in s
        assert "Total" in s


class TestModelPricing:
    def test_all_models_have_pricing(self):
        expected_models = ["claude-3.5-sonnet", "claude-3-opus", "claude-3-haiku", "gpt-4", "gpt-4o", "gpt-4o-mini", "qwen3-coder"]
        for model in expected_models:
            assert model in PRICING

    def test_pricing_per_token_conversion(self):
        pricing = PRICING["gpt-4"]
        assert pricing.input_per_token == pricing.input_per_million / 1_000_000
        assert pricing.output_per_token == pricing.output_per_million / 1_000_000

    def test_output_more_expensive_than_input(self):
        for model_name, pricing in PRICING.items():
            assert pricing.output_per_million >= pricing.input_per_million, (
                f"{model_name}: output ({pricing.output_per_million}) should be >= input ({pricing.input_per_million})"
            )

    def test_cache_read_cheaper_than_input(self):
        cache_models = ["claude-3.5-sonnet", "claude-3-opus", "claude-3-haiku", "gpt-4o", "gpt-4o-mini", "qwen3-coder"]
        for model_name in cache_models:
            pricing = PRICING[model_name]
            if pricing.cache_read_per_million > 0:
                assert pricing.cache_read_per_million < pricing.input_per_million, (
                    f"{model_name}: cache read ({pricing.cache_read_per_million}) should be < input ({pricing.input_per_million})"
                )


class TestFormatCostTable:
    def test_empty_breakdowns(self):
        result = format_cost_table([])
        assert "No data" in result

    def test_single_breakdown(self):
        bd = estimate_cost(1000, 500, model="gpt-4")
        result = format_cost_table([bd])
        assert "gpt-4" in result
        assert "TOTAL" in result

    def test_multiple_breakdowns(self):
        bds = [
            estimate_cost(1000, 500, model="gpt-4"),
            estimate_cost(2000, 1000, model="claude-3.5-sonnet"),
        ]
        result = format_cost_table(bds)
        assert "gpt-4" in result
        assert "claude-3.5-sonnet" in result
        assert "TOTAL" in result
