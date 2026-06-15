"""Prepare verification training data from agent traces.

Data sources:
- Verification phase from v-Fable (62.2% of traces contain verification)
- Error/recovery pairs from Glint (3,725 examples)
"""

from __future__ import annotations

import json
import random
import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class VerificationExample:
    """A single verification training example."""

    prompt: str
    code: str
    label: str
    explanation: str
    language: str = "python"
    source: str = ""
    issues: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)


@dataclass
class ContrastivePair:
    """A correct/incorrect pair for contrastive learning."""

    correct_code: str
    incorrect_code: str
    explanation: str
    bug_type: str = ""
    language: str = "python"


BUG_TEMPLATES = {
    "off_by_one": {
        "description": "Off-by-one error in loop bounds",
        "pattern": r"range\((\d+)\)",
        "transform": lambda m: f"range({int(m.group(1)) - 1})",
    },
    "wrong_operator": {
        "description": "Comparison operator swapped",
        "pattern": r"(\w+)\s*(==)\s*(\w+)",
        "transform_op": "== -> !=",
    },
    "missing_none_check": {
        "description": "Missing None check before attribute access",
        "pattern": r"(\w+)\.(\w+)",
        "transform_fn": "add_none_check",
    },
    "forgotten_await": {
        "description": "Missing await on async call",
        "pattern": r"(\w+)\s*=\s*(async\s+)?(\w+)\(",
        "transform_fn": "remove_await",
    },
    "mutable_default": {
        "description": "Mutable default argument",
        "pattern": r"def\s+(\w+)\s*\(([^)]*[\[\]]\s*=\s*(\[\]|\{\})[^)]*)\)",
        "transform_fn": "keep_mutable_default",
    },
    "shadowed_variable": {
        "description": "Variable shadowing in inner scope",
        "pattern": r"(\w+)\s*=\s*.+",
        "transform_fn": "shadow_variable",
    },
}


def extract_verification_pairs(traces: list[dict]) -> list[VerificationExample]:
    """Extract (code, pass/fail) pairs from verification phases in traces.

    Scans agent traces for verification steps — phases where the agent
    checks its own work — and extracts the code being verified along
    with the outcome.

    Args:
        traces: List of agent trace dictionaries. Each trace should have
                a 'steps' key with a list of step dicts, some of which
                may have 'type': 'verification'.

    Returns:
        List of VerificationExample instances from verification phases.
    """
    examples = []

    for trace in traces:
        steps = trace.get("steps", [])
        for step in steps:
            if step.get("type") != "verification":
                continue

            code = step.get("code", "") or step.get("content", "")
            if not code:
                continue

            result = step.get("result", step.get("outcome", "unknown"))
            if result in ("pass", "success", "correct", True):
                label = "PASS"
            elif result in ("fail", "error", "incorrect", False):
                label = "FAIL"
            else:
                label = "UNKNOWN"

            if label == "UNKNOWN":
                continue

            issues = step.get("issues", [])
            suggestions = step.get("suggestions", [])
            if isinstance(issues, str):
                issues = [issues]
            if isinstance(suggestions, str):
                suggestions = [suggestions]

            examples.append(
                VerificationExample(
                    prompt="Verify this code:",
                    code=code,
                    label=label,
                    explanation=step.get("explanation", step.get("reasoning", "")),
                    language=step.get("language", _detect_language(code)),
                    source=step.get("source", "v-fable"),
                    issues=issues,
                    suggestions=suggestions,
                )
            )

    return examples


def generate_incorrect_versions(
    code: str,
    num_versions: int = 3,
    bug_types: list[str] | None = None,
) -> list[dict]:
    """Generate incorrect versions of code by introducing bugs.

    Applies systematic bug-introduction strategies to produce
    verifiably-wrong versions of input code for contrastive learning.

    Strategies:
    - Off-by-one errors in loop bounds
    - Swapped comparison operators (== vs !=, < vs <=)
    - Missing None/type checks
    - Forgotten await on async calls
    - Mutable default arguments
    - Variable shadowing

    Args:
        code: The correct source code.
        num_versions: How many buggy variants to produce.
        bug_types: Optional list of specific bug types to apply.

    Returns:
        List of dicts with keys: code, bug_type, description, diff_hint.
    """
    results = []
    available_bugs = list(BUG_TEMPLATES.keys())

    if bug_types:
        available_bugs = [b for b in bug_types if b in BUG_TEMPLATES]

    random.shuffle(available_bugs)

    for bug_type in available_bugs[:num_versions]:
        bugged = _apply_bug(code, bug_type)
        if bugged and bugged != code:
            template = BUG_TEMPLATES[bug_type]
            results.append(
                {
                    "code": bugged,
                    "bug_type": bug_type,
                    "description": template["description"],
                    "diff_hint": f"Bug type: {bug_type}",
                }
            )

    if len(results) < num_versions:
        fallback = _apply_line_level_bugs(code, num_versions - len(results))
        results.extend(fallback)

    return results[:num_versions]


