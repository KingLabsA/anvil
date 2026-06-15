"""Verify phase: check execution results with trained verification model.

This is THE KEY DIFFERENTIATOR. Unlike other agent frameworks that rely on
LLM prompts for verification, VerifyLoop uses a trained ReasonCritic model
when available, falling back to LLM-based verification otherwise.
"""

from __future__ import annotations

import json
import re

import litellm

from verifyloop.models import (
    ExecuteStep,
    PlanStep,
    TokenUsage,
    VerifyCheckResult,
    VerifyStep,
)

VERIFY_SYSTEM_PROMPT = """You are a verification agent. Given a plan, execution results, and the original task, verify whether the task was completed correctly.

Produce a JSON object:
{
  "checks": ["Description of each verification check performed"],
  "check_results": [
    {"check": "description", "passed": true/false, "detail": "reasoning"}
  ],
  "passed": true/false,
  "confidence": 0.0-1.0,
  "failures": ["List of failures if any"],
  "fix_suggestions": ["Suggested fixes for each failure"]
}

Be thorough. Check:
1. Did every substep succeed?
2. Are the actual outputs consistent with what was expected?
3. Do files contain the expected content or structure?
4. Are there any syntax errors or obvious bugs in generated code?
5. Would the changes break existing functionality?

Respond ONLY with valid JSON, no markdown fences."""

REASON_CRITIC_PROMPT = """You are ReasonCritic, a specialized verification model trained to evaluate code changes and execution results.

Analyze the plan-execution pair for:
- Logical consistency between plan and execution
- Correctness of code changes (syntax, semantics)
- Completeness: were all substeps addressed?
- Edge cases: potential runtime errors
- Test coverage considerations

Output JSON:
{
  "checks": ["verification checks performed"],
  "check_results": [{"check": "...", "passed": bool, "detail": "..."}],
  "passed": bool,
  "confidence": float 0.0-1.0,
  "failures": ["list of failures"],
  "fix_suggestions": ["list of fix suggestions"]
}

Respond ONLY with valid JSON."""


class VerifierConfig:
    def __init__(
        self,
        verify_model: str = "reason-critic-7b",
        confidence_threshold: float = 0.8,
        api_key: str | None = None,
        api_base: str | None = None,
        prefer_trained_model: bool = True,
        max_retries: int = 2,
    ) -> None:
        self.verify_model = verify_model
        self.confidence_threshold = confidence_threshold
        self.api_key = api_key
        self.api_base = api_base
        self.prefer_trained_model = prefer_trained_model
        self.max_retries = max_retries


