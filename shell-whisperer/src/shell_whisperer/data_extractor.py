"""Extract Bash commands from Fable5 traces and create training pairs.

Supported formats:
  - Glint JSONL: command traces with shell intent metadata
  - armand0e JSONL: structured shell session logs
  - v-Fable JSONL: validated Fable traces with confirmation signals

Produces (natural_language, bash_command) training pairs filtered for quality.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

# Minimum command complexity: must use at least one "interesting" feature
_COMPLEX_PATTERNS: list[re.Pattern] = [
    re.compile(r"\|"),            # pipe
    re.compile(r"&&"),             # command chaining
    re.compile(r";"),              # sequence
    re.compile(r"\$\(.*\)"),      # command substitution
    re.compile(r"`.*`"),          # backtick substitution
    re.compile(r">"),             # redirect
    re.compile(r"-[a-zA-Z]{2,}"), # multi-flag (e.g., -la, -rfind)
    re.compile(r"xargs"),         # xargs
    re.compile(r"find\s", re.IGNORECASE),
    re.compile(r"grep\s", re.IGNORECASE),
    re.compile(r"sed\s", re.IGNORECASE),
    re.compile(r"awk\s", re.IGNORECASE),
    re.compile(r"sort\s", re.IGNORECASE),
    re.compile(r"uniq\s", re.IGNORECASE),
    re.compile(r"curl\s", re.IGNORECASE),
    re.compile(r"docker\s", re.IGNORECASE),
    re.compile(r"git\s", re.IGNORECASE),
    re.compile(r"ssh\s", re.IGNORECASE),
    re.compile(r"rsync\s", re.IGNORECASE),
    re.compile(r"tar\s", re.IGNORECASE),
    re.compile(r"npm\s", re.IGNORECASE),
    re.compile(r"pip\s", re.IGNORECASE),
    re.compile(r"kubectl\s", re.IGNORECASE),
    re.compile(r"aws\s", re.IGNORECASE),
]

# Commands that are too simple to be useful training data
_TRIVIAL_COMMANDS: set[str] = {
    "ls", "pwd", "whoami", "date", "clear", "exit", "history",
    "cd", "cd ~", "cd ..", "cd -",
}

# Danger patterns — skip these entirely during extraction
_DANGER_REGEX = re.compile(
    r"rm\s+-rf\s+(/|~|/home|/etc|/usr|/var|/bin)",
    re.IGNORECASE,
)


@dataclass
class TrainingPair:
    """A single training example pairing natural language with a shell command."""

    natural_language: str
    bash_command: str
    source: str = ""
    quality_score: float = 0.0

    def to_dict(self) -> dict:
        return {
            "natural_language": self.natural_language,
            "bash_command": self.bash_command,
            "source": self.source,
            "quality_score": self.quality_score,
        }


def _is_high_quality(cmd: str, nl: str) -> bool:
    """Return True if the (nl, cmd) pair is high-quality training data.

    Filters out:
      - Empty or whitespace-only commands
      - Trivially simple commands (ls, pwd, etc.)
      - Commands shorter than 8 characters
      - Descriptions shorter than 4 characters
      - Dangerous commands (rm -rf /)
      - Echo/cat-only commands with no other features
    """
    cmd = cmd.strip()
    nl = nl.strip()
    if len(cmd) < 8:
        return False
    if len(nl) < 4:
        return False
    if cmd in _TRIVIAL_COMMANDS:
        return False
    if _DANGER_REGEX.search(cmd):
        return False

    # Must have at least one complex feature
    has_complex = any(p.search(cmd) for p in _COMPLEX_PATTERNS)
    if not has_complex:
        # Allow some simple-but-real commands
        simple_ok = any(
            cmd.startswith(prefix)
            for prefix in ("git ", "docker ", "ssh ", "curl ", "pip ", "npm ")
        )
        if not simple_ok:
            return False

    return True


def _quality_score(cmd: str, nl: str) -> float:
    """Score a training pair on [0.0, 1.0].

    Higher scores for: longer descriptions, complex commands, multiple features.
    """
    score = 0.3
    score += min(len(nl) / 100.0, 0.3)  # length of description
    score += min(len(cmd) / 80.0, 0.2)   # length of command

    features = sum(1 for p in _COMPLEX_PATTERNS if p.search(cmd))
    score += min(features * 0.05, 0.2)   # complexity features

    return min(score, 1.0)


# ---------------------------------------------------------------------------
# Glint format extractor
# ---------------------------------------------------------------------------


def extract_bash_from_glint(jsonl_path: str | Path) -> list[TrainingPair]:
    """Extract Bash commands from Glint JSONL traces.

    Expected Glint format per line:
        {
            "type": "shell_command" | "shell_intent",
            "intent": "natural language description",
            "command": "actual bash command",
            "shell": "bash" | "zsh" | "fish",
            "exit_code": 0,
            "metadata": {...}
        }

    Lines with type "shell_intent" provide the NL description;
    lines with type "shell_command" provide the actual command.
    They are matched by sequence order.
    """
    path = Path(jsonl_path)
    pairs: list[TrainingPair] = []

    intents: list[str] = []
    commands: list[str] = []

    with path.open("r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue

            rec_type = record.get("type", "")
            if rec_type == "shell_intent":
                intent = record.get("intent", "").strip()
                if intent:
                    intents.append(intent)
            elif rec_type == "shell_command":
                shell = record.get("shell", "bash")
                if shell not in ("bash", "zsh", "sh"):
                    continue
                exit_code = record.get("exit_code")
                if exit_code is not None and exit_code != 0:
                    continue
                cmd = record.get("command", "").strip()
                if cmd:
                    commands.append(cmd)

    # Pair intents with commands by order; if intents are sparse,
    # generate a synthetic description from the command itself.
    for i, cmd in enumerate(commands):
        nl = intents[i] if i < len(intents) else _synthesize_description(cmd)
        pair = TrainingPair(
            natural_language=nl,
            bash_command=cmd,
            source="glint",
            quality_score=_quality_score(cmd, nl),
        )
        if _is_high_quality(cmd, nl):
            pairs.append(pair)

    return pairs


# ---------------------------------------------------------------------------
# armand0e format extractor
# ---------------------------------------------------------------------------


def extract_bash_from_armand0e(jsonl_path: str | Path) -> list[TrainingPair]:
    """Extract Bash commands from armand0e JSONL traces.

    Expected armand0e format per line:
        {
            "event": "command_executed",
            "prompt": "natural language description or null",
            "command": "bash command string",
            "cwd": "/home/user/project",
            "exit_status": 0,
            "duration_ms": 123,
            "tags": ["shell", "git"]
        }

    Only includes commands with exit_status == 0.
    If "prompt" is null/missing, synthesizes a description.
    """
    path = Path(jsonl_path)
    pairs: list[TrainingPair] = []

    with path.open("r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue

            if record.get("event") != "command_executed":
                continue
            if record.get("exit_status", -1) != 0:
                continue

            cmd = record.get("command", "").strip()
            if not cmd:
                continue

            nl = record.get("prompt") or _synthesize_description(cmd)
            nl = nl.strip()
            if not nl:
                continue

            pair = TrainingPair(
                natural_language=nl,
                bash_command=cmd,
                source="armand0e",
                quality_score=_quality_score(cmd, nl),
            )
            if _is_high_quality(cmd, nl):
                pairs.append(pair)

    return pairs


# ---------------------------------------------------------------------------
# v-Fable format extractor
# ---------------------------------------------------------------------------


def extract_bash_from_vfable(jsonl_path: str | Path) -> list[TrainingPair]:
    """Extract Bash commands from v-Fable JSONL traces.

    Expected v-Fable format per line:
        {
            "role": "user" | "assistant" | "tool_result",
            "content": "...",
            "tool_call": {
                "name": "execute_shell",
                "arguments": {"command": "..."}
            },
            "validation": {
                "confirmed": true,
                "exit_code": 0
            },
            "utterance": "natural language description"
        }

    Pairs user utterances with validated assistant tool calls.
    """
    path = Path(jsonl_path)
    pairs: list[TrainingPair] = []

    utterances: list[str] = []
    commands: list[str] = []

    with path.open("r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue

            role = record.get("role", "")

            if role == "user":
                utterance = record.get("utterance", "").strip()
                content = record.get("content", "").strip()
                text = utterance or content
                if text:
                    utterances.append(text)

            elif role == "assistant":
                tool_call = record.get("tool_call", {})
                if tool_call.get("name") == "execute_shell":
                    cmd = tool_call.get("arguments", {}).get("command", "").strip()
                    validation = record.get("validation", {})
                    if not cmd:
                        continue
                    if not validation.get("confirmed", False):
                        continue
                    if validation.get("exit_code", -1) != 0:
                        continue
                    commands.append(cmd)

    # Match utterances with commands
    for i, cmd in enumerate(commands):
        nl = utterances[i] if i < len(utterances) else _synthesize_description(cmd)
        pair = TrainingPair(
            natural_language=nl,
            bash_command=cmd,
            source="vfable",
            quality_score=_quality_score(cmd, nl),
        )
        if _is_high_quality(cmd, nl):
            pairs.append(pair)

    return pairs


# ---------------------------------------------------------------------------
# Synthetic description generator
# ---------------------------------------------------------------------------


def _synthesize_description(cmd: str) -> str:
    """Generate a natural language description from a Bash command.

    Uses simple pattern matching to create readable descriptions.
    This is a fallback when no human-written description is available.
    """
    cmd = cmd.strip()

    # Common patterns with templates
    patterns: list[tuple[re.Pattern, str]] = [
        (re.compile(r"^find\s+.*-name\s+['\"]?([^'\"]+)['\"]?"), r"find files named \1"),
        (re.compile(r"^find\s+.*-name\s+['\"]?([^'\"]+)['\"]?.*-exec\s+(\w+)"), r"find \1 and run \2 on them"),
        (re.compile(r"^grep\s+-[rR]\s+['\"]?([^'\"]+)['\"]?\s+(.+)"), r"recursively search for \1 in \2"),
        (re.compile(r"^git\s+(\w+)"), r"git \1"),
        (re.compile(r"^docker\s+(\w+)\s+(\w+)"), r"docker \1 \2"),
        (re.compile(r"^curl\s+.*(https?://\S+)"), r"curl \1"),
        (re.compile(r"^ssh\s+(\S+)"), r"ssh into \1"),
        (re.compile(r"^pip\s+install\s+(.+)"), r"pip install \1"),
        (re.compile(r"^npm\s+install\s+(.+)"), r"npm install \1"),
        (re.compile(r"^kubectl\s+(\w+)\s+(\w+)"), r"kubectl \1 \2"),
        (re.compile(r"^aws\s+(\w+)\s+(\w+)"), r"aws \1 \2"),
        (re.compile(r"^tar\s+.*-([xtc].*)\s+(.+)"), r"tar \1 \2"),
        (re.compile(r"^ps\s+aux\s*\|\s*grep\s+(\S+)"), r"find process named \1"),
        (re.compile(r"^du\s+-sh\s+(.+)"), r"check disk usage of \1"),
        (re.compile(r"^kill\s+-9\s+(\d+)"), r"force kill process \1"),
        (re.compile(r"^lsof\s+-[it]+:(\d+)"), r"find process on port \1"),
        (re.compile(r"^chmod\s+(\S+)\s+(\S+)"), r"change permissions of \2 to \1"),
        (re.compile(r"^cp\s+(-\S+\s+)?(.+)\s+(.+)"), r"copy \2 to \3"),
        (re.compile(r"^mv\s+(.+)\s+(.+)"), r"move \1 to \2"),
        (re.compile(r"^mkdir\s+(-p\s+)?(.+)"), r"create directory \2"),
        (re.compile(r"^sort\s+(.+)"), r"sort \1"),
        (re.compile(r"^wc\s+-l\s+(.+)"), r"count lines in \1"),
        (re.compile(r"^head\s+-(\d+)\s+(.+)"), r"show first \1 lines of \2"),
        (re.compile(r"^tail\s+-(\d+)\s+(.+)"), r"show last \1 lines of \2"),
    ]

    for pattern, template in patterns:
        m = pattern.search(cmd)
        if m:
            try:
                return template.replace(r"\1", m.group(1) if m.lastindex >= 1 else "")
            except IndexError:
                try:
                    return template.replace(r"\1", m.group(1)).replace(r"\2", m.group(2))
                except (IndexError, re.error):
                    pass

    # Fallback: use first meaningful token
    parts = cmd.split()
    if len(parts) >= 2:
        return f"run {parts[0]} {parts[1]}"
    return f"run {cmd}"


# ---------------------------------------------------------------------------
# Builtin example training pairs from real-world shell usage
# ---------------------------------------------------------------------------


BUILTIN_PAIRS: list[TrainingPair] = [
    TrainingPair(
        natural_language="find all python files over 100 lines",
        bash_command='find . -name "*.py" -exec wc -l {} + | awk \'$1 > 100\'',
        source="builtin",
        quality_score=0.85,
    ),
    TrainingPair(
        natural_language="kill the process on port 8080",
        bash_command="lsof -ti:8080 | xargs kill -9",
        source="builtin",
        quality_score=0.80,
    ),
    TrainingPair(
        natural_language="show disk usage sorted by size",
        bash_command="du -sh * | sort -rh",
        source="builtin",
        quality_score=0.75,
    ),
    TrainingPair(
        natural_language="list all docker containers including stopped ones",
        bash_command="docker ps -a",
        source="builtin",
        quality_score=0.70,
    ),
    TrainingPair(
        natural_language="create a virtual environment and install requests",
        bash_command="python3 -m venv .venv && source .venv/bin/activate && pip install requests",
        source="builtin",
        quality_score=0.80,
    ),
    TrainingPair(
        natural_language="find all json files modified in the last 7 days",
        bash_command='find . -name "*.json" -mtime -7',
        source="builtin",
        quality_score=0.82,
    ),
    TrainingPair(
        natural_language="recursively search for TODO in all python files",
        bash_command='grep -rn "TODO" --include="*.py" .',
        source="builtin",
        quality_score=0.83,
    ),
    TrainingPair(
        natural_language="show the top 10 processes by memory usage",
        bash_command="ps aux --sort=-%mem | head -11",
        source="builtin",
        quality_score=0.78,
    ),
    TrainingPair(
        natural_language="count how many lines of code are in all javascript files",
        bash_command='find . -name "*.js" -exec cat {} + | wc -l',
        source="builtin",
        quality_score=0.80,
    ),
    TrainingPair(
        natural_language="list all git branches sorted by last commit date",
        bash_command="git branch --sort=-committerdate",
        source="builtin",
        quality_score=0.75,
    ),
    TrainingPair(
        natural_language="create a tar.gz archive of the project directory",
        bash_command="tar -czf project.tar.gz project/",
        source="builtin",
        quality_score=0.72,
    ),
    TrainingPair(
        natural_language="show all listening ports with process names",
        bash_command="lsof -i -P -n | grep LISTEN",
        source="builtin",
        quality_score=0.78,
    ),
    TrainingPair(
        natural_language="delete all pycache directories recursively",
        bash_command='find . -type d -name "__pycache__" -exec rm -rf {} +',
        source="builtin",
        quality_score=0.77,
    ),
    TrainingPair(
        natural_language="rename all .txt files to .md in current directory",
        bash_command='for f in *.txt; do mv "$f" "${f%.txt}.md"; done',
        source="builtin",
        quality_score=0.84,
    ),
    TrainingPair(
        natural_language="show git log with one line per commit for last 20 commits",
        bash_command="git log --oneline -20",
        source="builtin",
        quality_score=0.65,
    ),
    TrainingPair(
        natural_language="find the largest files in the current directory tree",
        bash_command="find . -type f -exec du -h {} + | sort -rh | head -20",
        source="builtin",
        quality_score=0.82,
    ),
    TrainingPair(
        natural_language="download a file and verify its sha256 checksum",
        bash_command="curl -sLO https://example.com/file.tar.gz && sha256sum file.tar.gz",
        source="builtin",
        quality_score=0.80,
    ),
    TrainingPair(
        natural_language="show all environment variables containing PATH",
        bash_command='env | grep PATH',
        source="builtin",
        quality_score=0.60,
    ),
    TrainingPair(
        natural_language="start a local http server on port 8000",
        bash_command="python3 -m http.server 8000",
        source="builtin",
        quality_score=0.70,
    ),
    TrainingPair(
        natural_language="remove all stopped docker containers",
        bash_command="docker container prune -f",
        source="builtin",
        quality_score=0.73,
    ),
    TrainingPair(
        natural_language="tail the nginx error log in real time",
        bash_command="tail -f /var/log/nginx/error.log",
        source="builtin",
        quality_score=0.72,
    ),
    TrainingPair(
        natural_language="run a command every 5 seconds and highlight changes",
        bash_command='watch -n 5 "df -h"',
        source="builtin",
        quality_score=0.78,
    ),
    TrainingPair(
        natural_language="list all python files that contain the word import on line 1",
        bash_command='find . -name "*.py" -exec awk \'/^import/{print FILENAME}\' {} +',
        source="builtin",
        quality_score=0.85,
    ),
    TrainingPair(
        natural_language="show network connections in listen state",
        bash_command="ss -tlnp",
        source="builtin",
        quality_score=0.70,
    ),
    TrainingPair(
        natural_language="install a python package and write it to requirements.txt",
        bash_command="pip install requests && pip freeze | grep -i requests >> requirements.txt",
        source="builtin",
        quality_score=0.78,
    ),
    TrainingPair(
        natural_language="show all git commits by the current user this month",
        bash_command='git log --author="$(git config user.name)" --since="$(date +%Y-%m-01)" --oneline',
        source="builtin",
        quality_score=0.88,
    ),
    TrainingPair(
        natural_language="copy all jpg files from downloads to pictures preserving structure",
        bash_command='rsync -avR ~/Downloads/**/*.jpg ~/Pictures/',
        source="builtin",
        quality_score=0.82,
    ),
    TrainingPair(
        natural_language="show which processes are using the most swap",
        bash_command="for pid in $(ls /proc | grep -E '^[0-9]+$'); do swap=$(cat /proc/$pid/status 2>/dev/null | grep VmSwap | awk '{print $2}'); if [ -n \"$swap\" ] && [ \"$swap\" -gt 0 ]; then echo \"$swap kB PID $pid $(cat /proc/$pid/cmdline 2>/dev/null | tr '\\0' ' ')\"; fi; done | sort -rn | head",
        source="builtin",
        quality_score=0.90,
    ),
    TrainingPair(
        natural_language="list all unique IPs that connected via ssh",
        bash_command='grep "Accepted" /var/log/auth.log | awk \'{print $11}\' | sort -u',
        source="builtin",
        quality_score=0.84,
    ),
    TrainingPair(
        natural_language="show all files changed in the last git commit",
        bash_command="git diff-tree --no-commit-id --name-only -r HEAD",
        source="builtin",
        quality_score=0.75,
    ),
]


def extract_from_jsonl(
    jsonl_path: str | Path,
    fmt: str = "auto",
) -> list[TrainingPair]:
    """Extract training pairs from a JSONL file.

    Args:
        jsonl_path: Path to the JSONL trace file.
        fmt: Format — 'glint', 'armand0e', 'vfable', or 'auto'.
             Auto-detect tries each format and returns the first
             that produces results.

    Returns:
        List of TrainingPair objects, filtered for quality.
    """
    extractors = {
        "glint": extract_bash_from_glint,
        "armand0e": extract_bash_from_armand0e,
        "vfable": extract_bash_from_vfable,
    }

    if fmt == "auto":
        for name, extractor in extractors.items():
            try:
                pairs = extractor(jsonl_path)
                if pairs:
                    return pairs
            except Exception:
                continue
        return []

    extractor = extractors.get(fmt)
    if extractor is None:
        raise ValueError(f"Unknown format: {fmt!r}. Choose from: {', '.join(extractors)}")

    return extractor(jsonl_path)


def load_training_data(
    *paths: str | Path,
    fmt: str = "auto",
    include_builtin: bool = True,
    min_quality: float = 0.5,
) -> list[TrainingPair]:
    """Load and merge training data from multiple JSONL files.

    Args:
        *paths: Paths to JSONL trace files.
        fmt: Format for extraction ('auto', 'glint', 'armand0e', 'vfable').
        include_builtin: Whether to include the builtin example pairs.
        min_quality: Minimum quality score to include a pair.

    Returns:
        Deduplicated list of TrainingPair objects.
    """
    all_pairs: list[TrainingPair] = []

    if include_builtin:
        all_pairs.extend(BUILTIN_PAIRS)

    for path in paths:
        pairs = extract_from_jsonl(path, fmt=fmt)
        all_pairs.extend(pairs)

    # Deduplicate by (nl, cmd) key
    seen: set[tuple[str, str]] = set()
    deduped: list[TrainingPair] = []
    for pair in all_pairs:
        key = (pair.natural_language.lower().strip(), pair.bash_command.strip())
        if key not in seen:
            seen.add(key)
            deduped.append(pair)

    # Filter by quality score
    return [p for p in deduped if p.quality_score >= min_quality]