def create_contrastive_pairs(
    correct: str,
    incorrect: str | None = None,
) -> ContrastivePair:
    """Create a contrastive pair from correct and incorrect code.

    If only correct code is provided, generates an incorrect version
    automatically using generate_incorrect_versions.

    Args:
        correct: The correct source code.
        incorrect: Optional incorrect version. If None, one is generated.

    Returns:
        A ContrastivePair for contrastive learning.
    """
    if incorrect is None:
        bugged = generate_incorrect_versions(correct, num_versions=1)
        if not bugged:
            return ContrastivePair(
                correct_code=correct,
                incorrect_code=correct + "\n# BUG: unreachable placeholder",
                explanation="Synthetic bug: unreachable code added",
                bug_type="synthetic",
                language=_detect_language(correct),
            )
        incorrect = bugged[0]["code"]
        bug_type = bugged[0]["bug_type"]
        explanation = bugged[0]["description"]
    else:
        bug_type = "provided"
        explanation = "Manually provided incorrect version"

    return ContrastivePair(
        correct_code=correct,
        incorrect_code=incorrect,
        explanation=explanation,
        bug_type=bug_type,
        language=_detect_language(correct),
    )


def load_glint_error_recovery(path: Path | str) -> list[VerificationExample]:
    """Load error/recovery pairs from Glint dataset.

    The Glint dataset contains 3,725 examples of agent errors and
    their recovery attempts. Each example maps to a verification
    training example.

    Args:
        path: Path to the Glint dataset file (JSONL).

    Returns:
        List of VerificationExample from Glint data.
    """
    path = Path(path)
    examples = []

    with open(path) as f:
        for line in f:
            if not line.strip():
                continue
            entry = json.loads(line)

            error_code = entry.get("error_code", entry.get("code", ""))
            recovery = entry.get("recovery", entry.get("fix", ""))
            error_type = entry.get("error_type", "unknown")

            if error_code:
                examples.append(
                    VerificationExample(
                        prompt="Verify this code:",
                        code=error_code,
                        label="FAIL",
                        explanation=entry.get("error_description", f"Error type: {error_type}"),
                        language=_detect_language(error_code),
                        source="glint",
                        issues=[entry.get("error_description", "")],
                        suggestions=[recovery] if recovery else [],
                    )
                )

            if recovery:
                examples.append(
                    VerificationExample(
                        prompt="Verify this code:",
                        code=recovery,
                        label="PASS",
                        explanation="Recovered from previous error",
                        language=_detect_language(recovery),
                        source="glint",
                    )
                )

    return examples


def examples_to_dataset(examples: list[VerificationExample]):
    """Convert VerificationExample list to a HuggingFace Dataset.

    Args:
        examples: List of VerificationExample instances.

    Returns:
        A HuggingFace Dataset ready for training.
    """
    from datasets import Dataset

    return Dataset.from_list(
        [
            {
                "prompt": ex.prompt,
                "code": ex.code,
                "label": ex.label,
                "explanation": ex.explanation,
                "language": ex.language,
                "source": ex.source,
                "issues": json.dumps(ex.issues),
                "suggestions": json.dumps(ex.suggestions),
            }
            for ex in examples
        ]
    )


def pairs_to_dataset(pairs: list[ContrastivePair]):
    """Convert ContrastivePair list to a HuggingFace Dataset.

    Args:
        pairs: List of ContrastivePair instances.

    Returns:
        A HuggingFace Dataset with preferred/dispreferred columns for DPO.
    """
    from datasets import Dataset

    return Dataset.from_list(
        [
            {
                "preferred": pair.correct_code,
                "dispreferred": pair.incorrect_code,
                "explanation": pair.explanation,
                "bug_type": pair.bug_type,
                "language": pair.language,
            }
            for pair in pairs
        ]
    )


def format_training_prompt(example: VerificationExample) -> str:
    """Format a VerificationExample into a training prompt string.

    Uses a consistent prompt template so the model learns to
    produce structured verification output.

    Args:
        example: A VerificationExample.

    Returns:
        Formatted prompt string for model training.
    """
    return (
        f"{example.prompt}\n"
        f"```{example.language}\n{example.code}\n```\n\n"
        f"Verification result: {example.label}\n"
        f"Explanation: {example.explanation}"
    )


