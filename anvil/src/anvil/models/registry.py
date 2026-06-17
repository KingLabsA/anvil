"""Model backends — local, HuggingFace, OpenAI, Anthropic, Gemini, Bedrock, Azure, DeepSeek, Groq, Mistral, Cerebras, OpenRouter, Copilot, Vertex AI."""

from __future__ import annotations

import json
import os
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


def _msgs(messages: list[Message]) -> list[dict]:
    return [{"role": m.role, "content": m.content} for m in messages]


def _err(model: str, e: Exception, start: float) -> ModelResponse:
    return ModelResponse(content=f"Error: {e}", model=model, duration_ms=(time.time() - start) * 1000)


# ---------------------------------------------------------------------------
# Existing providers
# ---------------------------------------------------------------------------

class TransformersModel(BaseModel):
    name = "transformers"

    def __init__(self, model_name: str = "fableforge-ai/ShellWhisperer-1.5B", device: str | None = None, load_in_4bit: bool = False):
        self.model_name = model_name
        self.model = None
        self.tokenizer = None
        self.device = device or "cpu"
        self.load_error = ""
        try:
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

            self.device = device or ("cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu")
            print(f"Loading {model_name} on {self.device}...")
            self.tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
            if self.tokenizer.pad_token is None:
                self.tokenizer.pad_token = self.tokenizer.eos_token

            kwargs = {"dtype": torch.float16 if self.device == "cuda" else torch.float32, "trust_remote_code": True}
            if load_in_4bit and self.device == "cuda":
                kwargs["quantization_config"] = BitsAndBytesConfig(load_in_4bit=True)
                kwargs["device_map"] = "auto"
            else:
                kwargs["device_map"] = None

            self.model = AutoModelForCausalLM.from_pretrained(model_name, **kwargs)
            if not kwargs.get("device_map"):
                self.model = self.model.to(self.device)
            print(f"Model loaded on {self.device}")
        except Exception as e:
            self.model = None
            self.tokenizer = None
            self.load_error = str(e)
            print(f"Warning: failed to load {model_name}: {e}")

    def _prepare_inputs(self, messages: list[Message], max_new_tokens: int = 512, temperature: float = 0.2):
        if self.model is None or self.tokenizer is None:
            return None, None, "Error: model not loaded. " + getattr(self, "load_error", "")

        chat_text = self.tokenizer.apply_chat_template(
            [{"role": m.role, "content": m.content} for m in messages],
            tokenize=False,
            add_generation_prompt=True,
        )
        inputs = self.tokenizer(chat_text, return_tensors="pt", padding=True, truncation=True, max_length=2048)
        inputs = {k: v.to(self.model.device) for k, v in inputs.items()}
        input_tokens = inputs["input_ids"].shape[1]

        gen_kwargs = {
            "max_new_tokens": max_new_tokens,
            "temperature": temperature,
            "top_p": 0.9,
            "do_sample": temperature > 0,
            "pad_token_id": self.tokenizer.pad_token_id,
            "eos_token_id": self.tokenizer.eos_token_id,
        }
        return inputs, gen_kwargs, input_tokens

    def complete(self, messages: list[Message], **kwargs) -> ModelResponse:
        start = time.time()
        if self.model is None or self.tokenizer is None:
            return ModelResponse(
                content=getattr(self, "load_error", "Model not loaded"),
                model=self.model_name,
                duration_ms=(time.time() - start) * 1000,
            )

        inputs, gen_kwargs, input_tokens = self._prepare_inputs(
            messages,
            max_new_tokens=kwargs.get("max_tokens", 512),
            temperature=kwargs.get("temperature", 0.2),
        )
        try:
            import torch

            with torch.no_grad():
                outputs = self.model.generate(**inputs, **gen_kwargs)
            output_text = self.tokenizer.decode(outputs[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True)
            output_tokens = outputs.shape[1] - inputs["input_ids"].shape[1]
            duration = (time.time() - start) * 1000
            return ModelResponse(
                content=output_text.strip(),
                model=self.model_name,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                duration_ms=duration,
                cost_usd=0.0,
            )
        except Exception as e:
            return ModelResponse(
                content=f"Error during generation: {e}",
                model=self.model_name,
                duration_ms=(time.time() - start) * 1000,
            )

    def stream(self, messages: list[Message], **kwargs) -> Generator[str, None, None]:
        response = self.complete(messages, **kwargs)
        yield response.content

    def count_tokens(self, text: str) -> int:
        if self.tokenizer is None:
            return len(text) // 4
        return len(self.tokenizer.encode(text))


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
            "messages": _msgs(messages),
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
            return _err(self.model_name, e, start)

    def stream(self, messages: list[Message], **kwargs) -> Generator[str, None, None]:
        payload = {
            "model": self.model_name,
            "messages": _msgs(messages),
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
            "messages": _msgs(messages),
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
            return _err(self.model, e, start)

    def stream(self, messages: list[Message], **kwargs) -> Generator[str, None, None]:
        payload = {
            "model": self.model,
            "messages": _msgs(messages),
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
            return _err(self.model, e, start)

    def stream(self, messages: list[Message], **kwargs) -> Generator[str, None, None]:
        yield "Streaming not yet implemented for Anthropic"


# ---------------------------------------------------------------------------
# New providers
# ---------------------------------------------------------------------------

class _OpenAICompatible(BaseModel):
    """Base for providers that expose an OpenAI-compatible /chat/completions endpoint."""

    api_base: str = ""
    PRICING: dict[str, tuple[float, float]] = {}

    def __init__(self, api_key: str | None = None, model: str = "", api_base: str | None = None, env_var: str = ""):
        self.api_key = api_key or os.environ.get(env_var, "")
        self.model = model
        self.api_base = (api_base or self.__class__.api_base).rstrip("/")
        self.client = httpx.Client(timeout=120.0, headers={
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        })

    def complete(self, messages: list[Message], **kwargs) -> ModelResponse:
        start = time.time()
        payload = {
            "model": self.model,
            "messages": _msgs(messages),
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
            in_price, out_price = self.PRICING.get(self.model, (0.0, 0.0))
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
            return _err(self.model, e, start)

    def stream(self, messages: list[Message], **kwargs) -> Generator[str, None, None]:
        payload = {
            "model": self.model,
            "messages": _msgs(messages),
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


class GeminiModel(BaseModel):
    """Google Gemini API provider.

    Endpoint: https://generativelanguage.googleapis.com/v1beta/models/
    Models: gemini-2.0-flash, gemini-1.5-pro, gemini-1.5-flash
    Auth: API key in query parameter
    """

    name = "gemini"
    ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models"

    PRICING = {
        "gemini-2.0-flash": (0.0, 0.0),
        "gemini-1.5-pro": (1.25 / 1_000_000, 5.00 / 1_000_000),
        "gemini-1.5-flash": (0.0, 0.0),
    }

    def __init__(self, api_key: str | None = None, model: str = "gemini-2.0-flash"):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY", "")
        self.model = model
        self.client = httpx.Client(timeout=120.0)

    def _build_contents(self, messages: list[Message]) -> list[dict]:
        contents = []
        for m in messages:
            if m.role == "system":
                continue
            role = "user" if m.role == "user" else "model"
            contents.append({"role": role, "parts": [{"text": m.content}]})
        return contents

    def _system_instruction(self, messages: list[Message]) -> str | None:
        for m in messages:
            if m.role == "system":
                return m.content
        return None

    def complete(self, messages: list[Message], **kwargs) -> ModelResponse:
        start = time.time()
        payload: dict = {
            "contents": self._build_contents(messages),
            "generationConfig": {
                "maxOutputTokens": kwargs.get("max_tokens", 4096),
                "temperature": kwargs.get("temperature", 0.2),
            },
        }
        sys_instr = self._system_instruction(messages)
        if sys_instr:
            payload["systemInstruction"] = {"parts": [{"text": sys_instr}]}
        try:
            url = f"{self.ENDPOINT}/{self.model}:generateContent?key={self.api_key}"
            resp = self.client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
            duration = (time.time() - start) * 1000
            candidates = data.get("candidates", [])
            text = ""
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                text = parts[0].get("text", "") if parts else ""
            usage = data.get("usageMetadata", {})
            in_tokens = usage.get("promptTokenCount", 0)
            out_tokens = usage.get("candidatesTokenCount", 0)
            in_price, out_price = self.PRICING.get(self.model, (0.0, 0.0))
            return ModelResponse(
                content=text,
                model=self.model,
                input_tokens=in_tokens,
                output_tokens=out_tokens,
                duration_ms=duration,
                cost_usd=(in_tokens * in_price) + (out_tokens * out_price),
                finish_reason=candidates[0].get("finishReason", "stop").lower() if candidates else "stop",
            )
        except Exception as e:
            return _err(self.model, e, start)

    def stream(self, messages: list[Message], **kwargs) -> Generator[str, None, None]:
        payload: dict = {
            "contents": self._build_contents(messages),
            "generationConfig": {
                "maxOutputTokens": kwargs.get("max_tokens", 4096),
                "temperature": kwargs.get("temperature", 0.2),
            },
        }
        sys_instr = self._system_instruction(messages)
        if sys_instr:
            payload["systemInstruction"] = {"parts": [{"text": sys_instr}]}
        try:
            url = f"{self.ENDPOINT}/{self.model}:streamGenerateContent?alt=sse&key={self.api_key}"
            with self.client.stream("POST", url, json=payload) as resp:
                for line in resp.iter_lines():
                    if line.startswith("data: "):
                        data = json.loads(line[6:])
                        candidates = data.get("candidates", [])
                        if candidates:
                            parts = candidates[0].get("content", {}).get("parts", [])
                            for part in parts:
                                if text := part.get("text"):
                                    yield text
        except Exception as e:
            yield f"Error: {e}"


class BedrockModel(BaseModel):
    """AWS Bedrock provider.

    Uses boto3 to invoke models on AWS Bedrock.
    Models: claude-3, llama-3, mistral-large
    Auth: AWS credentials via boto3 (env vars, IAM role, etc.)
    """

    name = "bedrock"

    PRICING = {
        "claude-3": (3.00 / 1_000_000, 15.00 / 1_000_000),
        "llama-3": (0.0, 0.0),
        "mistral-large": (2.00 / 1_000_000, 6.00 / 1_000_000),
    }

    def __init__(self, api_key: str | None = None, model: str = "claude-3", region: str = "us-east-1"):
        self.model = model
        self.region = region
        self._client = None
        try:
            import boto3
            self._client = boto3.client("bedrock-runtime", region_name=region)
        except ImportError:
            pass
        except Exception as e:
            print(f"Warning: failed to initialize Bedrock client: {e}")

    def _model_id(self) -> str:
        mapping = {
            "claude-3": "anthropic.claude-3-5-sonnet-20241022-v2:0",
            "claude-3-opus": "anthropic.claude-3-opus-20240229-v1:0",
            "claude-3-sonnet": "anthropic.claude-3-sonnet-20240229-v1:0",
            "claude-3-haiku": "anthropic.claude-3-haiku-20240307-v1:0",
            "llama-3": "meta.llama3-70b-instruct-v1:0",
            "llama-3-70b": "meta.llama3-70b-instruct-v1:0",
            "llama-3-8b": "meta.llama3-8b-instruct-v1:0",
            "mistral-large": "mistral.mistral-large-2402-v1:0",
        }
        return mapping.get(self.model, self.model)

    def complete(self, messages: list[Message], **kwargs) -> ModelResponse:
        start = time.time()
        if self._client is None:
            return ModelResponse(
                content="Error: boto3 not available or Bedrock client failed to initialize. Install boto3.",
                model=self.model,
                duration_ms=(time.time() - start) * 1000,
            )
        try:
            body = {
                "messages": [{"role": m.role, "content": m.content} for m in messages if m.role != "system"],
                "max_tokens": kwargs.get("max_tokens", 4096),
                "temperature": kwargs.get("temperature", 0.2),
            }
            sys_msgs = [m.content for m in messages if m.role == "system"]
            if sys_msgs:
                body["system"] = sys_msgs[0]

            resp = self._client.invoke_model(
                modelId=self._model_id(),
                contentType="application/json",
                body=json.dumps(body),
            )
            data = json.loads(resp["body"].read())
            duration = (time.time() - start) * 1000

            content = ""
            if "content" in data:
                content = data["content"][0].get("text", "")
            elif "generation" in data:
                content = data["generation"]
            elif "outputs" in data:
                content = data["outputs"][0].get("text", "")

            usage = data.get("usage", {})
            in_tokens = usage.get("input_tokens", 0)
            out_tokens = usage.get("output_tokens", 0)
            in_price, out_price = self.PRICING.get(self.model, (0.0, 0.0))
            return ModelResponse(
                content=content,
                model=self.model,
                input_tokens=in_tokens,
                output_tokens=out_tokens,
                duration_ms=duration,
                cost_usd=(in_tokens * in_price) + (out_tokens * out_price),
            )
        except Exception as e:
            return _err(self.model, e, start)

    def stream(self, messages: list[Message], **kwargs) -> Generator[str, None, None]:
        response = self.complete(messages, **kwargs)
        yield response.content


class AzureOpenAIModel(BaseModel):
    """Azure OpenAI Service provider.

    Endpoint: https://{resource}.openai.azure.com/openai/deployments/{deployment}/
    Models: gpt-4, gpt-4-turbo, gpt-35-turbo
    Auth: API key + deployment name
    """

    name = "azure"

    PRICING = {
        "gpt-4": (30.00 / 1_000_000, 60.00 / 1_000_000),
        "gpt-4-turbo": (10.00 / 1_000_000, 30.00 / 1_000_000),
        "gpt-35-turbo": (0.50 / 1_000_000, 1.50 / 1_000_000),
    }

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "gpt-4",
        resource: str | None = None,
        deployment: str | None = None,
        api_version: str = "2024-02-01",
    ):
        self.api_key = api_key or os.environ.get("AZURE_OPENAI_API_KEY", "")
        self.model = model
        self.resource = resource or os.environ.get("AZURE_OPENAI_RESOURCE", "")
        self.deployment = deployment or model
        self.api_version = api_version
        self.api_base = f"https://{self.resource}.openai.azure.com/openai/deployments/{self.deployment}"
        self.client = httpx.Client(timeout=120.0, headers={
            "api-key": self.api_key,
            "Content-Type": "application/json",
        })

    def complete(self, messages: list[Message], **kwargs) -> ModelResponse:
        start = time.time()
        payload = {
            "messages": _msgs(messages),
            "max_tokens": kwargs.get("max_tokens", 4096),
            "temperature": kwargs.get("temperature", 0.2),
        }
        try:
            url = f"{self.api_base}/chat/completions?api-version={self.api_version}"
            resp = self.client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
            choice = data["choices"][0]
            usage = data.get("usage", {})
            duration = (time.time() - start) * 1000
            in_tokens = usage.get("prompt_tokens", 0)
            out_tokens = usage.get("completion_tokens", 0)
            in_price, out_price = self.PRICING.get(self.model, (30.00 / 1_000_000, 60.00 / 1_000_000))
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
            return _err(self.model, e, start)

    def stream(self, messages: list[Message], **kwargs) -> Generator[str, None, None]:
        payload = {
            "messages": _msgs(messages),
            "stream": True,
            "max_tokens": kwargs.get("max_tokens", 4096),
            "temperature": kwargs.get("temperature", 0.2),
        }
        try:
            url = f"{self.api_base}/chat/completions?api-version={self.api_version}"
            with self.client.stream("POST", url, json=payload) as resp:
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


class DeepSeekModel(_OpenAICompatible):
    """DeepSeek API provider (OpenAI-compatible).

    Endpoint: https://api.deepseek.com/v1
    Models: deepseek-coder, deepseek-chat
    Auth: API key
    """

    name = "deepseek"
    api_base = "https://api.deepseek.com/v1"

    PRICING = {
        "deepseek-coder": (0.14 / 1_000_000, 0.28 / 1_000_000),
        "deepseek-chat": (0.14 / 1_000_000, 0.28 / 1_000_000),
    }

    def __init__(self, api_key: str | None = None, model: str = "deepseek-coder"):
        super().__init__(api_key=api_key, model=model, env_var="DEEPSEEK_API_KEY")


class GroqModel(_OpenAICompatible):
    """Groq fast inference provider (OpenAI-compatible).

    Endpoint: https://api.groq.com/openai/v1
    Models: llama-3.1-70b, mixtral-8x7b
    Auth: API key
    """

    name = "groq"
    api_base = "https://api.groq.com/openai/v1"

    PRICING = {
        "llama-3.1-70b": (0.59 / 1_000_000, 0.79 / 1_000_000),
        "mixtral-8x7b": (0.24 / 1_000_000, 0.24 / 1_000_000),
    }

    def __init__(self, api_key: str | None = None, model: str = "llama-3.1-70b"):
        super().__init__(api_key=api_key, model=model, env_var="GROQ_API_KEY")


class MistralModel(_OpenAICompatible):
    """Mistral AI provider (OpenAI-compatible).

    Endpoint: https://api.mistral.ai/v1
    Models: mistral-large, codestral, mistral-small
    Auth: API key
    """

    name = "mistral"
    api_base = "https://api.mistral.ai/v1"

    PRICING = {
        "mistral-large": (2.00 / 1_000_000, 6.00 / 1_000_000),
        "codestral": (0.20 / 1_000_000, 0.60 / 1_000_000),
        "mistral-small": (0.10 / 1_000_000, 0.30 / 1_000_000),
    }

    def __init__(self, api_key: str | None = None, model: str = "mistral-large"):
        super().__init__(api_key=api_key, model=model, env_var="MISTRAL_API_KEY")


class CerebrasModel(_OpenAICompatible):
    """Cerebras fastest inference provider (OpenAI-compatible).

    Endpoint: https://api.cerebras.ai/v1
    Models: llama3.1-70b, llama3.1-8b
    Auth: API key
    """

    name = "cerebras"
    api_base = "https://api.cerebras.ai/v1"

    PRICING = {
        "llama3.1-70b": (0.0, 0.0),
        "llama3.1-8b": (0.0, 0.0),
    }

    def __init__(self, api_key: str | None = None, model: str = "llama3.1-70b"):
        super().__init__(api_key=api_key, model=model, env_var="CEREBRAS_API_KEY")


class OpenRouterModel(_OpenAICompatible):
    """OpenRouter multi-model routing provider (OpenAI-compatible).

    Endpoint: https://openrouter.ai/api/v1
    Models: Any model via routing (100+ available)
    Auth: API key
    """

    name = "openrouter"
    api_base = "https://openrouter.ai/api/v1"

    PRICING: dict[str, tuple[float, float]] = {}

    def __init__(self, api_key: str | None = None, model: str = "openai/gpt-4o"):
        super().__init__(api_key=api_key, model=model, env_var="OPENROUTER_API_KEY")


class CopilotModel(BaseModel):
    """GitHub Copilot provider.

    Uses GitHub token auth to access Copilot's model proxy.
    Models: gpt-4, claude-3, gemini-pro
    Auth: GitHub PAT
    """

    name = "copilot"
    ENDPOINT = "https://api.githubcopilot.com/chat/completions"

    def __init__(self, api_key: str | None = None, model: str = "gpt-4"):
        self.api_key = api_key or os.environ.get("GITHUB_TOKEN", "")
        self.model = model
        self.client = httpx.Client(timeout=120.0, headers={
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Editor-Version": "vscode/1.90.0",
            "Editor-Plugin-Version": "copilot-chat/0.17",
        })

    def complete(self, messages: list[Message], **kwargs) -> ModelResponse:
        start = time.time()
        payload = {
            "model": self.model,
            "messages": _msgs(messages),
            "max_tokens": kwargs.get("max_tokens", 4096),
            "temperature": kwargs.get("temperature", 0.2),
        }
        try:
            resp = self.client.post(self.ENDPOINT, json=payload)
            resp.raise_for_status()
            data = resp.json()
            choice = data["choices"][0]
            usage = data.get("usage", {})
            duration = (time.time() - start) * 1000
            return ModelResponse(
                content=choice["message"]["content"],
                model=self.model,
                input_tokens=usage.get("prompt_tokens", 0),
                output_tokens=usage.get("completion_tokens", 0),
                duration_ms=duration,
                cost_usd=0.0,
                finish_reason=choice.get("finish_reason", "stop"),
            )
        except Exception as e:
            return _err(self.model, e, start)

    def stream(self, messages: list[Message], **kwargs) -> Generator[str, None, None]:
        payload = {
            "model": self.model,
            "messages": _msgs(messages),
            "stream": True,
            "max_tokens": kwargs.get("max_tokens", 4096),
            "temperature": kwargs.get("temperature", 0.2),
        }
        try:
            with self.client.stream("POST", self.ENDPOINT, json=payload) as resp:
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


class VertexAIModel(BaseModel):
    """GCP Vertex AI provider.

    Uses google-cloud-aiplatform SDK.
    Models: gemini-pro, claude-3, code-bison
    Auth: GCP service account
    """

    name = "vertex"

    PRICING = {
        "gemini-pro": (0.0, 0.0),
        "claude-3": (3.00 / 1_000_000, 15.00 / 1_000_000),
        "code-bison": (0.0, 0.0),
    }

    def __init__(self, api_key: str | None = None, model: str = "gemini-pro", project: str | None = None, location: str = "us-central1"):
        self.api_key = api_key
        self.model = model
        self.project = project or os.environ.get("GOOGLE_CLOUD_PROJECT", "")
        self.location = location
        self._client = None
        try:
            from google.cloud import aiplatform
            aiplatform.init(project=self.project, location=self.location)
            self._client = aiplatform
        except ImportError:
            pass
        except Exception as e:
            print(f"Warning: failed to initialize Vertex AI client: {e}")

    def complete(self, messages: list[Message], **kwargs) -> ModelResponse:
        start = time.time()
        if self._client is None:
            return ModelResponse(
                content="Error: google-cloud-aiplatform not available. Install google-cloud-aiplatform.",
                model=self.model,
                duration_ms=(time.time() - start) * 1000,
            )
        try:
            from vertexai.generative_models import GenerativeModel

            model = GenerativeModel(self.model)
            contents = []
            for m in messages:
                if m.role == "system":
                    continue
                contents.append({"role": "user" if m.role == "user" else "model", "parts": [m.content]})

            sys_msgs = [m.content for m in messages if m.role == "system"]
            gen_config = {
                "max_output_tokens": kwargs.get("max_tokens", 4096),
                "temperature": kwargs.get("temperature", 0.2),
            }
            response = model.generate_content(
                contents,
                generation_config=gen_config,
            )
            duration = (time.time() - start) * 1000
            text = response.text if hasattr(response, "text") else ""
            usage = response.usage_metadata if hasattr(response, "usage_metadata") else {}
            in_tokens = getattr(usage, "prompt_token_count", 0) if usage else 0
            out_tokens = getattr(usage, "candidates_token_count", 0) if usage else 0
            in_price, out_price = self.PRICING.get(self.model, (0.0, 0.0))
            return ModelResponse(
                content=text,
                model=self.model,
                input_tokens=in_tokens,
                output_tokens=out_tokens,
                duration_ms=duration,
                cost_usd=(in_tokens * in_price) + (out_tokens * out_price),
            )
        except Exception as e:
            return _err(self.model, e, start)

    def stream(self, messages: list[Message], **kwargs) -> Generator[str, None, None]:
        response = self.complete(messages, **kwargs)
        yield response.content


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

class ModelRegistry:
    """Routes model names to provider backends."""

    _models: dict[str, type[BaseModel]] = {}

    @classmethod
    def register(cls, name: str, model_class: type[BaseModel]) -> None:
        cls._models[name] = model_class

    @classmethod
    def create(cls, name: str, **kwargs) -> BaseModel:
        if name in cls._models:
            return cls._models[name](**kwargs)

        transformers_kwargs = {k: v for k, v in kwargs.items() if k in ("device", "load_in_4bit")}

        if name in ("shellwhisperer", "fableforge-ai/ShellWhisperer-1.5B"):
            return TransformersModel(model_name="fableforge-ai/ShellWhisperer-1.5B", **transformers_kwargs)
        if name in ("local", "ollama", "llama"):
            local_kwargs = {k: v for k, v in kwargs.items() if k in ("model_path", "api_base")}
            return LocalModel(**local_kwargs)

        # OpenAI-compatible prefix routing
        if name.startswith("gpt-") or name.startswith("o3") or name.startswith("o4"):
            api_kwargs = {k: v for k, v in kwargs.items() if k in ("api_key", "api_base", "model")}
            api_kwargs.setdefault("model", name)
            return OpenAIModel(**api_kwargs)
        if name.startswith("claude") and not name.startswith("copilot"):
            anthropic_kwargs = {k: v for k, v in kwargs.items() if k in ("api_key", "model")}
            anthropic_kwargs.setdefault("model", name)
            return AnthropicModel(**anthropic_kwargs)

        # New provider prefix routing
        if name.startswith("gemini"):
            p = {k: v for k, v in kwargs.items() if k in ("api_key", "model")}
            p.setdefault("model", name)
            return GeminiModel(**p)
        if name.startswith("bedrock"):
            p = {k: v for k, v in kwargs.items() if k in ("api_key", "model", "region")}
            p.setdefault("model", name)
            return BedrockModel(**p)
        if name.startswith("azure"):
            p = {k: v for k, v in kwargs.items() if k in ("api_key", "model", "resource", "deployment", "api_version")}
            p.setdefault("model", name)
            return AzureOpenAIModel(**p)
        if name.startswith("deepseek"):
            p = {k: v for k, v in kwargs.items() if k in ("api_key", "model")}
            p.setdefault("model", name)
            return DeepSeekModel(**p)
        if name.startswith("groq"):
            p = {k: v for k, v in kwargs.items() if k in ("api_key", "model")}
            p.setdefault("model", name)
            return GroqModel(**p)
        if name.startswith("mistral"):
            p = {k: v for k, v in kwargs.items() if k in ("api_key", "model")}
            p.setdefault("model", name)
            return MistralModel(**p)
        if name.startswith("cerebras"):
            p = {k: v for k, v in kwargs.items() if k in ("api_key", "model")}
            p.setdefault("model", name)
            return CerebrasModel(**p)
        if name.startswith("openrouter"):
            p = {k: v for k, v in kwargs.items() if k in ("api_key", "model")}
            p.setdefault("model", name)
            return OpenRouterModel(**p)
        if name.startswith("copilot"):
            p = {k: v for k, v in kwargs.items() if k in ("api_key", "model")}
            p.setdefault("model", name)
            return CopilotModel(**p)
        if name.startswith("vertex"):
            p = {k: v for k, v in kwargs.items() if k in ("api_key", "model", "project", "location")}
            p.setdefault("model", name)
            return VertexAIModel(**p)

        if "/" in name:
            return TransformersModel(model_name=name, **transformers_kwargs)

        local_kwargs = {k: v for k, v in kwargs.items() if k in ("model_path", "api_base")}
        local_kwargs.setdefault("model_path", name)
        return LocalModel(**local_kwargs)

    @classmethod
    def available(cls) -> list[str]:
        return list(cls._models.keys()) + [
            "shellwhisperer", "local",
            "gpt-4o", "gpt-4o-mini", "o3-mini", "o4-mini",
            "claude-3.5-sonnet", "claude-3.5-haiku", "claude-3-opus",
            "gemini-2.0-flash", "gemini-1.5-pro", "gemini-1.5-flash",
            "bedrock/claude-3", "bedrock/llama-3", "bedrock/mistral-large",
            "azure/gpt-4", "azure/gpt-4-turbo", "azure/gpt-35-turbo",
            "deepseek-coder", "deepseek-chat",
            "groq/llama-3.1-70b", "groq/mixtral-8x7b",
            "mistral-large", "codestral", "mistral-small",
            "cerebras/llama3.1-70b", "cerebras/llama3.1-8b",
            "openrouter/openai/gpt-4o",
            "copilot/gpt-4", "copilot/claude-3",
            "vertex/gemini-pro", "vertex/claude-3",
        ]