class Verifier:
    def __init__(self, config: VerifierConfig | None = None) -> None:
        self.config = config or VerifierConfig()
        self._token_usage = TokenUsage()
        self._trained_model_available: bool | None = None

    @property
    def token_usage(self) -> TokenUsage:
        return self._token_usage

    async def verify_code_edits(
        self,
        plan: PlanStep,
        execute_steps: list[ExecuteStep],
    ) -> VerifyStep:
        executed_summary = self._summarize_executions(execute_steps)
        prompt = self._build_verification_prompt(
            task=plan.description,
            plan_substeps=plan.substeps,
            executions=executed_summary,
        )
        return await self._run_verification(prompt, plan=plan, execute_steps=execute_steps)

    async def verify_bash_output(
        self,
        command: str,
        output: str,
        expected: str | None = None,
    ) -> VerifyStep:
        checks = [f"Command '{command}' executed successfully"]
        if output.strip():
            checks.append("Command produced output")
        if expected:
            checks.append(f"Output matches expected: {expected[:100]}")

        prompt = f"Verify bash command execution:\n\nCommand: {command}\nOutput:\n{output}\n"
        if expected:
            prompt += f"\nExpected output contains: {expected}\n"

        return await self._run_verification(prompt, checks=checks)

    async def verify_file_state(
        self,
        file_path: str,
        expected_content: str | None = None,
        should_exist: bool = True,
    ) -> VerifyStep:
        from pathlib import Path

        target = Path(file_path)
        checks = [f"File {file_path} {'exists' if should_exist else 'should not exist'}"]

        if target.exists() != should_exist:
            return VerifyStep(
                checks=checks,
                passed=False,
                confidence=1.0,
                failures=[f"File {file_path} {'does not exist' if should_exist else 'exists unexpectedly'}"],
                fix_suggestions=[
                    f"Create the file {file_path}" if should_exist else f"Remove the file {file_path}"
                ],
                verification_model=self.config.verify_model,
                used_trained_model=False,
            )

        if expected_content and target.exists():
            actual = target.read_text()
            if expected_content in actual:
                checks.append("File contains expected content")
            else:
                checks.append("File content mismatch")
                return VerifyStep(
                    checks=checks,
                    passed=False,
                    confidence=0.9,
                    failures=[f"File {file_path} does not contain expected content"],
                    fix_suggestions=[f"Edit {file_path} to include: {expected_content[:100]}..."],
                    verification_model=self.config.verify_model,
                    used_trained_model=False,
                )

        return VerifyStep(
            checks=checks,
            passed=True,
            confidence=1.0,
            verification_model="local",
            used_trained_model=False,
        )

    async def verify_tests(
        self,
        test_command: str,
        working_dir: str = ".",
    ) -> VerifyStep:
        import asyncio as _asyncio

        proc = await _asyncio.create_subprocess_shell(
            test_command,
            stdout=_asyncio.subprocess.PIPE,
            stderr=_asyncio.subprocess.PIPE,
            cwd=working_dir,
        )
        stdout, stderr = await _asyncio.wait_for(proc.communicate(), timeout=120)

        passed = proc.returncode == 0
        output = stdout.decode(errors="replace")
        errors = stderr.decode(errors="replace")

        checks = [f"Test command: {test_command}", f"Exit code: {proc.returncode}"]
        failures = []
        fix_suggestions = []

        if passed:
            checks.append("All tests passed")
        else:
            checks.append("Tests failed")
            failures.append(f"Test suite returned exit code {proc.returncode}")
            failures.extend(self._extract_failure_lines(output + "\n" + errors))
            fix_suggestions.extend(self._suggest_test_fixes(output + "\n" + errors))

        return VerifyStep(
            checks=checks,
            passed=passed,
            confidence=1.0 if passed else 0.3,
            failures=failures,
            fix_suggestions=fix_suggestions,
            verification_model="local",
            used_trained_model=False,
        )

    async def _run_verification(
        self,
        prompt: str,
        plan: PlanStep | None = None,
        execute_steps: list[ExecuteStep] | None = None,
        checks: list[str] | None = None,
    ) -> VerifyStep:
        if self.config.prefer_trained_model and await self._check_trained_model():
            result = await self._verify_with_trained_model(prompt)
            if result is not None:
                return result

        return await self._verify_with_llm(prompt)

    async def _check_trained_model(self) -> bool:
        if self._trained_model_available is not None:
            return self._trained_model_available

        try:
            test_response = await litellm.acompletion(
                model=self.config.verify_model,
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=5,
                api_key=self.config.api_key,
                api_base=self.config.api_base,
            )
            self._trained_model_available = True
            return True
        except Exception:
            self._trained_model_available = False
            return False

    async def _verify_with_trained_model(self, prompt: str) -> VerifyStep | None:
        try:
            response = await litellm.acompletion(
                model=self.config.verify_model,
                messages=[
                    {"role": "system", "content": REASON_CRITIC_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.0,
                max_tokens=2048,
                api_key=self.config.api_key,
                api_base=self.config.api_base,
            )
            self._token_usage = self._token_usage.merge(
                TokenUsage(
                    prompt_tokens=response.usage.prompt_tokens if response.usage else 0,
                    completion_tokens=response.usage.completion_tokens if response.usage else 0,
                    total_tokens=response.usage.total_tokens if response.usage else 0,
                )
            )
            return self._parse_verification_response(
                response.choices[0].message.content or "{}",
                used_trained_model=True,
            )
        except Exception:
            return None

    async def _verify_with_llm(self, prompt: str) -> VerifyStep:
        fallback_model = self.config.verify_model
        if await self._check_trained_model() is False:
            fallback_model = "gpt-4o"

        response = await litellm.acompletion(
            model=fallback_model,
            messages=[
                {"role": "system", "content": VERIFY_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.0,
            max_tokens=2048,
            api_key=self.config.api_key,
            api_base=self.config.api_base,
        )
        self._token_usage = self._token_usage.merge(
            TokenUsage(
                prompt_tokens=response.usage.prompt_tokens if response.usage else 0,
                completion_tokens=response.usage.completion_tokens if response.usage else 0,
                total_tokens=response.usage.total_tokens if response.usage else 0,
            )
        )
        return self._parse_verification_response(
            response.choices[0].message.content or "{}",
            used_trained_model=False,
        )

    def _parse_verification_response(
        self, content: str, used_trained_model: bool = False
    ) -> VerifyStep:
        content = re.sub(r"^```(?:json)?\s*", "", content.strip())
        content = re.sub(r"\s*```$", "", content.strip())
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            return VerifyStep(
                checks=["Failed to parse verification response"],
                passed=False,
                confidence=0.0,
                failures=["Verification model returned invalid JSON"],
                fix_suggestions=["Retry verification"],
                verification_model=self.config.verify_model,
                used_trained_model=used_trained_model,
            )

        check_results = []
        for cr in data.get("check_results", []):
            check_results.append(VerifyCheckResult(
                check=cr.get("check", ""),
                passed=cr.get("passed", False),
                detail=cr.get("detail", ""),
            ))

        return VerifyStep(
            checks=data.get("checks", []),
            check_results=check_results,
            passed=data.get("passed", False),
            confidence=data.get("confidence", 0.0),
            failures=data.get("failures", []),
            fix_suggestions=data.get("fix_suggestions", []),
            verification_model=self.config.verify_model,
            used_trained_model=used_trained_model,
        )

    def _summarize_executions(self, steps: list[ExecuteStep]) -> str:
        lines = []
        for i, step in enumerate(steps, 1):
            status = "SUCCESS" if step.success else "FAILED"
            result_preview = step.result[:500] if step.result else "(no output)"
            error_info = f"\nError: {step.error}" if step.error else ""
            lines.append(
                f"Step {i} [{step.tool}] {status}:\n"
                f"  Args: {step.arguments}\n"
                f"  Result: {result_preview}{error_info}"
            )
        return "\n\n".join(lines)

    def _build_verification_prompt(
        self,
        task: str,
        plan_substeps: list[str],
        executions: str,
    ) -> str:
        substep_text = "\n".join(f"  {i+1}. {s}" for i, s in enumerate(plan_substeps))
        return (
            f"Original Task: {task}\n\n"
            f"Plan Substeps:\n{substep_text}\n\n"
            f"Execution Results:\n{executions}\n\n"
            f"Verify whether the task was completed correctly and all substeps were addressed."
        )

    @staticmethod
    def _extract_failure_lines(output: str) -> list[str]:
        failures = []
        for line in output.splitlines():
            stripped = line.strip()
            if any(stripped.startswith(prefix) for prefix in ("FAILED", "ERROR", "AssertionError", "FAIL")):
                failures.append(stripped[:200])
        return failures[:10]

    @staticmethod
    def _suggest_test_fixes(output: str) -> list[str]:
        suggestions = []
        if "import" in output and "ModuleNotFoundError" in output:
            suggestions.append("Missing import — install the required package or add the module")
        if "AssertionError" in output:
            suggestions.append("Assertion failed — review expected vs actual values in the test")
        if "TypeError" in output:
            suggestions.append("Type error — check function signatures and argument types")
        if "NameError" in output:
            suggestions.append("Name error — variable or function not defined in scope")
        if not suggestions:
            suggestions.append("Review the failing test output for specific error details")
        return suggestions[:5]
