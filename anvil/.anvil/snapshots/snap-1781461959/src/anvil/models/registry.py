"""Model backends — local (llama.cpp/ollama) and API (OpenAI/Anthropic)."""

from __future__ import annotations

import json
import time
from abc import ABC, abstractmethod
from collections.abc import Generator
from dataclasses import dataclass, field

import httpx


@dataclass
class Message:
    role: str
    content: str
    tool_calls: list[dict] | None = None
    tool_call_id: str | None = None


@dataclass
class ModelResponse:
    content: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    duration_ms: float = 0.0
    cost_usd: float = 0.0
    tool_calls: list[dict] = field(default_factory=list)
    finish_reason: str = "stop"


class BaseModel(ABC):
    name: str = "base"

    @abstractmethod
    def complete(self, messages: list[Message], **kwargs) -> ModelResponse:
        ...

    @abstractmethod
    def stream(self, messages: list[Message], **kwargs) -> Generator[str, None, None]:
        ...

    def count_tokens(self, text: str) -> int:
        return len(text) // 4


class LocalModel(BaseModel):
    name = "local"

    def __init__(self, model_path: str | None = None, api_base: str = "http://localhost:11434"):
        self.model_path = model_path
        self.api_base = (api_base or "http://localhost:11434").rstrip("/")
        self.model_name = model_path or "fableforge-14b"
        self.client = httpx.Client(timeout=120.0)

    def complete(self, messages: list[Message], **kwargs) -> ModelResponse:
        start = time.time()
        payload = {
            "model": self.model_name,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": False,
            "options": {
                "temperature": kwargs.get("temperature", 0.2),
                "num_predict": kwargs.get("max_tokens", 4096),
            },
        }
        try:
            resp = self.client.post(f"{self.api_base}/api/chat", json=payload)
            resp.raise_for_status()
            data = resp.json()
            duration = (time.time() - start) * 1000
            content = data.get("message", {}).get("content", "")
            eval_count = data.get("eval_count", 0)
            prompt_count = data.get("prompt_eval_count", 0)
            return ModelResponse(
                content=content,
                model=self.model_name,
                input_tokens=prompt_count,
                output_tokens=eval_count,
                duration_ms=duration,
                cost_usd=0.0,
            )
        except httpx.ConnectError:
            return ModelResponse(
                content="Error: Cannot connect to local model server. Start ollama or llama.cpp server.",
                model=self.model_name, duration_ms=(time.time() - start) * 1000,
            )
        except Exception as e:
            return ModelResponse(
                content=f"Error: {e}", model=self.model_name,
                duration_ms=(time.time() - start) * 1000,
            )

    def stream(self, messages: list[Message], **kwargs) -> Generator[str, None, None]:
        payload = {
            "model": self.model_name,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": True,
        }
        try:
            with self.client.stream("POST", f"{self.api_base}/api/chat", json=payload) as resp:
                for line in resp.iter_lines():
                    if line:
                        data = json.loads(line)
                        if "message" in data:
                            chunk = data["message"].get("content", "")
                            if chunk:
                                yield chunk
        except Exception as e:
            yield f"Error: {e}"


class OpenAIModel(BaseModel):
    name = "openai"

    PRICING = {
        "gpt-4o": (2.50 / 1_000_000, 10.00 / 1_000_000),
        "gpt-4o-mini": (0.15 / 1_000_000, 0.60 / 1_000_000),
        "gpt-4-turbo": (10.00 / 1_000_000, 30.00 / 1_000_000),
        "o3-mini": (1.10 / 1_000_000, 4.40 / 1_000_000),
        "o4-mini": (1.10 / 1_000_000, 4.40 / 1_000_000),
    }

    def __init__(self, api_key: str | None = None, model: str = "gpt-4o", api_base: str | None = None):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self.model = model
        self.api_base = api_base or "https://api.openai.com/v1"
        self.client = httpx.Client(timeout=120.0, headers={
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        })

    def complete(self, messages: list[Message], **kwargs) -> ModelResponse:
        start = time.time()
        payload = {
            "model": self.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "max_tokens": kwargs.get("max_tokens", 4096),
            "temperature": kwargs.get("temperature", 0.2),
        }
        try:
            resp = self.client.post(f"{self.api_base}/chat/completions", json=payload)
            resp.raise_for_status()
            data = resp.json()
            choice = data["choices"][0]
            usage = data.get("usage", {})
            duration = (time.time() - start) * 1000
            in_tokens = usage.get("prompt_tokens", 0)
            out_tokens = usage.get("completion_tokens", 0)
            in_price, out_price = self.PRICING.get(self.model, (2.50 / 1_000_000, 10.00 / 1_000_000))
            return ModelResponse(
                content=choice["message"]["content"],
                model=self.model,
                input_tokens=in_tokens,
                output_tokens=out_tokens,
                duration_ms=duration,
                cost_usd=(in_tokens * in_price) + (out_tokens * out_price),
                finish_reason=choice.get("finish_reason", "stop"),
            )
        except Exception as e:
            return ModelResponse(
                content=f"Error: {e}", model=self.model,
                duration_ms=(time.time() - start) * 1000,
            )

    def stream(self, messages: list[Message], **kwargs) -> Generator[str, None, None]:
        payload = {
            "model": self.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": True,
            "max_tokens": kwargs.get("max_tokens", 4096),
            "temperature": kwargs.get("temperature", 0.2),
        }
        try:
            with self.client.stream("POST", f"{self.api_base}/chat/completions", json=payload) as resp:
                for line in resp.iter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str == "[DONE]":
                            break
                        data = json.loads(data_str)
                        delta = data.get("choices", [{}])[0].get("delta", {})
                        if "content" in delta:
                            yield delta["content"]
        except Exception as e:
            yield f"Error: {e}"


