"""Local inference for ShellWhisperer — natural language to shell commands.

Supports:
  - HuggingFace transformers (local GPU/CPU)
  - ONNX Runtime (edge/phone)
  - llama.cpp GGUF (via llama-cpp-python)
  - Streaming output
  - Context-aware predictions (working_directory, os_type, recent_history)
"""

from __future__ import annotations

import logging
import time
from collections.abc import Generator
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from shell_whisperer.prompts import get_prompt

logger = logging.getLogger(__name__)


class Backend(str, Enum):
    """Inference backend."""

    TRANSFORMERS = "transformers"
    ONNX = "onnx"
    LLAMA_CPP = "llama_cpp"


@dataclass
class Prediction:
    """Result of a single prediction."""

    command: str
    raw_output: str
    latency_ms: float
    backend: str
    os_type: str
    safety_warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "command": self.command,
            "raw_output": self.raw_output,
            "latency_ms": round(self.latency_ms, 1),
            "backend": self.backend,
            "os_type": self.os_type,
            "safety_warnings": self.safety_warnings,
        }


# ---------------------------------------------------------------------------
# Safety guard
# ---------------------------------------------------------------------------

_DANGEROUS_PATTERNS = [
    ("rm -rf /", "Destructive: recursive force-delete of root filesystem"),
    ("rm -rf ~", "Destructive: recursive force-delete of home directory"),
    ("rm -rf /home", "Destructive: recursive force-delete of /home"),
    ("rm -rf /etc", "Destructive: recursive force-delete of /etc"),
    (":(){ :|:& };:", "Fork bomb: will crash the system"),
    ("chmod 777 /", "Dangerous: makes root world-writable"),
    ("dd if=/dev/zero of=/dev/sda", "Destructive: overwrites disk"),
    ("> /etc/passwd", "Destructive: wipes password file"),
    ("mkfs.ext4 /dev/sda", "Destructive: formats root disk"),
]


def _check_safety(command: str) -> list[str]:
    """Check a command for dangerous patterns and return warnings."""
    warnings = []
    cmd_lower = command.lower().strip()

    for pattern, reason in _DANGEROUS_PATTERNS:
        if pattern.lower() in cmd_lower:
            warnings.append(f"SAFETY: {reason}")

    # Check for pipe-to-shell patterns
    if "| sh" in cmd_lower or "| bash" in cmd_lower or "| zsh" in cmd_lower:
        if "curl" in cmd_lower or "wget" in cmd_lower:
            warnings.append("SAFETY: piping remote content to shell is dangerous")

    # Check for sudo without -A (no askpass)
    if cmd_lower.startswith("sudo ") and "-a" not in cmd_lower:
        warnings.append("INFO: this command requires sudo privileges")

    return warnings


def _clean_output(text: str) -> str:
    """Clean model output to extract just the shell command."""
    # Remove any markdown backticks
    text = text.strip()
    if text.startswith("```") and text.endswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines).strip()

    # Remove common model prefixes
    prefixes = [
        "Here's the command:",
        "Here is the command:",
        "The command is:",
        "Command:",
        "Bash:",
        "Shell:",
        "Output:",
        "Result:",
    ]
    for prefix in prefixes:
        if text.lower().startswith(prefix.lower()):
            text = text[len(prefix):].strip()

    # Take only the first line if multi-line (some models explain)
    # But preserve multi-pipe commands with && and ;
    lines = text.split("\n")
    cleaned_lines = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if line.startswith("#") or line.startswith("//"):
            continue  # skip comments
        cleaned_lines.append(line)
        # If this line ends with a shell continuation, keep going
        if line.endswith("\\"):
            continue
        # If this is a complete command (no continuation), stop
        if not any(line.endswith(c) for c in ("|", "&&", "||", ";")):
            break

    return "\n".join(cleaned_lines).strip()


# ---------------------------------------------------------------------------
# ShellWhisperer — main inference class
# ---------------------------------------------------------------------------


