"""Core verification model: ReasonCritic.

Doesn't generate — it flags errors. Takes code as input and produces
structured verification results with confidence scores, issue lists,
and actionable suggestions.
"""

from __future__ import annotations

import json
import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class Verdict(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"


@dataclass
class VerificationResult:
    """Result of verifying a single piece of code."""

    pass_fail: str
    confidence: float
    issues: list[str]
    suggestions: list[str]
    explanation: str = ""
    language: str = "python"
    raw_output: str = ""
    model_name: str = ""

    @property
    def is_pass(self) -> bool:
        return self.pass_fail == Verdict.PASS

    def to_dict(self) -> dict:
        return {
            "pass_fail": self.pass_fail,
            "confidence": self.confidence,
            "issues": self.issues,
            "suggestions": self.suggestions,
            "explanation": self.explanation,
            "language": self.language,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)


@dataclass
class StepVerification:
    """Verification result for a single agent step."""

    step_index: int
    step_type: str
    result: VerificationResult
    step_name: str = ""

    def to_dict(self) -> dict:
        return {
            "step_index": self.step_index,
            "step_type": self.step_type,
            "step_name": self.step_name,
            "result": self.result.to_dict(),
        }


@dataclass
class RunVerification:
    """Verification result for a full agent run."""

    run_id: str
    step_verifications: list[StepVerification]
    overall_verdict: str
    overall_confidence: float
    summary: str = ""

    @property
    def num_passed(self) -> int:
        return sum(1 for sv in self.step_verifications if sv.result.is_pass)

    @property
    def num_failed(self) -> int:
        return sum(1 for sv in self.step_verifications if not sv.result.is_pass)

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "step_verifications": [sv.to_dict() for sv in self.step_verifications],
            "overall_verdict": self.overall_verdict,
            "overall_confidence": self.overall_confidence,
            "num_passed": self.num_passed,
            "num_failed": self.num_failed,
            "summary": self.summary,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)


class CriticBackend(ABC):
    """Abstract base class for verification backends."""

    @abstractmethod
    def verify(self, code: str, context: str = "", language: str = "python") -> VerificationResult:
        ...

    @abstractmethod
    def batch_verify(self, items: list[dict]) -> list[VerificationResult]:
        ...


