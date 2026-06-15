"""Evaluate distilled skill adapters against base model performance.

Loads base model + LoRA adapter, runs benchmark tasks for each skill,
compares base vs adapted performance, and generates an evaluation report.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from trace_compiler.skill_extractor import SkillType

logger = logging.getLogger(__name__)


@dataclass
class BenchmarkResult:
    skill_type: SkillType
    task_name: str
    base_score: float
    adapted_score: float
    improvement: float
    base_latency_ms: float = 0.0
    adapted_latency_ms: float = 0.0
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "skill_type": self.skill_type.value,
            "task_name": self.task_name,
            "base_score": self.base_score,
            "adapted_score": self.adapted_score,
            "improvement": self.improvement,
            "base_latency_ms": self.base_latency_ms,
            "adapted_latency_ms": self.adapted_latency_ms,
            "details": self.details,
        }


@dataclass
class EvaluationReport:
    model_name: str
    adapter_path: str
    results: list[BenchmarkResult] = field(default_factory=list)
    overall_base_score: float = 0.0
    overall_adapted_score: float = 0.0
    overall_improvement: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_name": self.model_name,
            "adapter_path": self.adapter_path,
            "results": [r.to_dict() for r in self.results],
            "overall_base_score": self.overall_base_score,
            "overall_adapted_score": self.overall_adapted_score,
            "overall_improvement": self.overall_improvement,
        }

    def save(self, path: Path | str) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)
        logger.info("Evaluation report saved to %s", path)


BENCHMARK_PROMPTS: dict[SkillType, list[dict[str, str]]] = {
    SkillType.DEBUG: [
        {
            "input": "I'm getting a KeyError: 'user_id' in my Flask app. The traceback shows it's in line 45 of routes.py. How do I fix this?",
            "criteria": ["identifies_keyerror", "suggests_fix", "explains_root_cause"],
        },
        {
            "input": "My React component throws 'Cannot read property of undefined' when the API returns null. How should I handle this?",
            "criteria": ["identifies_null_issue", "suggests_null_check", "provides_fix"],
        },
        {
            "input": "The test suite fails with AssertionError: expected 200 but got 403. The endpoint requires auth. What's going wrong?",
            "criteria": ["identifies_auth_issue", "suggests_auth_fix", "explains_403"],
        },
    ],
    SkillType.EDIT: [
        {
            "input": "Change the function `get_user` to also return the user's email address.",
            "criteria": ["makes_minimal_edit", "preserves_existing_behavior", "correct_syntax"],
        },
        {
            "input": "Refactor the nested if-else into a switch statement in the handleRequest function.",
            "criteria": ["correct_refactor", "preserves_logic", "clean_code"],
        },
        {
            "input": "Add input validation to the `create_order` function — quantities must be positive integers.",
            "criteria": ["adds_validation", "preserves_existing_logic", "returns_clear_error"],
        },
    ],
    SkillType.VERIFY: [
        {
            "input": "I just added an index to the users table. How should I verify it works correctly?",
            "criteria": ["suggests_query_plan", "checks_index_usage", "verifies_performance"],
        },
        {
            "input": "After deploying the auth fix, how do I verify login works for all user roles?",
            "criteria": ["suggests_test_cases", "covers_edge_cases", "systematic_verification"],
        },
    ],
    SkillType.RECOVER: [
        {
            "input": "The deployment failed with 'port 8080 already in use'. The service won't start. How do I recover?",
            "criteria": ["identifies_port_conflict", "suggests_recovery_steps", "prevents_recurrence"],
        },
        {
            "input": "After a disk-full error, the database won't start. How do I recover the data and get it running?",
            "criteria": ["diagnoses_disk_issue", "recovery_steps", "data_safety"],
        },
    ],
    SkillType.PLAN: [
        {
            "input": "We need to migrate from PostgreSQL to MySQL. Create a migration plan.",
            "criteria": ["structured_plan", "identifies_risks", "sequenced_steps"],
        },
        {
            "input": "We're adding multi-tenant support to the SaaS app. Plan the implementation.",
            "criteria": ["clear_plan", "identifies_dependencies", "prioritized_steps"],
        },
    ],
}


class Evaluator:
    def __init__(
        self,
        model_name: str = "Qwen/Qwen2.5-Coder-1.5B",
        adapter_path: str | None = None,
        device: str | None = None,
    ) -> None:
        self.model_name = model_name
        self.adapter_path = adapter_path
        self.device = device
        self._base_model = None
        self._base_tokenizer = None
        self._adapted_model = None
        self._adapted_tokenizer = None

    def _load_base_model(self) -> tuple[Any, Any]:
        if self._base_model is not None:
            return self._base_model, self._base_tokenizer

        from transformers import AutoModelForCausalLM, AutoTokenizer

        logger.info("Loading base model: %s", self.model_name)
        tokenizer = AutoTokenizer.from_pretrained(self.model_name)
        model = AutoModelForCausalLM.from_pretrained(
            self.model_name,
            device_map=self.device or "auto",
            torch_dtype="auto",
        )
        self._base_model = model
        self._base_tokenizer = tokenizer
        return model, tokenizer

    def _load_adapted_model(self) -> tuple[Any, Any]:
        if self._adapted_model is not None:
            return self._adapted_model, self._adapted_tokenizer

        from peft import PeftModel
        from transformers import AutoModelForCausalLM, AutoTokenizer

        logger.info("Loading base model for adapter: %s", self.model_name)
        tokenizer = AutoTokenizer.from_pretrained(self.model_name)
        model = AutoModelForCausalLM.from_pretrained(
            self.model_name,
            device_map=self.device or "auto",
            torch_dtype="auto",
        )

        if self.adapter_path:
            logger.info("Loading LoRA adapter from: %s", self.adapter_path)
            model = PeftModel.from_pretrained(model, self.adapter_path)

        self._adapted_model = model
        self._adapted_tokenizer = tokenizer
        return model, tokenizer

    def _generate(
        self,
        model: Any,
        tokenizer: Any,
        prompt: str,
        max_new_tokens: int = 512,
        temperature: float = 0.7,
    ) -> tuple[str, float]:
        messages = [
            {"role": "system", "content": "You are a skilled coding assistant."},
            {"role": "user", "content": prompt},
        ]
        text = tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        inputs = tokenizer(text, return_tensors="pt").to(model.device)

        start = time.time()
        with __import__("torch").no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                temperature=temperature,
                do_sample=True,
                top_p=0.95,
            )
        latency_ms = (time.time() - start) * 1000

        generated_ids = outputs[0][inputs["input_ids"].shape[1]:]
        response = tokenizer.decode(generated_ids, skip_special_tokens=True)
        return response, latency_ms

    def _score_response(
        self,
        response: str,
        criteria: list[str],
        skill_type: SkillType,
    ) -> float:
        response_lower = response.lower()
        scores: list[float] = []

        criteria_keywords: dict[str, list[str]] = {
            "identifies_keyerror": ["keyerror", "key error", "missing key", "dictionary key"],
            "suggests_fix": ["fix", "solution", "resolve", "change to", "use .get", "try"],
            "explains_root_cause": ["because", "reason", "caused by", "due to", "root cause"],
            "identifies_null_issue": ["null", "undefined", "none", "optional"],
            "suggests_null_check": ["null check", "optional chaining", "?.", "default value", "fallback"],
            "provides_fix": ["fix", "change", "update", "modify", "replace"],
            "identifies_auth_issue": ["auth", "permission", "forbidden", "token", "session"],
            "suggests_auth_fix": ["add auth", "token", "header", "credential", "login"],
            "explains_403": ["forbidden", "403", "permission", "unauthorized"],
            "makes_minimal_edit": ["change", "add", "only", "just", "simply"],
            "preserves_existing_behavior": ["keep", "maintain", "preserve", "existing", "still"],
            "correct_syntax": ["def ", "function", "return", "class ", "=>"],
            "correct_refactor": ["switch", "case", "match", "if", "elif", "refactor"],
            "preserves_logic": ["same logic", "equivalent", "same behavior", "preserves"],
            "clean_code": ["clean", "readable", "clear", "simple"],
            "adds_validation": ["validate", "check", "verify", "assert", "if not", "guard"],
            "returns_clear_error": ["error", "raise", "throw", "exception", "invalid"],
            "suggests_query_plan": ["explain", "query plan", "index", "scan"],
            "checks_index_usage": ["index", "seek", "scan", "explain analyze"],
            "verifies_performance": ["performance", "latency", "speed", "benchmark", "measure"],
            "suggests_test_cases": ["test", "verify", "check", "assert", "should"],
            "covers_edge_cases": ["edge case", "boundary", "corner", "empty", "null"],
            "systematic_verification": ["step", "systematic", "checklist", "verify each"],
            "identifies_port_conflict": ["port", "conflict", "in use", "already running", "process"],
            "suggests_recovery_steps": ["restart", "kill", "stop", "redeploy", "free port"],
            "prevents_recurrence": ["persist", "prevent", "monitor", "healthcheck", "systemd"],
            "diagnoses_disk_issue": ["disk", "space", "full", "storage", "capacity"],
            "recovery_steps": ["clean", "purge", "vacuum", "remove", "free space"],
            "data_safety": ["backup", "safety", "preserve data", "don't delete", "export"],
            "structured_plan": ["phase", "step", "stage", "milestone", "timeline"],
            "identifies_risks": ["risk", "concern", "caveat", "issue", "challenge"],
            "sequenced_steps": ["1.", "2.", "3.", "first", "then", "finally"],
            "clear_plan": ["plan", "strategy", "approach", "roadmap"],
            "identifies_dependencies": ["depend", "require", "prerequisite", "blocking"],
            "prioritized_steps": ["priority", "critical", "important", "first", "must"],
        }

        for criterion in criteria:
            keywords = criteria_keywords.get(criterion, [criterion.replace("_", " ")])
            match_count = sum(1 for kw in keywords if kw in response_lower)
            if match_count > 0:
                scores.append(min(match_count / len(keywords), 1.0))
            else:
                scores.append(0.0)

        if not scores:
            return 0.0
        return sum(scores) / len(scores)

    def evaluate_skill(
        self,
        skill_type: SkillType,
        custom_prompts: list[dict[str, Any]] | None = None,
        max_new_tokens: int = 512,
    ) -> list[BenchmarkResult]:
        prompts = custom_prompts or BENCHMARK_PROMPTS.get(skill_type, [])
        if not prompts:
            logger.warning("No benchmark prompts for skill type: %s", skill_type.value)
            return []

        base_model, base_tokenizer = self._load_base_model()
        adapted_model, adapted_tokenizer = self._load_adapted_model()

        results: list[BenchmarkResult] = []
        for i, prompt_data in enumerate(prompts):
            input_text = prompt_data.get("input", prompt_data.get("prompt", ""))
            criteria = prompt_data.get("criteria", [])

            task_name = f"{skill_type.value}_task_{i + 1}"

            logger.info("Evaluating task: %s", task_name)

            base_response, base_latency = self._generate(
                base_model, base_tokenizer, input_text, max_new_tokens=max_new_tokens
            )
            adapted_response, adapted_latency = self._generate(
                adapted_model, adapted_tokenizer, input_text, max_new_tokens=max_new_tokens
            )

            base_score = self._score_response(base_response, criteria, skill_type)
            adapted_score = self._score_response(adapted_response, criteria, skill_type)
            improvement = adapted_score - base_score

            results.append(BenchmarkResult(
                skill_type=skill_type,
                task_name=task_name,
                base_score=base_score,
                adapted_score=adapted_score,
                improvement=improvement,
                base_latency_ms=base_latency,
                adapted_latency_ms=adapted_latency,
                details={
                    "base_response_preview": base_response[:200],
                    "adapted_response_preview": adapted_response[:200],
                    "criteria": criteria,
                },
            ))

        return results

    def evaluate(
        self,
        skill_types: list[SkillType] | None = None,
        output_path: str | None = None,
    ) -> EvaluationReport:
        if skill_types is None:
            skill_types = [SkillType.DEBUG, SkillType.EDIT, SkillType.VERIFY]

        all_results: list[BenchmarkResult] = []

        for st in skill_types:
            logger.info("=== Evaluating skill: %s ===", st.value)
            results = self.evaluate_skill(st)
            all_results.extend(results)

        base_scores = [r.base_score for r in all_results]
        adapted_scores = [r.adapted_score for r in all_results]

        report = EvaluationReport(
            model_name=self.model_name,
            adapter_path=self.adapter_path or "none",
            results=all_results,
            overall_base_score=sum(base_scores) / len(base_scores) if base_scores else 0.0,
            overall_adapted_score=sum(adapted_scores) / len(adapted_scores) if adapted_scores else 0.0,
            overall_improvement=(
                (sum(adapted_scores) - sum(base_scores)) / len(base_scores)
                if base_scores
                else 0.0
            ),
        )

        if output_path:
            report.save(Path(output_path))

        return report
