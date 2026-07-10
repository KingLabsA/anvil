"""Model provider implementations for bench-agent."""

from __future__ import annotations

import json
import os
import urllib.request
import urllib.error


def _openai_complete(model: str, prompt: str, api_key: str, base_url: str) -> str:
    """Call an OpenAI-compatible chat endpoint."""
    url = f"{base_url.rstrip('/')}/chat/completions"
    data = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 1024,
        "temperature": 0.2,
    }).encode()
    req = urllib.request.Request(url, data=data, headers={
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    })
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read())
        return result["choices"][0]["message"]["content"]
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        return f"[API ERROR {e.code}] {body[:500]}"
    except Exception as e:
        return f"[ERROR] {e}"


def _anthropic_complete(model: str, prompt: str, api_key: str) -> str:
    """Call Anthropic API."""
    url = "https://api.anthropic.com/v1/messages"
    data = json.dumps({
        "model": model,
        "max_tokens": 1024,
        "messages": [{"role": "user", "content": prompt}],
    }).encode()
    req = urllib.request.Request(url, data=data, headers={
        "Content-Type": "application/json",
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
    })
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read())
        return result["content"][0]["text"]
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        return f"[API ERROR {e.code}] {body[:500]}"
    except Exception as e:
        return f"[ERROR] {e}"


def _huggingface_complete(model: str, prompt: str) -> str:
    """Load and run a HuggingFace model locally with transformers."""
    try:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
    except ImportError:
        return "[ERROR] transformers not installed. Run: pip install transformers torch"

    try:
        tokenizer = AutoTokenizer.from_pretrained(model, trust_remote_code=True)
        model_obj = AutoModelForCausalLM.from_pretrained(
            model, torch_dtype=torch.bfloat16, trust_remote_code=True,
        )
        model_obj.eval()
        if torch.cuda.is_available():
            model_obj = model_obj.cuda()
    except Exception as e:
        return f"[ERROR loading model] {e}"

    try:
        if tokenizer.chat_template:
            text = tokenizer.apply_chat_template(
                [{"role": "user", "content": prompt}],
                tokenize=False, add_generation_prompt=True,
            )
        else:
            text = f"user: {prompt}\nassistant:"
        inputs = tokenizer(text, return_tensors="pt")
        if torch.cuda.is_available():
            inputs = {k: v.to("cuda") for k, v in inputs.items()}
        with torch.no_grad():
            outputs = model_obj.generate(
                **inputs, max_new_tokens=512, temperature=0.2, do_sample=True,
                pad_token_id=tokenizer.eos_token_id,
            )
        return tokenizer.decode(outputs[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True)
    except Exception as e:
        return f"[ERROR during generation] {e}"


def create_model_fn(provider: str, model: str) -> callable:
    """Create a model function for the given provider."""
    if provider == "openai":
        api_key = os.environ.get("OPENAI_API_KEY", "not-needed")
        base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
        return lambda prompt: _openai_complete(model, prompt, api_key, base_url)

    elif provider == "anthropic":
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            return lambda prompt: "[ERROR] ANTHROPIC_API_KEY not set"
        return lambda prompt: _anthropic_complete(model, prompt, api_key)

    elif provider == "local":
        return lambda prompt: _huggingface_complete(model, prompt)

    elif provider == "huggingface":
        return lambda prompt: _huggingface_complete(model, prompt)

    else:
        return lambda prompt: f"[ERROR] Unknown provider: {provider}"
