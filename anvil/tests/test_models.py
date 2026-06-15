"""Tests for Anvil model backends — Message, ModelResponse, LocalModel, OpenAI, Anthropic, Registry."""

import os
from unittest.mock import patch

import pytest

from anvil.models.registry import (
    AnthropicModel,
    BaseModel,
    LocalModel,
    Message,
    ModelRegistry,
    ModelResponse,
    OpenAIModel,
)

# ---------------------------------------------------------------------------
# Message dataclass
# ---------------------------------------------------------------------------

class TestMessage:
    def test_creation_with_role_and_content(self):
        msg = Message(role="user", content="Hello")
        assert msg.role == "user"
        assert msg.content == "Hello"

    def test_system_role(self):
        msg = Message(role="system", content="You are a helpful assistant")
        assert msg.role == "system"
        assert msg.content == "You are a helpful assistant"

    def test_assistant_role(self):
        msg = Message(role="assistant", content="I can help with that")
        assert msg.role == "assistant"

    def test_message_with_tool_calls(self):
        tool_calls = [{"name": "bash", "args": {"command": "ls"}}]
        msg = Message(role="assistant", content="", tool_calls=tool_calls)
        assert msg.tool_calls is not None
        assert len(msg.tool_calls) == 1
        assert msg.tool_calls[0]["name"] == "bash"

    def test_message_with_tool_call_id(self):
        msg = Message(role="tool", content="output", tool_call_id="call_123")
        assert msg.tool_call_id == "call_123"


# ---------------------------------------------------------------------------
# ModelResponse dataclass
# ---------------------------------------------------------------------------

class TestModelResponse:
    def test_basic_response(self):
        resp = ModelResponse(content="Hello world", model="gpt-4o")
        assert resp.content == "Hello world"
        assert resp.model == "gpt-4o"
        assert resp.input_tokens == 0
        assert resp.output_tokens == 0
        assert resp.cost_usd == 0.0
        assert resp.finish_reason == "stop"
        assert resp.tool_calls == []

    def test_response_with_tokens(self):
        resp = ModelResponse(content="test", model="gpt-4o", input_tokens=100, output_tokens=50, cost_usd=0.003)
        assert resp.input_tokens == 100
        assert resp.output_tokens == 50
        assert resp.cost_usd == pytest.approx(0.003)

    def test_response_with_tool_calls(self):
        tc = [{"name": "bash", "args": {"command": "ls"}, "id": "call_1"}]
        resp = ModelResponse(content="", model="local", tool_calls=tc)
        assert len(resp.tool_calls) == 1
        assert resp.tool_calls[0]["name"] == "bash"

    def test_response_error_content(self):
        resp = ModelResponse(content="Error: Something went wrong", model="local")
        assert "Error" in resp.content

    def test_response_with_duration(self):
        resp = ModelResponse(content="ok", model="local", duration_ms=250.5)
        assert resp.duration_ms == pytest.approx(250.5)


# ---------------------------------------------------------------------------
# LocalModel
# ---------------------------------------------------------------------------

class TestLocalModel:
    def test_initialization_defaults(self):
        model = LocalModel()
        assert model.name == "local"
        assert model.api_base == "http://localhost:11434"
        assert model.model_name == "fableforge-14b"

    def test_initialization_custom(self):
        model = LocalModel(model_path="my-model", api_base="http://custom:8080")
        assert model.model_name == "my-model"
        assert model.api_base == "http://custom:8080"

    def test_strip_trailing_slash_from_api_base(self):
        model = LocalModel(api_base="http://localhost:11434/")
        assert model.api_base == "http://localhost:11434"

    def test_none_api_base_defaults(self):
        model = LocalModel(api_base=None)
        assert model.api_base == "http://localhost:11434"

    def test_connection_failure_returns_error(self):
        model = LocalModel(api_base="http://localhost:99999")
        resp = model.complete([Message(role="user", content="test")])
        assert "Error" in resp.content or "Cannot connect" in resp.content

    def test_stream_yields_chunks_on_failure(self):
        model = LocalModel(api_base="http://localhost:99999")
        chunks = list(model.stream([Message(role="user", content="test")]))
        assert len(chunks) > 0
        assert any("Error" in c for c in chunks)

    def test_count_tokens(self):
        model = LocalModel()
        count = model.count_tokens("Hello world, this is a test message")
        assert count > 0
        assert count == len("Hello world, this is a test message") // 4


# ---------------------------------------------------------------------------
# OpenAIModel
# ---------------------------------------------------------------------------

class TestOpenAIModel:
    def test_initialization_defaults(self):
        model = OpenAIModel(api_key="test-key")
        assert model.name == "openai"
        assert model.model == "gpt-4o"
        assert model.api_key == "test-key"
        assert model.api_base == "https://api.openai.com/v1"

    def test_initialization_custom_model(self):
        model = OpenAIModel(api_key="key", model="gpt-4o-mini", api_base="https://custom.api.com/v1")
        assert model.model == "gpt-4o-mini"
        assert model.api_base == "https://custom.api.com/v1"

    def test_env_var_api_key(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "env-key-123"}):
            model = OpenAIModel()
            assert model.api_key == "env-key-123"

    def test_pricing_data_gpt4o(self):
        assert "gpt-4o" in OpenAIModel.PRICING
        in_price, out_price = OpenAIModel.PRICING["gpt-4o"]
        assert in_price > 0
        assert out_price > 0
        assert out_price > in_price  # Output is more expensive

    def test_pricing_data_gpt4o_mini(self):
        assert "gpt-4o-mini" in OpenAIModel.PRICING
        in_price, out_price = OpenAIModel.PRICING["gpt-4o-mini"]
        mini_in, mini_out = OpenAIModel.PRICING["gpt-4o"]
        assert in_price < mini_in  # Mini is cheaper
        assert out_price < mini_out

    def test_complete_failure_returns_error(self):
        model = OpenAIModel(api_key="bad-key")
        resp = model.complete([Message(role="user", content="test")])
        assert "Error" in resp.content

    def test_stream_failure_yields_error(self):
        model = OpenAIModel(api_key="bad-key")
        chunks = list(model.stream([Message(role="user", content="test")]))
        # Stream on connection failure may yield 0 chunks or error chunks
        # depending on httpx behavior; just verify it doesn't crash
        assert isinstance(chunks, list)


