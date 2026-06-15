"""Generate-then-verify pipeline.

Takes a generator model and a critic model, generates code,
verifies it, and feeds issues back for re-generation if needed.
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime

from reason_critic.critic import VerificationResult

logger = logging.getLogger(__name__)


@dataclass
class GenerationAttempt:
    """A single generation-verification attempt."""

    attempt_number: int
    code: str
    verification: VerificationResult
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class VerifiedResult:
    """Final result from the generate-then-verify pipeline."""

    task: str
    attempts: list[GenerationAttempt]
    final_code: str
    final_verification: VerificationResult
    passed: bool
    total_attempts: int

    def to_dict(self) -> dict:
        return {
            "task": self.task,
            "passed": self.passed,
            "total_attempts": self.total_attempts,
            "final_code": self.final_code,
            "final_verification": self.final_verification.to_dict(),
            "attempts": [
                {
                    "attempt": a.attempt_number,
                    "code": a.code,
                    "verification": a.verification.to_dict(),
                    "timestamp": a.timestamp,
                }
                for a in self.attempts
            ],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)


class GeneratorWrapper:
    """Wraps a text generation model for code generation.

    Handles prompting, generation parameters, and issue feedback
    integration for re-generation attempts.
    """

    def __init__(self, model_name: str = "Qwen/Qwen3-7B", device: str = "auto"):
        self.model_name = model_name
        self.device = device
        self._model = None
        self._tokenizer = None

    def _load(self):
        if self._model is not None:
            return

        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        logger.info(f"Loading generator model: {self.model_name}")
        self._tokenizer = AutoTokenizer.from_pretrained(self.model_name, trust_remote_code=True)
        if self._tokenizer.pad_token is None:
            self._tokenizer.pad_token = self._tokenizer.eos_token

        self._model = AutoModelForCausalLM.from_pretrained(
            self.model_name,
            torch_dtype=torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16,
            device_map=self.device,
            trust_remote_code=True,
        )
        self._model.eval()

    def generate(
        self,
        task: str,
        language: str = "python",
        issues: list[str] | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.7,
    ) -> str:
        """Generate code for a task, optionally addressing previous issues.

        Args:
            task: Description of the code to generate.
            language: Programming language.
            issues: Previous verification issues to address (for re-generation).
            max_tokens: Maximum tokens to generate.
            temperature: Sampling temperature.

        Returns:
            Generated code string.
        """
        self._load()

        prompt = f"Generate {language} code for the following task:\n\n{task}\n\n"
        prompt += f"```{language}\n"

        if issues:
            prompt = (
                f"Generate {language} code for the following task. "
                f"The previous attempt had these issues that must be fixed:\n"
            )
            for issue in issues:
                prompt += f"- {issue}\n"
            prompt += f"\nTask: {task}\n\n```{language}\n"

        inputs = self._tokenizer(prompt, return_tensors="pt").to(self._model.device)

        import torch

        with torch.no_grad():
            outputs = self._model.generate(
                **inputs,
                max_new_tokens=max_tokens,
                temperature=temperature,
                do_sample=temperature > 0,
                pad_token_id=self._tokenizer.eos_token_id,
            )

        generated = self._tokenizer.decode(outputs[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True)

        # Extract code from markdown fences
        code = _extract_code(generated)
        return code


class GenerateVerifyPipeline:
    """Generate-then-verify pipeline.

    Takes a generator model and a critic model, generates code,
    verifies it, and feeds issues back to the generator for
    re-generation if verification fails.

    The pipeline tracks every attempt, including:
    - Generation output
    - Verification result
    - Re-generation with issue feedback
    - Final verification

    Args:
        generator: GeneratorWrapper or model name string for generation.
        critic: ReasonCritic instance for verification.
        max_attempts: Maximum generation-verification cycles.
        language: Default programming language.

    Usage:
        pipeline = GenerateVerifyPipeline(
            generator="Qwen/Qwen3-7B",
            critic=ReasonCritic(backend="local", model_name="reason-critic-7b"),
        )
        result = pipeline.generate_and_verify("Write a function that reverses a string")
        print(result.passed, result.final_code)
    """

    def __init__(
        self,
        generator: str | GeneratorWrapper,
        critic,  # ReasonCritic — lazy to avoid torch import
        max_attempts: int = 3,
        language: str = "python",
    ):
        if isinstance(generator, str):
            self.generator = GeneratorWrapper(model_name=generator)
        else:
            self.generator = generator

        self.critic = critic
        self.max_attempts = max_attempts
        self.language = language

    def generate_and_verify(
        self,
        task: str,
        max_attempts: int | None = None,
        language: str | None = None,
        context: str = "",
    ) -> VerifiedResult:
        """Generate code and verify it, with re-generation on failures.

        Args:
            task: Description of the code to generate.
            max_attempts: Override max attempts for this call.
            language: Override language for this call.
            context: Optional context for verification.

        Returns:
            VerifiedResult with all attempts and final outcome.
        """
        attempts = max_attempts or self.max_attempts
        lang = language or self.language
        all_attempts: list[GenerationAttempt] = []

        issues_from_previous: list[str] = []

        for attempt_num in range(1, attempts + 1):
            logger.info(f"Generate-verify attempt {attempt_num}/{attempts}")

            # Generate
            code = self.generator.generate(
                task=task,
                language=lang,
                issues=issues_from_previous if attempt_num > 1 else None,
            )

            # Verify
            verification = self.critic.verify(code, context=context, language=lang)

            attempt = GenerationAttempt(
                attempt_number=attempt_num,
                code=code,
                verification=verification,
            )
            all_attempts.append(attempt)

            # If it passes, we're done
            if verification.is_pass:
                logger.info(f"Verification passed on attempt {attempt_num}")
                return VerifiedResult(
                    task=task,
                    attempts=all_attempts,
                    final_code=code,
                    final_verification=verification,
                    passed=True,
                    total_attempts=attempt_num,
                )

            # Feed issues back
            issues_from_previous = verification.issues
            logger.info(
                f"Attempt {attempt_num} failed: "
                f"{len(verification.issues)} issues, "
                f"re-generating with feedback..."
            )

        # All attempts exhausted — return the last one
        last_attempt = all_attempts[-1]
        return VerifiedResult(
            task=task,
            attempts=all_attempts,
            final_code=last_attempt.code,
            final_verification=last_attempt.verification,
            passed=False,
            total_attempts=attempts,
        )

    def generate_and_verify_trace(
        self,
        trace: dict,
        max_attempts: int | None = None,
    ) -> dict:
        """Generate-verify pipeline applied to an agent trace.

        For each generation step in the trace, verify the output
        and attempt re-generation if it fails.

        Args:
            trace: Agent trace dict with 'steps' key.
            max_attempts: Override max attempts per step.

        Returns:
            Dict with step-by-step verified results.
        """
        max_att = max_attempts or self.max_attempts
        steps = trace.get("steps", [])
        results = []

        for step in steps:
            if step.get("type") not in ("generation", "code_generation", "write"):
                continue

            task = step.get("description", step.get("task", ""))
            code = step.get("output", step.get("code", ""))

            if not task:
                task = f"Improve the following code:\n```{self.language}\n{code}\n```"

            verified = self.generate_and_verify(
                task=task,
                max_attempts=max_att,
                language=step.get("language", self.language),
            )
            results.append(verified)

        return {
            "trace_id": trace.get("id", str(uuid.uuid4())),
            "results": [v.to_dict() for v in results],
            "total_steps": len(steps),
            "verified_steps": len(results),
            "all_passed": all(v.passed for v in results) if results else False,
        }


def _extract_code(text: str) -> str:
    """Extract code from markdown code fences or raw text."""
    # Try to extract from ```language\n...\n``` blocks
    import re
    fence_match = re.search(r"```(?:\w+)?\s*\n(.*?)```", text, re.DOTALL)
    if fence_match:
        return fence_match.group(1).strip()

    # No fences found — return the text as-is, stripped
    return text.strip()