class ShellWhisperer:
    """Natural language to shell command converter.

    Usage:
        sw = ShellWhisperer()
        sw.load_model("./models/shell-whisperer-merged")
        result = sw.predict("find all python files over 100 lines")
        print(result.command)
    """

    def __init__(
        self,
        model_path: str | None = None,
        backend: Backend = Backend.TRANSFORMERS,
        os_type: str = "linux",
        max_new_tokens: int = 256,
        temperature: float = 0.1,
        top_p: float = 0.95,
    ):
        self.model_path = model_path
        self.backend = backend
        self.os_type = os_type
        self.max_new_tokens = max_new_tokens
        self.temperature = temperature
        self.top_p = top_p

        self.model = None
        self.tokenizer = None
        self._onnx_session = None
        self._llama_model = None

    def load_model(self, model_path: str | None = None) -> None:
        """Load the model for inference.

        Args:
            model_path: Path to the model. Uses self.model_path if None.
        """
        path = model_path or self.model_path
        if path is None:
            raise ValueError("model_path must be provided")

        self.model_path = path

        if self.backend == Backend.TRANSFORMERS:
            self._load_transformers(path)
        elif self.backend == Backend.ONNX:
            self._load_onnx(path)
        elif self.backend == Backend.LLAMA_CPP:
            self._load_llama_cpp(path)

    def _load_transformers(self, model_path: str) -> None:
        """Load model via HuggingFace transformers."""
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        logger.info("Loading transformers model from %s", model_path)

        self.tokenizer = AutoTokenizer.from_pretrained(
            model_path,
            padding_side="left",
            use_fast=True,
        )
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token

        self.model = AutoModelForCausalLM.from_pretrained(
            model_path,
            torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
            device_map="auto" if torch.cuda.is_available() else "cpu",
        )
        self.model.eval()

        logger.info("Model loaded successfully (transformers)")

    def _load_onnx(self, model_path: str) -> None:
        """Load model via ONNX Runtime."""
        import onnxruntime as ort
        from transformers import AutoTokenizer

        logger.info("Loading ONNX model from %s", model_path)

        model_dir = Path(model_path)
        onnx_file = model_dir / "model.onnx"
        if not onnx_file.exists():
            # Look for any .onnx file
            onnx_files = list(model_dir.glob("*.onnx"))
            if not onnx_files:
                raise FileNotFoundError(f"No ONNX files found in {model_dir}")
            onnx_file = onnx_files[0]

        sess_options = ort.SessionOptions()
        sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

        providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
        self._onnx_session = ort.InferenceSession(
            str(onnx_file),
            sess_options=sess_options,
            providers=providers,
        )

        # Also load tokenizer
        self.tokenizer = AutoTokenizer.from_pretrained(
            str(model_dir),
            padding_side="left",
        )

        logger.info("ONNX model loaded successfully")

    def _load_llama_cpp(self, model_path: str) -> None:
        """Load model via llama.cpp Python bindings."""
        from llama_cpp import Llama

        logger.info("Loading GGUF model from %s", model_path)

        self._llama_model = Llama(
            model_path=model_path,
            n_ctx=2048,
            n_gpu_layers=-1,  # offload all to GPU if available
        )

        logger.info("GGUF model loaded successfully")

    def predict(
        self,
        prompt: str,
        working_directory: str | None = None,
        recent_history: list[str] | None = None,
        os_type: str | None = None,
    ) -> Prediction:
        """Convert natural language to a shell command.

        Args:
            prompt: Natural language description of the desired command.
            working_directory: Current working directory context.
            recent_history: Last N commands the user ran.
            os_type: Target OS ('linux', 'macos', 'windows').

        Returns:
            Prediction with the shell command and metadata.
        """
        os_type = os_type or self.os_type
        system_prompt = get_prompt(os_type)

        # Build context-augmented user message
        user_msg = prompt
        if working_directory:
            user_msg = f"[cwd: {working_directory}] {user_msg}"
        if recent_history:
            history_str = "\n".join(f"  {cmd}" for cmd in recent_history[-5:])
            user_msg = f"{user_msg}\n[recent commands:\n{history_str}]"

        start_time = time.monotonic()

        raw_output = self._generate(system_prompt, user_msg)
        command = _clean_output(raw_output)
        safety_warnings = _check_safety(command)

        latency_ms = (time.monotonic() - start_time) * 1000

        return Prediction(
            command=command,
            raw_output=raw_output,
            latency_ms=latency_ms,
            backend=self.backend.value,
            os_type=os_type,
            safety_warnings=safety_warnings,
        )

    def predict_batch(
        self,
        prompts: list[str],
        working_directory: str | None = None,
        recent_history: list[str] | None = None,
        os_type: str | None = None,
    ) -> list[Prediction]:
        """Convert multiple natural language prompts to shell commands.

        Args:
            prompts: List of natural language descriptions.
            working_directory: Current working directory context.
            recent_history: Last N commands the user ran.
            os_type: Target OS.

        Returns:
            List of Predictions.
        """
        return [
            self.predict(p, working_directory, recent_history, os_type)
            for p in prompts
        ]

    def predict_stream(
        self,
        prompt: str,
        working_directory: str | None = None,
        recent_history: list[str] | None = None,
        os_type: str | None = None,
    ) -> Generator[str, None, None]:
        """Stream prediction tokens one at a time.

        Args:
            prompt: Natural language description.
            working_directory: Current working directory context.
            recent_history: Last N commands.
            os_type: Target OS.

        Yields:
            Token strings as they are generated.
        """
        os_type = os_type or self.os_type
        system_prompt = get_prompt(os_type)

        user_msg = prompt
        if working_directory:
            user_msg = f"[cwd: {working_directory}] {user_msg}"
        if recent_history:
            history_str = "\n".join(f"  {cmd}" for cmd in recent_history[-5:])
            user_msg = f"{user_msg}\n[recent commands:\n{history_str}]"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_msg},
        ]

        if self.backend == Backend.TRANSFORMERS and self.model is not None:
            yield from self._stream_transformers(messages)
        elif self.backend == Backend.LLAMA_CPP and self._llama_model is not None:
            yield from self._stream_llama_cpp(system_prompt, user_msg)
        else:
            # Fallback: generate all at once, then yield
            result = self.predict(prompt, working_directory, recent_history, os_type)
            yield result.command

    def _generate(self, system_prompt: str, user_msg: str) -> str:
        """Generate text using the loaded backend."""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_msg},
        ]

        if self.backend == Backend.TRANSFORMERS and self.model is not None:
            return self._generate_transformers(messages)
        elif self.backend == Backend.ONNX and self._onnx_session is not None:
            return self._generate_onnx(messages)
        elif self.backend == Backend.LLAMA_CPP and self._llama_model is not None:
            return self._generate_llama_cpp(system_prompt, user_msg)

        raise RuntimeError("No model loaded. Call load_model() first.")

    def _generate_transformers(self, messages: list[dict]) -> str:
        """Generate using HuggingFace transformers."""
        import torch

        text = self.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )
        inputs = self.tokenizer(text, return_tensors="pt").to(self.model.device)

        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=self.max_new_tokens,
                temperature=self.temperature,
                top_p=self.top_p,
                do_sample=self.temperature > 0,
                pad_token_id=self.tokenizer.eos_token_id,
            )

        # Decode only the new tokens
        input_len = inputs["input_ids"].shape[1]
        generated = outputs[0][input_len:]
        return self.tokenizer.decode(generated, skip_special_tokens=True)

    def _generate_onnx(self, messages: list[dict]) -> str:
        """Generate using ONNX Runtime."""
        import numpy as np

        text = self.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )
        inputs = self.tokenizer(text, return_tensors="np")

        input_ids = inputs["input_ids"].astype(np.int64)
        attention_mask = inputs["attention_mask"].astype(np.int64)

        # Simple greedy generation loop
        generated_ids = input_ids.copy()
        for _ in range(self.max_new_tokens):
            outputs = self._onnx_session.run(
                None,
                {
                    "input_ids": generated_ids,
                    "attention_mask": np.ones_like(generated_ids),
                },
            )
            next_token = outputs[0][0, -1, :].argmax()
            generated_ids = np.concatenate(
                [generated_ids, [[next_token]]], axis=1
            )
            if next_token == self.tokenizer.eos_token_id:
                break

        # Decode only new tokens
        new_tokens = generated_ids[0, input_ids.shape[1]:]
        return self.tokenizer.decode(new_tokens, skip_special_tokens=True)

    def _generate_llama_cpp(self, system_prompt: str, user_msg: str) -> str:
        """Generate using llama.cpp."""
        response = self._llama_model.create_chat_completion(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_msg},
            ],
            max_tokens=self.max_new_tokens,
            temperature=self.temperature,
            top_p=self.top_p,
        )
        return response["choices"][0]["message"]["content"]

    def _stream_transformers(
        self, messages: list[dict]
    ) -> Generator[str, None, None]:
        """Stream tokens from transformers model."""
        from threading import Thread

        from transformers import TextIteratorStreamer

        text = self.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )
        inputs = self.tokenizer(text, return_tensors="pt").to(self.model.device)

        streamer = TextIteratorStreamer(
            self.tokenizer,
            skip_prompt=True,
            skip_special_tokens=True,
        )

        generation_kwargs = {
            **inputs,
            "streamer": streamer,
            "max_new_tokens": self.max_new_tokens,
            "temperature": self.temperature,
            "top_p": self.top_p,
            "do_sample": self.temperature > 0,
            "pad_token_id": self.tokenizer.eos_token_id,
        }

        thread = Thread(target=self.model.generate, kwargs=generation_kwargs)
        thread.start()

        for token in streamer:
            yield token

        thread.join()

    def _stream_llama_cpp(
        self, system_prompt: str, user_msg: str
    ) -> Generator[str, None, None]:
        """Stream tokens from llama.cpp."""
        response = self._llama_model.create_chat_completion(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_msg},
            ],
            max_tokens=self.max_new_tokens,
            temperature=self.temperature,
            top_p=self.top_p,
            stream=True,
        )

        for chunk in response:
            delta = chunk["choices"][0].get("delta", {})
            if "content" in delta:
                yield delta["content"]

    def unload(self) -> None:
        """Free model resources."""
        if self.model is not None:
            del self.model
            self.model = None
        if self._onnx_session is not None:
            del self._onnx_session
            self._onnx_session = None
        if self._llama_model is not None:
            del self._llama_model
            self._llama_model = None
        self.tokenizer = None

        import gc

        gc.collect()

        try:
            import torch

            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except ImportError:
            pass
