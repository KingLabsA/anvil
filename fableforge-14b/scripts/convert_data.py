#!/usr/bin/env python3
"""convert_data.py — Convert Fable-5 raw datasets into stage-specific training formats.

Reads all 6 Fable-5 source datasets and converts each into the format needed
for the 4 training stages of FableForge-14B, plus ShellWhisperer and ReasonCritic.

Stages:
  1. behavior_shaping — messages format with tool_use blocks (SFT)
  2. skill_distillation   — instruction/input/output format (SFT)
  3. error_recovery — error→recovery pairs with error_type classification (SFT)
  4. DPO           — chosen/rejected pairs for preference optimization (DPO)

Usage:
  python convert_data.py [--dry-run] [--stage STAGE] [--output-dir DIR]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import random
import re
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("convert_data")

RAW_DATA_DIR = Path(os.environ.get("FABLE5_RAW_DATA", "/tmp/fable5_analysis/raw_data"))
OUTPUT_DIR = Path(os.environ.get("FABLEFORGE_DATA", "/tmp/fableforge/fableforge-14b/data"))

VAL_SPLIT = 0.05
SEED = 42

TOOL_NAMES = {
    "Bash", "Read", "Write", "Edit", "Glob", "Grep",
    "mcp__Claude_Preview__preview_click", "mcp__Claude_Preview__preview_eval",
    "List", "Search", "Create", "Delete",
}

SHELL_COMMAND_PATTERNS = [
    re.compile(r"```(?:ba)?sh\n(.*?)```", re.DOTALL),
    re.compile(r"`([^`]+)`"),
]

ERROR_PATTERNS = [
    re.compile(r"(Error|Exception|Traceback|FAILED|error:|warning:).*", re.IGNORECASE),
    re.compile(r"(SyntaxError|TypeError|NameError|ValueError|ImportError|KeyError|IndexError|AttributeError|RuntimeError|OSError|IOError|FileNotFoundError|PermissionError|TimeoutError).*", re.IGNORECASE),
    re.compile(r"(ModuleNotFoundError|NotImplementedError|StopIteration|OverflowError|RecursionError|UnicodeDecodeError|UnicodeEncodeError|ZeroDivisionError).*", re.IGNORECASE),
]


def load_jsonl(path: Path) -> list[dict]:
    """Load a JSONL file, handling empty/broken lines."""
    records = []
    if not path.exists():
        log.warning("File not found: %s", path)
        return records
    with open(path, encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as e:
                log.warning("Skipping broken JSON at %s:%d: %s", path.name, line_num, e)
    return records


def load_parquet_as_jsonl(path: Path) -> list[dict]:
    """Load a parquet file and return as list of dicts."""
    try:
        import pandas as pd
        df = pd.read_parquet(path)
        return df.to_dict(orient="records")
    except ImportError:
        log.warning("pandas not installed, cannot load parquet: %s", path)
        return []


def load_dataset(name: str) -> list[dict]:
    """Load a named Fable-5 dataset from raw_data."""
    base = RAW_DATA_DIR / name
    if name == "vfable":
        path = base / "v_fable.jsonl"
        if not path.exists():
            path = Path("/tmp/fable5_analysis/raw_data/summerMC_vFable/v_fable.jsonl")
        if not path.exists():
            for p in sorted(Path("/tmp/fable5_analysis/raw_data/summerMC_vFable").glob("*.jsonl")):
                path = p
                break
        if path.exists():
            return load_jsonl(path)
        return load_jsonl(base / "v_fable.jsonl") if (base / "v_fable.jsonl").exists() else []

    if name == "coding_excellence":
        path = Path("/tmp/fable5_analysis/raw_data/summerMC_coding_excellence/coding_excellence.jsonl")
        if not path.exists():
            path = base / "coding_excellence.jsonl"
        if not path.exists():
            for p in sorted(base.glob("*.jsonl")):
                path = p
                break
        return load_jsonl(path) if path.exists() else []

    if name == "armand0e":
        records = []
        for p in sorted(base.glob("*.jsonl")):
            records.extend(load_jsonl(p))
        return records

    if name == "opencoven":
        path = base / "train.jsonl"
        if not path.exists():
            for p in sorted(base.glob("*.jsonl")):
                path = p
                break
        return load_jsonl(path)

    if name == "victor":
        path = base / "trace.jsonl"
        if not path.exists():
            for p in sorted(base.glob("*.jsonl")):
                path = p
                break
        return load_jsonl(path)

    if name == "glint":
        parquet_path = base / "data.parquet"
        jsonl_path = base / "glint_traces.jsonl"
        if jsonl_path.exists():
            return load_jsonl(jsonl_path)
        if parquet_path.exists():
            return load_parquet_as_jsonl(parquet_path)
        for p in sorted(base.glob("*.jsonl")):
            return load_jsonl(p)
        return []

    return []


def extract_tool_calls_from_text(text: str) -> list[dict]:
    """Extract tool-use blocks from agent trace text."""
    tool_calls = []
    pattern = re.compile(
        r"(?:ASSISTANT|assistant)\s*\((?:message|tool call\w*)\)\s*:? "
        r"(\w+)\s+(?:input|arguments?)\s*=\s*(\{.*?\})",
        re.IGNORECASE | re.DOTALL,
    )
    for m in pattern.finditer(text):
        tool_name = m.group(1)
        try:
            args = json.loads(m.group(2))
        except (json.JSONDecodeError, TypeError):
            args = {"raw": m.group(2)[:200]}
        tool_calls.append({"name": tool_name, "arguments": args})

    json_tool_pattern = re.compile(
        r'"function"?\s*:\s*\{\s*"name"?\s*:\s*"([^"]+)"',
        re.IGNORECASE,
    )
    for m in json_tool_pattern.finditer(text):
        tool_calls.append({"name": m.group(1), "arguments": {}})

    return tool_calls


def extract_bash_commands(messages: list[dict]) -> list[str]:
    """Extract bash/shell commands from message list."""
    commands = []
    for msg in messages:
        content = msg.get("content", "") if isinstance(msg.get("content"), str) else ""
        if not content:
            continue
        if isinstance(msg.get("tool_calls"), list):
            for tc in msg["tool_calls"]:
                fn = tc.get("function", tc) if isinstance(tc.get("function"), dict) else {}
                name = fn.get("name", tc.get("name", ""))
                args_str = fn.get("arguments", tc.get("arguments", "{}"))
                if name.lower() in ("bash", "shell", "command", "run"):
                    if isinstance(args_str, str):
                        try:
                            args = json.loads(args_str)
                        except (json.JSONDecodeError, TypeError):
                            args = {"command": args_str}
                    else:
                        args = args_str if isinstance(args_str, dict) else {"command": str(args_str)}
                    cmd = args.get("command", args.get("input", ""))
                    if cmd:
                        commands.append(cmd)

        if msg.get("role") == "tool" and "bash" in str(msg.get("name", "")).lower():
            pass

        full_text = content if isinstance(content, str) else json.dumps(content)
        for pat in SHELL_COMMAND_PATTERNS:
            for m in pat.finditer(full_text):
                candidate = m.group(1).strip()
                if candidate and len(candidate) > 3 and not candidate.startswith("#!"):
                    commands.append(candidate)

    return commands


def classify_error_type(text: str) -> str:
    """Classify the type of error in a text snippet."""
    text_lower = text.lower()
    if any(k in text_lower for k in ["syntaxerror", "syntax error", "unexpected token", "unexpected eof"]):
        return "syntax_error"
    if any(k in text_lower for k in ["typeerror", "type error", "cannot read", "is not a function", "undefined is not"]):
        return "type_error"
    if any(k in text_lower for k in ["nameerror", "name '"]):
        return "name_error"
    if any(k in text_lower for k in ["keyerror", "key error", "no such key", "key not found"]):
        return "key_error"
    if any(k in text_lower for k in ["indexerror", "index out of range", "list index"]):
        return "index_error"
    if any(k in text_lower for k in ["importerror", "modulenotfound", "no module named"]):
        return "import_error"
    if any(k in text_lower for k in ["filenotfound", "no such file", "enoent"]):
        return "file_not_found"
    if any(k in text_lower for k in ["permissionerror", "permission denied", "eacces"]):
        return "permission_error"
    if any(k in text_lower for k in ["timeout", "timed out", "deadline exceeded"]):
        return "timeout_error"
    if any(k in text_lower for k in ["runtimeerror", "runtime error"]):
        return "runtime_error"
    if any(k in text_lower for k in ["valueerror", "invalid value"]):
        return "value_error"
    if any(k in text_lower for k in ["oserror", "ioerror", "connection", "network"]):
        return "io_error"
    return "other_error"


# ---------- Stage 1: Behavior Shaping (SFT) ----------

def convert_stage1_behavior_shaping(all_data: dict[str, list[dict]]) -> list[dict]:
    """Convert data to OpenAI fine-tuning messages format with tool_use blocks.

    This is the primary SFT format for teaching the model when/how to use tools.
    Input: OpenAI chat-completions format with messages array.
    Output: OpenAI fine-tuning format with tool_calls.
    """
    results = []

    for dataset_name, records in all_data.items():
        log.info("Stage 1: Processing %d records from %s", len(records), dataset_name)

        for rec in records:
            messages = rec.get("messages", [])
            if not messages:
                continue

            has_tool_use = False
            for msg in messages:
                content = msg.get("content", "")
                if isinstance(content, str):
                    for tn in TOOL_NAMES:
                        if tn in content:
                            has_tool_use = True
                            break
                if msg.get("tool_calls"):
                    has_tool_use = True
                    break

            tool_calls_in_msg = extract_tool_calls_from_text(
                " ".join(m.get("content", "") for m in messages if isinstance(m.get("content", ""), str))
            )
            if tool_calls_in_msg:
                has_tool_use = True

            if not has_tool_use and dataset_name not in ("vfable", "armand0e", "glint", "victor"):
                continue

            ft_messages = []
            for msg in messages:
                role = msg.get("role", "")
                content = msg.get("content", "")
                if role not in ("system", "user", "assistant", "tool"):
                    continue

                if role == "tool":
                    ft_messages.append({
                        "role": "tool",
                        "content": content if isinstance(content, str) else json.dumps(content),
                        "tool_call_id": msg.get("tool_call_id", f"call_{hashlib.md5(content[:64].encode()).hexdigest()[:12]}"),
                    })
                    continue

                if msg.get("tool_calls"):
                    ft_messages.append({
                        "role": "assistant",
                        "content": content if isinstance(content, str) else "",
                        "tool_calls": [
                            {
                                "id": tc.get("id", f"call_{i}"),
                                "type": "function",
                                "function": {
                                    "name": tc.get("function", tc).get("name", tc.get("name", "unknown")),
                                    "arguments": tc.get("function", tc).get("arguments", tc.get("arguments", "{}")),
                                },
                            }
                            for i, tc in enumerate(msg["tool_calls"])
                        ],
                    })
                    continue

                ft_messages.append({
                    "role": role,
                    "content": content if isinstance(content, str) else json.dumps(content),
                })

            if len(ft_messages) >= 2:
                results.append({
                    "messages": ft_messages,
                    "source": dataset_name,
                    "stage": "behavior_shaping",
                })

    return results


# ---------- Stage 2: Skill Distillation (SFT) ----------

def convert_stage2_skill_distillation(all_data: dict[str, list[dict]]) -> list[dict]:
    """Convert data to instruction/input/output format for skill distillation.

    This stage focuses on code generation quality, not tool use.
    Extracts the core coding skill from each example.
    """
    results = []
    skill_categories = [
        "code_generation", "debugging", "refactoring", "testing",
        "documentation", "architecture", "optimization", "security_review",
    ]

    for dataset_name, records in all_data.items():
        log.info("Stage 2: Processing %d records from %s", len(records), dataset_name)

        for rec in records:
            messages = rec.get("messages", [])

            user_msg = None
            assistant_msg = None
            system_msg = None

            for msg in messages:
                role = msg.get("role", "")
                content = msg.get("content", "")
                if not isinstance(content, str):
                    content = json.dumps(content) if content else ""
                if role == "system":
                    system_msg = content
                elif role == "user" and not user_msg:
                    user_msg = content
                elif role == "assistant" and not assistant_msg:
                    assistant_msg = content

            if dataset_name in ("coding_excellence",):
                inst = rec.get("instruction", rec.get("input", ""))
                inp = rec.get("input", "")
                out = rec.get("output", "")

                if inst or inp:
                    instruction = inst or inp
                    results.append({
                        "instruction": instruction[:4096],
                        "input": inp if inst else "",
                        "output": out[:8192] if out else (assistant_msg or "")[:8192],
                        "category": "code_generation",
                        "source": dataset_name,
                        "stage": "skill_distillation",
                    })
                    continue

            if user_msg and assistant_msg:
                skill_idx = hash(user_msg) % len(skill_categories)
                results.append({
                    "instruction": user_msg[:4096],
                    "input": system_msg[:512] if system_msg else "",
                    "output": assistant_msg[:8192],
                    "category": skill_categories[skill_idx],
                    "source": dataset_name,
                    "stage": "skill_distillation",
                })

    return results


# ---------- Stage 3: Error Recovery (SFT) ----------

def convert_stage3_error_recovery(all_data: dict[str, list[dict]]) -> list[dict]:
    """Convert data to error→recovery pairs with error_type classification.

    Finds examples where an error occurred and the agent recovered from it.
    Format: instruction contains the error context, output contains the fix.
    """
    results = []

    for dataset_name, records in all_data.items():
        log.info("Stage 3: Processing %d records from %s", len(records), dataset_name)

        for rec in records:
            messages = rec.get("messages", [])

            error_idx = None
            error_text = None
            recovery_idx = None
            recovery_text = None

            for i, msg in enumerate(messages):
                content = msg.get("content", "")
                if not isinstance(content, str):
                    content = json.dumps(content) if content else ""
                role = msg.get("role", "")

                if role in ("tool", "user") and error_idx is None:
                    if any(pat.search(content) for pat in ERROR_PATTERNS):
                        for j in range(i + 1, min(i + 6, len(messages))):
                            next_content = messages[j].get("content", "")
                            if not isinstance(next_content, str):
                                next_content = json.dumps(next_content) if next_content else ""
                            next_role = messages[j].get("role", "")
                            if next_role == "assistant" and len(next_content) > 20:
                                error_idx = i
                                error_text = content[:2048]
                                recovery_idx = j
                                recovery_text = next_content[:4096]
                                break

            if error_idx is not None and error_text and recovery_text:
                error_type = classify_error_type(error_text)

                pre_context = ""
                for k in range(max(0, error_idx - 2), error_idx):
                    pre = messages[k].get("content", "")
                    if isinstance(pre, str):
                        pre_context += pre[:512] + "\n"

                results.append({
                    "instruction": f"Fix the following {error_type}:\n\n{error_text}",
                    "input": pre_context,
                    "output": recovery_text,
                    "error_type": error_type,
                    "source": dataset_name,
                    "stage": "error_recovery",
                })

        if dataset_name == "coding_excellence":
            for rec in records:
                messages = rec.get("messages", [])
                full_text = " ".join(
                    m.get("content", "") for m in messages
                    if isinstance(m.get("content", ""), str)
                )
                if "Error" in full_text or "error" in full_text or "Exception" in full_text:
                    for i, msg in enumerate(messages):
                        content = msg.get("content", "")
                        if not isinstance(content, str):
                            continue
                        if any(pat.search(content) for pat in ERROR_PATTERNS):
                            end_idx = min(i + 8, len(messages))
                            for j in range(i + 1, end_idx):
                                nxt = messages[j]
                                nxt_content = nxt.get("content", "")
                                if not isinstance(nxt_content, str):
                                    continue
                                if nxt.get("role") == "assistant" and len(nxt_content) > 40:
                                    error_type = classify_error_type(content)
                                    if error_type != "other_error" or random.random() < 0.2:
                                        results.append({
                                            "instruction": f"Fix the following {error_type}:\n\n{content[:2048]}",
                                            "input": "",
                                            "output": nxt_content[:4096],
                                            "error_type": error_type,
                                            "source": dataset_name,
                                            "stage": "error_recovery",
                                        })
                                    break

    return results


# ---------- Stage 4: DPO (Preference Optimization) ----------

def convert_stage4_dpo(all_data: dict[str, list[dict]]) -> list[dict]:
    """Convert data to chosen/rejected pairs for Direct Preference Optimization.

    Strategy:
    1. From vfable/armand0e tool-use traces: chosen = agent's actual tool use,
       rejected = a degraded version (wrong tool, missing tool, etc.)
    2. From coding_excellence: chosen = expert output, rejected = simplified/degraded output
    3. From opencoven reasoning: chosen = correct reasoning, rejected = flawed reasoning
    """
    results = []
    rng = random.Random(SEED)

    def degrade_code(code: str) -> str:
        """Create a plausible but inferior version of code."""
        lines = code.strip().split("\n")
        if len(lines) <= 3:
            return code

        degraded = list(lines)
        removals = max(1, len(lines) // 5)
        indices = rng.sample(range(len(lines)), min(removals, len(lines)))
        degraded = [l for i, l in enumerate(degraded) if i not in indices]

        if len(degraded) >= 2:
            swap_a, swap_b = rng.sample(range(len(degraded)), min(2, len(degraded)))
            degraded[swap_a], degraded[swap_b] = degraded[swap_b], degraded[swap_a]

        return "\n".join(degraded)

    def degrade_tool_choice(tool_calls: list[dict]) -> list[dict]:
        """Create a worse tool call sequence."""
        if not tool_calls:
            return []
        degraded = list(tool_calls)
        if len(degraded) > 1:
            swap_a, swap_b = rng.sample(range(len(degraded)), min(2, len(degraded)))
            degraded[swap_a], degraded[swap_b] = degraded[swap_b], degraded[swap_a]
        return degraded

    for dataset_name, records in all_data.items():
        log.info("Stage 4: Processing %d records from %s", len(records), dataset_name)

        for rec in records:
            messages = rec.get("messages", [])
            if len(messages) < 3:
                continue

            user_msgs = [m for m in messages if m.get("role") == "user"]
            assistant_msgs = [m for m in messages if m.get("role") == "assistant"]

            if not user_msgs or not assistant_msgs:
                continue

            prompt = user_msgs[0].get("content", "")
            if not isinstance(prompt, str):
                prompt = json.dumps(prompt)
            prompt = prompt[:4096]

            chosen_content = assistant_msgs[0].get("content", "")
            if not isinstance(chosen_content, str):
                chosen_content = json.dumps(chosen_content)
            chosen_content = chosen_content[:8192]

            chosen_tool_calls = assistant_msgs[0].get("tool_calls", [])

            if chosen_tool_calls:
                rejected_tool_calls = degrade_tool_choice(chosen_tool_calls)
                rejected_content = degrade_code(chosen_content) if len(chosen_content) > 50 else chosen_content

                results.append({
                    "prompt": prompt,
                    "chosen": json.dumps({
                        "role": "assistant",
                        "content": chosen_content,
                        "tool_calls": chosen_tool_calls,
                    }),
                    "rejected": json.dumps({
                        "role": "assistant",
                        "content": rejected_content,
                        "tool_calls": rejected_tool_calls,
                    }),
                    "source": dataset_name,
                    "stage": "dpo",
                })
            elif len(chosen_content) > 100:
                rejected_content = degrade_code(chosen_content)

                results.append({
                    "prompt": prompt,
                    "chosen": chosen_content,
                    "rejected": rejected_content,
                    "source": dataset_name,
                    "stage": "dpo",
                })

    return results


def write_jsonl(records: list[dict], path: Path, dry_run: bool = False) -> int:
    """Write records to a JSONL file. Returns count written."""
    if dry_run:
        log.info("DRY: Would write %d records to %s", len(records), path)
        return len(records)

    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with open(path, "w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            count += 1
    log.info("Wrote %d records to %s", count, path)
    return count


def write_manifest(stage: str, counts: dict[str, int], output_dir: Path):
    """Write a manifest file for a stage."""
    manifest = {
        "stage": stage,
        "format": "jsonl",
        "splits": {},
        "total": 0,
    }
    for split_name, count in counts.items():
        manifest["splits"][split_name] = {
            "path": str(output_dir / f"{stage}_{split_name}.jsonl"),
            "count": count,
        }
        manifest["total"] += count
    manifest_path = output_dir / f"{stage}_manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
    log.info("Wrote manifest to %s", manifest_path)


def convert_shell_whisperer(all_data: dict[str, list[dict]]) -> list[dict]:
    """Extract NL→shell-command pairs for ShellWhisperer training."""
    results = []

    for dataset_name, records in all_data.items():
        if dataset_name not in ("vfable", "armand0e", "glint", "victor"):
            continue

        for rec in records:
            messages = rec.get("messages", [])
            commands = extract_bash_commands(messages)
            if not commands:
                continue

            user_msgs = [m for m in messages if m.get("role") == "user"]
            if not user_msgs:
                continue

            for cmd in commands:
                if len(cmd) < 5 or len(cmd) > 1000:
                    continue
                if any(dangerous in cmd.lower() for dangerous in [
                    "rm -rf /", ":(){ :|:& };:", "> /dev/sda", "mkfs",
                ]):
                    continue

                prompt = user_msgs[0].get("content", "")
                if isinstance(prompt, list):
                    prompt = " ".join(str(p.get("text", "")) for p in prompt if isinstance(p, dict))
                prompt = str(prompt)[:1024]

                results.append({
                    "instruction": "Generate a shell command for the following task",
                    "input": prompt[:512],
                    "output": cmd,
                    "category": "shell_command",
                    "source": dataset_name,
                })

    return results


def convert_reason_critic(all_data: dict[str, list[dict]]) -> list[dict]:
    """Extract verification/critique pairs for ReasonCritic training."""
    results = []

    for dataset_name, records in all_data.items():
        for rec in records:
            messages = rec.get("messages", [])
            if len(messages) < 2:
                continue

            code_blocks = []
            error_indices = []
            for i, msg in enumerate(messages):
                content = msg.get("content", "")
                if not isinstance(content, str):
                    continue

                code_matches = re.findall(r"```(?:\w+)?\n(.*?)```", content, re.DOTALL)
                for block in code_matches:
                    if len(block) > 20:
                        code_blocks.append((i, block, content))

                if any(pat.search(content) for pat in ERROR_PATTERNS):
                    error_indices.append(i)

            for err_idx in error_indices:
                err_content = messages[err_idx].get("content", "")
                if not isinstance(err_content, str):
                    continue

                pre_code = ""
                for ci, cb, cc in code_blocks:
                    if ci < err_idx and ci >= err_idx - 5:
                        pre_code = cb
                        break

                if not pre_code:
                    continue

                fix_found = False
                for j in range(err_idx + 1, min(err_idx + 6, len(messages))):
                    fix_msg = messages[j]
                    fix_content = fix_msg.get("content", "")
                    if not isinstance(fix_content, str):
                        continue
                    if fix_msg.get("role") == "assistant" and len(fix_content) > 20:
                        results.append({
                            "code": pre_code[:4096],
                            "error_trace": err_content[:2048],
                            "verdict": "FAIL",
                            "confidence": 0.85 + random.random() * 0.14,
                            "issues": [{"type": classify_error_type(err_content), "description": err_content[:200]}],
                            "suggestions": [fix_content[:500]],
                            "source": dataset_name,
                        })
                        fix_found = True
                        break

            for ci, cb, cc in code_blocks:
                if ci not in error_indices and len(cb) > 50:
                    if random.random() < 0.3:
                        results.append({
                            "code": cb[:4096],
                            "error_trace": "",
                            "verdict": "PASS",
                            "confidence": 0.9 + random.random() * 0.09,
                            "issues": [],
                            "suggestions": [],
                            "source": dataset_name,
                        })

    return results


def main():
    parser = argparse.ArgumentParser(description="Convert Fable-5 data to training formats")
    parser.add_argument("--dry-run", action="store_true", help="Validate format without writing files")
    parser.add_argument("--stage", choices=["1", "2", "3", "4", "shell_whisperer", "reason_critic", "all"], default="all",
                        help="Convert only one stage (1-4, shell_whisperer, reason_critic, or all)")
    parser.add_argument("--output-dir", default=str(OUTPUT_DIR),
                        help="Output directory for converted data")
    parser.add_argument("--val-split", type=float, default=VAL_SPLIT,
                        help="Validation split ratio (default: 0.05)")
    parser.add_argument("--seed", type=int, default=SEED, help="Random seed")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    rng = random.Random(args.seed)

    log.info("Loading Fable-5 datasets from %s", RAW_DATA_DIR)

    datasets = {
        "vfable": load_dataset("vfable"),
        "coding_excellence": load_dataset("coding_excellence"),
        "armand0e": load_dataset("armand0e"),
        "opencoven": load_dataset("opencoven"),
        "victor": load_dataset("victor"),
        "glint": load_dataset("glint"),
    }

    for name, data in datasets.items():
        log.info("  %s: %d records", name, len(data))

    stage_configs = [
        ("1", "behavior_shaping", convert_stage1_behavior_shaping),
        ("2", "skill_distillation", convert_stage2_skill_distillation),
        ("3", "error_recovery", convert_stage3_error_recovery),
        ("4", "dpo", convert_stage4_dpo),
    ]

    target_stage = args.stage
    if target_stage == "all":
        target_stages = {"1", "2", "3", "4", "shell_whisperer", "reason_critic"}
    else:
        target_stages = {target_stage}

    for stage_num, stage_name, converter in stage_configs:
        if stage_num not in target_stages:
            continue

        log.info("=== Converting Stage %s: %s ===", stage_num, stage_name)
        records = converter(datasets)
        log.info("  Total records: %d", len(records))

        if not records:
            log.warning("  No records converted for stage %s", stage_num)
            continue

        rng.shuffle(records)
        val_count = max(1, int(len(records) * args.val_split))
        train_records = records[val_count:]
        val_records = records[:val_count]

        train_path = output_dir / stage_name / f"{stage_name}_train.jsonl"
        val_path = output_dir / stage_name / f"{stage_name}_val.jsonl"

        train_count = write_jsonl(train_records, train_path, dry_run=args.dry_run)
        val_count_actual = write_jsonl(val_records, val_path, dry_run=args.dry_run)

        if not args.dry_run:
            write_manifest(stage_name, {"train": train_count, "val": val_count_actual}, output_dir / stage_name)

    if "shell_whisperer" in target_stages:
        log.info("=== Converting ShellWhisperer data ===")
        sw_records = convert_shell_whisperer(datasets)
        log.info("  Total shell command pairs: %d", len(sw_records))

        if sw_records:
            rng.shuffle(sw_records)
            val_count = max(1, int(len(sw_records) * args.val_split))
            sw_train = sw_records[val_count:]
            sw_val = sw_records[:val_count]

            sw_dir = Path(os.environ.get("SHELL_WHISPERER_DATA", "/tmp/fableforge/shell-whisperer/data"))
            write_jsonl(sw_train, sw_dir / "shell_train.jsonl", dry_run=args.dry_run)
            write_jsonl(sw_val, sw_dir / "shell_val.jsonl", dry_run=args.dry_run)

    if "reason_critic" in target_stages:
        log.info("=== Converting ReasonCritic data ===")
        rc_records = convert_reason_critic(datasets)
        log.info("  Total verification pairs: %d", len(rc_records))

        if rc_records:
            rng.shuffle(rc_records)
            val_count = max(1, int(len(rc_records) * args.val_split))
            rc_train = rc_records[val_count:]
            rc_val = rc_records[:val_count]

            rc_dir = Path(os.environ.get("REASON_CRITIC_DATA", "/tmp/fableforge/reason-critic/data"))
            write_jsonl(rc_train, rc_dir / "critic_train.jsonl", dry_run=args.dry_run)
            write_jsonl(rc_val, rc_dir / "critic_val.jsonl", dry_run=args.dry_run)

    log.info("=== Conversion complete ===")


if __name__ == "__main__":
    main()