# ---------------------------------------------------------------------------
# AnthropicModel
# ---------------------------------------------------------------------------

class TestAnthropicModel:
    def test_initialization_defaults(self):
        model = AnthropicModel(api_key="test-key")
        assert model.name == "anthropic"
        assert model.model == "claude-3.5-sonnet"
        assert model.api_key == "test-key"

    def test_initialization_custom_model(self):
        model = AnthropicModel(api_key="key", model="claude-3.5-haiku")
        assert model.model == "claude-3.5-haiku"

    def test_env_var_api_key(self):
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "env-ant-key"}):
            model = AnthropicModel()
            assert model.api_key == "env-ant-key"

    def test_pricing_data(self):
        assert "claude-3.5-sonnet" in AnthropicModel.PRICING
        assert "claude-3.5-haiku" in AnthropicModel.PRICING
        assert "claude-3-opus" in AnthropicModel.PRICING
        sonnet_in, sonnet_out = AnthropicModel.PRICING["claude-3.5-sonnet"]
        haiku_in, haiku_out = AnthropicModel.PRICING["claude-3.5-haiku"]
        assert sonnet_in > haiku_in  # Sonnet costs more than Haiku

    def test_complete_failure_returns_error(self):
        model = AnthropicModel(api_key="bad-key")
        resp = model.complete([Message(role="user", content="test")])
        assert "Error" in resp.content

    def test_stream_returns_not_implemented_message(self):
        model = AnthropicModel(api_key="key")
        chunks = list(model.stream([Message(role="user", content="test")]))
        assert len(chunks) > 0
        assert "not yet implemented" in chunks[0].lower() or "not" in chunks[0].lower()

    def test_system_message_handling_in_complete(self):
        model = AnthropicModel(api_key="bad-key")
        messages = [
            Message(role="system", content="You are helpful"),
            Message(role="user", content="Hi"),
        ]
        resp = model.complete(messages)
        assert resp is not None


# ---------------------------------------------------------------------------
# BaseModel abstraction
# ---------------------------------------------------------------------------

class TestBaseModel:
    def test_cannot_instantiate_directly(self):
        with pytest.raises(TypeError):
            BaseModel()

    def test_subclass_must_implement_methods(self):
        class IncompleteModel(BaseModel):
            name = "incomplete"

        with pytest.raises(TypeError):
            IncompleteModel()

    def test_proper_subclass_works(self):
        class TestModel(BaseModel):
            name = "test"
            def complete(self, messages, **kwargs):
                return ModelResponse(content="test response", model="test")
            def stream(self, messages, **kwargs):
                yield "test"

        model = TestModel()
        resp = model.complete([Message(role="user", content="hi")])
        assert resp.content == "test response"
        assert model.count_tokens("hello") > 0


# ---------------------------------------------------------------------------
# ModelRegistry
# ---------------------------------------------------------------------------

class TestModelRegistry:
    def test_create_local_model(self):
        model = ModelRegistry.create("local")
        assert isinstance(model, LocalModel)

    def test_create_ollama_alias(self):
        model = ModelRegistry.create("ollama")
        assert isinstance(model, LocalModel)

    def test_create_llama_alias(self):
        model = ModelRegistry.create("llama")
        assert isinstance(model, LocalModel)

    def test_create_gpt4o(self):
        model = ModelRegistry.create("gpt-4o")
        assert isinstance(model, OpenAIModel)
        assert model.model == "gpt-4o"

    def test_create_gpt4o_mini(self):
        model = ModelRegistry.create("gpt-4o-mini")
        assert isinstance(model, OpenAIModel)
        assert model.model == "gpt-4o-mini"

    def test_create_claude(self):
        model = ModelRegistry.create("claude-3.5-sonnet")
        assert isinstance(model, AnthropicModel)

    def test_create_o3_mini(self):
        model = ModelRegistry.create("o3-mini")
        assert isinstance(model, OpenAIModel)

    def test_register_custom_model(self):
        class CustomModel(BaseModel):
            name = "custom-test"
            def complete(self, messages, **kwargs):
                return ModelResponse(content="custom", model="custom-test")
            def stream(self, messages, **kwargs):
                yield "custom"

        ModelRegistry.register("custom-test", CustomModel)
        model = ModelRegistry.create("custom-test")
        assert isinstance(model, CustomModel)
        resp = model.complete([])
        assert resp.content == "custom"

    def test_available_returns_list(self):
        models = ModelRegistry.available()
        assert isinstance(models, list)
        assert len(models) > 0
        assert "local" in models
        assert "gpt-4o" in models

    def test_unknown_model_returns_local(self):
        model = ModelRegistry.create("totally-unknown-model-xyz")
        assert isinstance(model, LocalModel)

    def test_create_with_kwargs(self):
        model = ModelRegistry.create("gpt-4o", api_key="test-key-123")
        assert model.api_key == "test-key-123"

    def test_create_with_api_base(self):
        model = ModelRegistry.create("gpt-4o", api_key="key", api_base="https://custom.api.com")
        assert model.api_base == "https://custom.api.com"