def format_contrastive_prompt(pair: ContrastivePair) -> dict[str, str]:
    """Format a ContrastivePair into preferred/dispreferred prompt pair.

    Args:
        pair: A ContrastivePair.

    Returns:
        Dict with 'preferred' and 'dispreferred' formatted prompts.
    """
    template = "Verify this code:\n```{language}\n{code}\n```\n\nIs this code correct? Explain your reasoning."
    return {
        "preferred": template.format(language=pair.language, code=pair.correct_code),
        "dispreferred": template.format(language=pair.language, code=pair.incorrect_code),
    }


def _detect_language(code: str) -> str:
    """Heuristic language detection from code content."""
    if "def " in code or "import " in code or "class " in code:
        if "async def" in code or "await " in code:
            return "python"
        if "self." in code:
            return "python"
        return "python"
    if "function " in code or "const " in code or "=>" in code:
        if re.search(r"\btsx?\b", code):
            return "typescript"
        return "javascript"
    if "fn " in code and ("let " in code or "mut " in code):
        return "rust"
    if "func " in code and "package " in code:
        return "go"
    if re.search(r"public\s+static\s+void", code):
        return "java"
    return "python"


def _apply_bug(code: str, bug_type: str) -> str | None:
    """Apply a specific bug pattern to code."""
    if bug_type == "off_by_one":
        lines = code.split("\n")
        for i, line in enumerate(lines):
            if "range(" in line:
                match = re.search(r"range\((\d+)\)", line)
                if match:
                    n = int(match.group(1))
                    lines[i] = line.replace(f"range({n})", f"range({n - 1})")
                    return "\n".join(lines)
        return None

    elif bug_type == "wrong_operator":
        replacements = [(" == ", " != "), (" != ", " == "), (" < ", " <= "), (" <= ", " < "), (" > ", " >= "), (" >= ", " > ")]
        for old, new in replacements:
            if old in code:
                return code.replace(old, new, 1)
        return None

    elif bug_type == "missing_none_check":
        lines = code.split("\n")
        for i, line in enumerate(lines):
            match = re.match(r"(\s*)(\w+)\.(\w+)", line)
            if match and match.group(2) not in ("self", "cls", "print", "len", "str", "int"):
                indent = match.group(1)
                var = match.group(2)
                attr = match.group(3)
                lines.insert(i, f"{indent}if {var} is None:")
                lines.insert(i + 1, f"{indent}    return None")
                return "\n".join(lines)
        return None

    elif bug_type == "forgotten_await":
        return re.sub(r"await\s+", "", code, count=1) if "await " in code else None

    elif bug_type == "mutable_default":
        replacements = {"=[]": "=None", "={}": "=None", "= list()": "=None", "= dict()": "=None"}
        for old, new in replacements.items():
            if old in code:
                return code.replace(old, new, 1)
        return None

    elif bug_type == "shadowed_variable":
        for_scope = re.search(r"for\s+(\w+)\s+in\s+", code)
        if for_scope:
            var = for_scope.group(1)
            lines = code.split("\n")
            for i, line in enumerate(lines):
                if f"{var} =" in line and "for " not in line:
                    lines[i] = line.replace(f"{var} =", f"shadowed_{var} =", 1)
                    return "\n".join(lines)
        return None

    return None


def _apply_line_level_bugs(code: str, count: int) -> list[dict]:
    """Fallback: apply simple line-level bugs when template bugs don't apply."""
    results = []
    lines = code.split("\n")

    strategies = [
        ("remove_return_value", lambda ls: _remove_return_value(ls)),
        ("swap_lines", lambda ls: _swap_adjacent_lines(ls)),
        ("remove_indent", lambda ls: _remove_indent(ls)),
    ]

    for strategy_name, strategy_fn in strategies[:count]:
        bugged = strategy_fn(lines[:])
        if bugged and "\n".join(bugged) != code:
            results.append(
                {
                    "code": "\n".join(bugged),
                    "bug_type": strategy_name,
                    "description": f"Line-level bug: {strategy_name}",
                    "diff_hint": f"Bug type: {strategy_name}",
                }
            )

    return results


def _remove_return_value(lines: list[str]) -> list[str] | None:
    for i, line in enumerate(lines):
        if "return " in line and "return None" not in line and "return True" not in line:
            lines[i] = re.sub(r"return\s+.+", "return None", line)
            return lines
    return None


def _swap_adjacent_lines(lines: list[str]) -> list[str] | None:
    for i in range(len(lines) - 1):
        if lines[i].strip() and lines[i + 1].strip():
            if not lines[i].startswith(("def ", "class ", "import ", "from ")):
                lines[i], lines[i + 1] = lines[i + 1], lines[i]
                return lines
    return None


def _remove_indent(lines: list[str]) -> list[str] | None:
    for i, line in enumerate(lines):
        if line.startswith("    ") and not line.startswith("        "):
            lines[i] = line.lstrip()
            return lines
    return None