class LocalBackend(CriticBackend):
    """Local model backend using transformers."""

    def __init__(self, model_name_or_path: str = "Qwen/Qwen3-7B", device: str = "auto"):
        self.model_name = model_name_or_path
        self.device = device
        self._model = None
        self._tokenizer = None

    def _load(self):
        if self._model is not None:
            return

        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        logger.info(f"Loading local model: {self.model_name}")
        self._tokenizer = AutoTokenizer.from_pretrained(self.model_name, trust_remote_code=True)
        self._model = AutoModelForCausalLM.from_pretrained(
            self.model_name,
            torch_dtype=torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16,
            device_map=self.device,
            trust_remote_code=True,
        )
        self._model.eval()

    def verify(self, code: str, context: str = "", language: str = "python") -> VerificationResult:
        import torch

        self._load()

        prompt = _build_prompt(code, context, language)
        inputs = self._tokenizer(prompt, return_tensors="pt").to(self._model.device)

        with torch.no_grad():
            outputs = self._model.generate(
                **inputs,
                max_new_tokens=512,
                temperature=0.1,
                do_sample=False,
                pad_token_id=self._tokenizer.eos_token_id,
            )

        decoded = self._tokenizer.decode(outputs[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True)
        return _parse_output(decoded, language, self.model_name)

    def batch_verify(self, items: list[dict]) -> list[VerificationResult]:
        results = []
        for item in items:
            result = self.verify(
                code=item.get("code", ""),
                context=item.get("context", ""),
                language=item.get("language", "python"),
            )
            results.append(result)
        return results


class APIBackend(CriticBackend):
    """API backend that calls a remote verification service."""

    def __init__(self, endpoint: str, api_key: str = "", timeout: int = 30):
        self.endpoint = endpoint.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    def verify(self, code: str, context: str = "", language: str = "python") -> VerificationResult:
        import httpx

        payload = {"code": code, "context": context, "language": language}
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        response = httpx.post(
            f"{self.endpoint}/verify",
            json=payload,
            headers=headers,
            timeout=self.timeout,
        )
        response.raise_for_status()
        data = response.json()

        return VerificationResult(
            pass_fail=data.get("pass_fail", "FAIL"),
            confidence=data.get("confidence", 0.0),
            issues=data.get("issues", []),
            suggestions=data.get("suggestions", []),
            explanation=data.get("explanation", ""),
            language=language,
            model_name=data.get("model_name", self.endpoint),
        )

    def batch_verify(self, items: list[dict]) -> list[VerificationResult]:
        import httpx

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        response = httpx.post(
            f"{self.endpoint}/verify/batch",
            json={"items": items},
            headers=headers,
            timeout=self.timeout * len(items),
        )
        response.raise_for_status()
        data = response.json()

        return [
            VerificationResult(
                pass_fail=r.get("pass_fail", "FAIL"),
                confidence=r.get("confidence", 0.0),
                issues=r.get("issues", []),
                suggestions=r.get("suggestions", []),
                explanation=r.get("explanation", ""),
                language=r.get("language", "python"),
            )
            for r in data.get("results", [])
        ]


class HybridBackend(CriticBackend):
    """Hybrid backend: tries local first, falls back to API."""

    def __init__(self, local: LocalBackend, api: APIBackend, local_confidence_threshold: float = 0.7):
        self.local = local
        self.api = api
        self.threshold = local_confidence_threshold

    def verify(self, code: str, context: str = "", language: str = "python") -> VerificationResult:
        result = self.local.verify(code, context, language)
        if result.confidence >= self.threshold:
            return result

        logger.info(f"Local confidence {result.confidence:.2f} < {self.threshold}, falling back to API")
        return self.api.verify(code, context, language)

    def batch_verify(self, items: list[dict]) -> list[VerificationResult]:
        results = self.local.batch_verify(items)
        low_confidence_indices = [i for i, r in enumerate(results) if r.confidence < self.threshold]

        if low_confidence_indices:
            api_items = [items[i] for i in low_confidence_indices]
            api_results = self.api.batch_verify(api_items)
            for idx, api_result in zip(low_confidence_indices, api_results):
                results[idx] = api_result

        return results


class ReasonCritic:
    """Self-verification model that critiques agent output.

    ReasonCritic doesn't generate — it flags errors. Given code, a
    step, or a full agent run, it produces structured verification
    results with confidence scores and actionable suggestions.

    Supported backends:
    - "local": Load model locally via transformers
    - "api": Call a remote verification API
    - "hybrid": Try local first, fall back to API for low confidence

    Usage:
        critic = ReasonCritic(backend="local", model_name="reason-critic-7b")
        result = critic.verify("def add(a, b): return a + b")
        print(result.pass_fail)  # "PASS" or "FAIL"
    """

    def __init__(
        self,
        backend: str = "local",
        model_name: str = "Qwen/Qwen3-7B",
        device: str = "auto",
        api_endpoint: str = "",
        api_key: str = "",
        local_confidence_threshold: float = 0.7,
    ):
        self.backend_name = backend
        self.model_name = model_name

        if backend == "local":
            self._backend = LocalBackend(model_name, device)
        elif backend == "api":
            if not api_endpoint:
                raise ValueError("api_endpoint required for API backend")
            self._backend = APIBackend(api_endpoint, api_key)
        elif backend == "hybrid":
            local = LocalBackend(model_name, device)
            if not api_endpoint:
                raise ValueError("api_endpoint required for hybrid backend")
            api = APIBackend(api_endpoint, api_key)
            self._backend = HybridBackend(local, api, local_confidence_threshold)
        else:
            raise ValueError(f"Unknown backend: {backend}. Use 'local', 'api', or 'hybrid'.")

    def verify(
        self,
        code: str,
        context: str = "",
        language: str = "python",
    ) -> VerificationResult:
        """Verify a piece of code.

        Args:
            code: The source code to verify.
            context: Optional surrounding context or task description.
            language: Programming language of the code.

        Returns:
            VerificationResult with pass/fail, confidence, issues, and suggestions.
        """
        if not code.strip():
            return VerificationResult(
                pass_fail=Verdict.FAIL,
                confidence=1.0,
                issues=["Empty code provided"],
                suggestions=["Provide non-empty code to verify"],
                explanation="No code was provided for verification.",
                language=language,
            )

        result = self._backend.verify(code, context, language)
        return result

    def verify_step(
        self,
        step: dict,
        context: str = "",
    ) -> StepVerification:
        """Verify a single agent step.

        Args:
            step: A step dict with keys like 'index', 'type', 'code', 'name'.
            context: Optional context about the overall task.

        Returns:
            StepVerification wrapping a VerificationResult.
        """
        code = step.get("code", step.get("content", step.get("output", "")))
        language = step.get("language", _detect_language(code))

        result = self.verify(code, context, language)

        return StepVerification(
            step_index=step.get("index", 0),
            step_type=step.get("type", "unknown"),
            step_name=step.get("name", ""),
            result=result,
        )

    def verify_run(
        self,
        run: dict,
        context: str = "",
    ) -> RunVerification:
        """Verify a full agent run (all steps).

        Args:
            run: A run dict with 'id' and 'steps' keys.
            context: Optional context about the task.

        Returns:
            RunVerification with per-step results and overall verdict.
        """
        steps = run.get("steps", [])
        run_id = run.get("id", "unknown")

        step_verifications = []
        for step in steps:
            sv = self.verify_step(step, context)
            step_verifications.append(sv)

        if not step_verifications:
            return RunVerification(
                run_id=run_id,
                step_verifications=[],
                overall_verdict=Verdict.FAIL,
                overall_confidence=1.0,
                summary="No steps found in the run.",
            )

        num_passed = sum(1 for sv in step_verifications if sv.result.is_pass)
        num_total = len(step_verifications)
        avg_confidence = sum(sv.result.confidence for sv in step_verifications) / num_total

        overall = Verdict.PASS if num_passed == num_total else Verdict.FAIL

        failed_steps = [
            f"Step {sv.step_index} ({sv.step_name or sv.step_type}): {sv.result.issues}"
            for sv in step_verifications
            if not sv.result.is_pass
        ]

        summary = f"{num_passed}/{num_total} steps passed."
        if failed_steps:
            summary += f" Failed: {'; '.join(failed_steps[:3])}"
            if len(failed_steps) > 3:
                summary += f" ... and {len(failed_steps) - 3} more."

        return RunVerification(
            run_id=run_id,
            step_verifications=step_verifications,
            overall_verdict=overall,
            overall_confidence=avg_confidence,
            summary=summary,
        )

    def batch_verify(self, items: list[dict]) -> list[VerificationResult]:
        """Verify multiple code snippets in batch.

        Args:
            items: List of dicts with 'code', 'context', 'language' keys.

        Returns:
            List of VerificationResults.
        """
        return self._backend.batch_verify(items)


def _build_prompt(code: str, context: str, language: str) -> str:
    """Build a verification prompt for the model."""
    prompt = "You are a code verification critic. Analyze the following code and determine if it is correct or contains bugs.\n\n"

    if context:
        prompt += f"Context: {context}\n\n"

    prompt += f"Language: {language}\n\n"
    prompt += f"```{language}\n{code}\n```\n\n"
    prompt += (
        "Respond in this exact format:\n"
        "VERDICT: [PASS or FAIL]\n"
        "CONFIDENCE: [0.0 to 1.0]\n"
        "ISSUES: [comma-separated list of issues, or 'none' if PASS]\n"
        "SUGGESTIONS: [comma-separated list of suggestions, or 'none' if PASS]\n"
        "EXPLANATION: [brief explanation]\n"
    )
    return prompt


def _parse_output(output: str, language: str = "python", model_name: str = "") -> VerificationResult:
    """Parse model output into a VerificationResult."""
    verdict = Verdict.FAIL
    confidence = 0.5
    issues = []
    suggestions = []
    explanation = ""

    verdict_match = re.search(r"VERDICT:\s*(PASS|FAIL)", output, re.IGNORECASE)
    if verdict_match:
        verdict = verdict_match.group(1).upper()

    confidence_match = re.search(r"CONFIDENCE:\s*([\d.]+)", output)
    if confidence_match:
        try:
            confidence = min(1.0, max(0.0, float(confidence_match.group(1))))
        except ValueError:
            confidence = 0.5

    issues_match = re.search(r"ISSUES:\s*(.+?)(?:\n|SUGGESTIONS:|$)", output, re.IGNORECASE)
    if issues_match:
        issues_text = issues_match.group(1).strip()
        if issues_text.lower() not in ("none", "n/a", "no issues", ""):
            issues = [i.strip() for i in issues_text.split(",") if i.strip()]

    suggestions_match = re.search(r"SUGGESTIONS:\s*(.+?)(?:\n|EXPLANATION:|$)", output, re.IGNORECASE)
    if suggestions_match:
        suggestions_text = suggestions_match.group(1).strip()
        if suggestions_text.lower() not in ("none", "n/a", "no suggestions", ""):
            suggestions = [s.strip() for s in suggestions_text.split(",") if s.strip()]

    explanation_match = re.search(r"EXPLANATION:\s*(.+)", output, re.IGNORECASE | re.DOTALL)
    if explanation_match:
        explanation = explanation_match.group(1).strip()

    if not issues and verdict == Verdict.FAIL and not explanation:
        explanation = output.strip()

    return VerificationResult(
        pass_fail=verdict,
        confidence=confidence,
        issues=issues,
        suggestions=suggestions,
        explanation=explanation,
        language=language,
        raw_output=output,
        model_name=model_name,
    )


def _detect_language(code: str) -> str:
    """Quick heuristic language detection."""
    if "def " in code or "import " in code:
        return "python"
    if "function " in code or "const " in code or "=>" in code:
        return "javascript"
    if "fn " in code and ("let " in code or "mut " in code):
        return "rust"
    if "func " in code and "package " in code:
        return "go"
    return "python"