class AnthropicModel(BaseModel):
    name = "anthropic"

    PRICING = {
        "claude-3.5-sonnet": (3.00 / 1_000_000, 15.00 / 1_000_000),
        "claude-3.5-haiku": (0.80 / 1_000_000, 4.00 / 1_000_000),
        "claude-3-opus": (15.00 / 1_000_000, 75.00 / 1_000_000),
    }

    def __init__(self, api_key: str | None = None, model: str = "claude-3.5-sonnet"):
        import os
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self.model = model
        self.client = httpx.Client(timeout=120.0, headers={
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        })

    def complete(self, messages: list[Message], **kwargs) -> ModelResponse:
        start = time.time()
        system_msg = ""
        chat_messages = []
        for m in messages:
            if m.role == "system":
                system_msg = m.content
            else:
                chat_messages.append({"role": m.role, "content": m.content})
        payload = {
            "model": self.model,
            "messages": chat_messages,
            "max_tokens": kwargs.get("max_tokens", 4096),
            "temperature": kwargs.get("temperature", 0.2),
        }
        if system_msg:
            payload["system"] = system_msg
        try:
            resp = self.client.post("https://api.anthropic.com/v1/messages", json=payload)
            resp.raise_for_status()
            data = resp.json()
            usage = data.get("usage", {})
            duration = (time.time() - start) * 1000
            in_tokens = usage.get("input_tokens", 0)
            out_tokens = usage.get("output_tokens", 0)
            content = data.get("content", [{}])
            text = content[0].get("text", "") if content else ""
            in_price, out_price = self.PRICING.get(self.model, (3.00 / 1_000_000, 15.00 / 1_000_000))
            return ModelResponse(
                content=text, model=self.model,
                input_tokens=in_tokens, output_tokens=out_tokens,
                duration_ms=duration,
                cost_usd=(in_tokens * in_price) + (out_tokens * out_price),
                finish_reason=data.get("stop_reason", "stop"),
            )
        except Exception as e:
            return ModelResponse(
                content=f"Error: {e}", model=self.model,
                duration_ms=(time.time() - start) * 1000,
            )

    def stream(self, messages: list[Message], **kwargs) -> Generator[str, None, None]:
        yield "Streaming not yet implemented for Anthropic"


class ModelRegistry:
    _models: dict[str, type[BaseModel]] = {}

    @classmethod
    def register(cls, name: str, model_class: type[BaseModel]) -> None:
        cls._models[name] = model_class

    @classmethod
    def create(cls, name: str, **kwargs) -> BaseModel:
        if name in cls._models:
            return cls._models[name](**kwargs)
        if name in ("local", "ollama", "llama"):
            local_kwargs = {k: v for k, v in kwargs.items() if k in ("model_path", "api_base")}
            return LocalModel(**local_kwargs)
        if name.startswith("gpt-") or name.startswith("o3") or name.startswith("o4"):
            api_kwargs = {k: v for k, v in kwargs.items() if k in ("api_key", "api_base", "model")}
            api_kwargs.setdefault("model", name)
            return OpenAIModel(**api_kwargs)
        if name.startswith("claude"):
            anthropic_kwargs = {k: v for k, v in kwargs.items() if k in ("api_key", "model")}
            anthropic_kwargs.setdefault("model", name)
            return AnthropicModel(**anthropic_kwargs)
        return LocalModel()

    @classmethod
    def available(cls) -> list[str]:
        return list(cls._models.keys()) + ["local", "gpt-4o", "gpt-4o-mini", "o3-mini", "claude-3.5-sonnet"]

import os
