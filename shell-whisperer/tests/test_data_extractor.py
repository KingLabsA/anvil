"""Unit tests for shell_whisperer.data_extractor."""

import json
from pathlib import Path

import pytest

from shell_whisperer.data_extractor import (
    BUILTIN_PAIRS,
    TrainingPair,
    _check_safety,
    _clean_output,
    _is_high_quality,
    _quality_score,
    _synthesize_description,
    extract_bash_from_armand0e,
    extract_bash_from_glint,
    extract_bash_from_vfable,
    extract_from_jsonl,
    load_training_data,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def glint_jsonl(tmp_path: Path) -> Path:
    """Create a temporary Glint format JSONL file."""
    data = [
        {"type": "shell_intent", "intent": "find all python files over 100 lines"},
        {"type": "shell_command", "command": 'find . -name "*.py" -exec wc -l {} + | awk \'/ $1 > 100\'', "shell": "bash", "exit_code": 0},
        {"type": "shell_intent", "intent": "kill process on port 8080"},
        {"type": "shell_command", "command": "lsof -ti:8080 | xargs kill -9", "shell": "bash", "exit_code": 0},
        {"type": "shell_intent", "intent": "simple ls"},
        {"type": "shell_command", "command": "ls", "shell": "bash", "exit_code": 0},
        {"type": "shell_intent", "intent": "dangerous rm"},
        {"type": "shell_command", "command": "rm -rf /", "shell": "bash", "exit_code": 0},
        {"type": "shell_command", "command": "", "shell": "bash", "exit_code": 0},
    ]
    path = tmp_path / "glint.jsonl"
    with path.open("w") as f:
        for record in data:
            f.write(json.dumps(record) + "\n")
    return path


@pytest.fixture
def armand0e_jsonl(tmp_path: Path) -> Path:
    """Create a temporary armand0e format JSONL file."""
    data = [
        {"event": "command_executed", "prompt": "show disk usage sorted by size", "command": "du -sh * | sort -rh", "exit_status": 0},
        {"event": "command_executed", "prompt": "list all docker containers", "command": "docker ps -a", "exit_status": 0},
        {"event": "command_executed", "prompt": None, "command": "git status", "exit_status": 0},
        {"event": "command_executed", "command": "ls", "exit_status": 1},
        {"event": "other_event", "command": "echo test", "exit_status": 0},
    ]
    path = tmp_path / "armand0e.jsonl"
    with path.open("w") as f:
        for record in data:
            f.write(json.dumps(record) + "\n")
    return path


@pytest.fixture
def vfable_jsonl(tmp_path: Path) -> Path:
    """Create a temporary v-Fable format JSONL file."""
    data = [
        {"role": "user", "utterance": "find all json files modified recently", "content": ""},
        {"role": "assistant", "tool_call": {"name": "execute_shell", "arguments": {"command": 'find . -name "*.json" -mtime -7'}}, "validation": {"confirmed": True, "exit_code": 0}},
        {"role": "user", "utterance": "show top processes by memory", "content": ""},
        {"role": "assistant", "tool_call": {"name": "execute_shell", "arguments": {"command": "ps aux --sort=-%mem | head -11"}}, "validation": {"confirmed": True, "exit_code": 0}},
        {"role": "user", "utterance": "unvalidated command", "content": ""},
        {"role": "assistant", "tool_call": {"name": "execute_shell", "arguments": {"command": "ls -la"}}, "validation": {"confirmed": False, "exit_code": 0}},
    ]
    path = tmp_path / "vfable.jsonl"
    with path.open("w") as f:
        for record in data:
            f.write(json.dumps(record) + "\n")
    return path


# ---------------------------------------------------------------------------
# Tests: _is_high_quality
# ---------------------------------------------------------------------------


class TestIsHighQuality:
    def test_short_command_rejected(self):
        assert not _is_high_quality("ls", "list files")

    def test_short_description_rejected(self):
        assert not _is_high_quality("find . -name '*.py' -exec wc -l {} +", "ab")

    def test_trivial_command_rejected(self):
        assert not _is_high_quality("pwd", "show current directory")

    def test_dangerous_command_rejected(self):
        assert not _is_high_quality("rm -rf /", "delete everything")

    def test_good_command_accepted(self):
        assert _is_high_quality(
            "find . -name '*.py' -exec wc -l {} + | awk '$1 > 100'",
            "find all python files over 100 lines"
        )

    def test_git_command_accepted(self):
        assert _is_high_quality(
            "git log --oneline -20",
            "show recent git log"
        )

    def test_simple_command_rejected_without_complex_features(self):
        assert not _is_high_quality("echo hello", "print hello")


# ---------------------------------------------------------------------------
# Tests: _check_safety
# ---------------------------------------------------------------------------


class TestCheckSafety:
    def test_dangerous_rm(self):
        warnings = _check_safety("rm -rf /")
        assert any("Destructive" in w for w in warnings)

    def test_curl_pipe_bash(self):
        warnings = _check_safety("curl http://example.com/script.sh | bash")
        assert any("piping" in w.lower() for w in warnings)

    def test_sudo_warning(self):
        warnings = _check_safety("sudo apt update")
        assert any("sudo" in w.lower() for w in warnings)

    def test_safe_command(self):
        warnings = _check_safety("find . -name '*.py'")
        assert len(warnings) == 0

    def test_fork_bomb(self):
        warnings = _check_safety(":(){ :|:& };:")
        assert any("Fork bomb" in w for w in warnings)

    def test_chmod_777(self):
        warnings = _check_safety("chmod 777 /")
        assert any("777" in w for w in warnings)


# ---------------------------------------------------------------------------
# Tests: _synthesize_description
# ---------------------------------------------------------------------------


class TestSynthesizeDescription:
    def test_find_pattern(self):
        desc = _synthesize_description('find . -name "*.py"')
        assert "find" in desc.lower()

    def test_git_pattern(self):
        desc = _synthesize_description("git log --oneline")
        assert "git" in desc.lower()

    def test_docker_pattern(self):
        desc = _synthesize_description("docker ps -a")
        assert "docker" in desc.lower()

    def test_kill_pattern(self):
        desc = _synthesize_description("kill -9 1234")
        assert "kill" in desc.lower()

    def test_unknown_fallback(self):
        desc = _synthesize_description("someunknowncmd")
        assert len(desc) > 0


# ---------------------------------------------------------------------------
# Tests: extract_bash_from_glint
# ---------------------------------------------------------------------------


class TestExtractGlint:
    def test_extracts_valid_pairs(self, glint_jsonl: Path):
        pairs = extract_bash_from_glint(glint_jsonl)
        assert len(pairs) >= 2  # two high-quality commands

    def test_filters_trivial_commands(self, glint_jsonl: Path):
        pairs = extract_bash_from_glint(glint_jsonl)
        commands = [p.bash_command for p in pairs]
        assert "ls" not in commands

    def test_filters_dangerous_commands(self, glint_jsonl: Path):
        pairs = extract_bash_from_glint(glint_jsonl)
        commands = [p.bash_command for p in pairs]
        assert "rm -rf /" not in commands

    def test_source_is_glint(self, glint_jsonl: Path):
        pairs = extract_bash_from_glint(glint_jsonl)
        for pair in pairs:
            assert pair.source == "glint"


# ---------------------------------------------------------------------------
# Tests: extract_bash_from_armand0e
# ---------------------------------------------------------------------------


class TestExtractArmand0e:
    def test_extracts_valid_pairs(self, armand0e_jsonl: Path):
        pairs = extract_bash_from_armand0e(armand0e_jsonl)
        assert len(pairs) >= 2

    def test_synthesizes_description_when_no_prompt(self, armand0e_jsonl: Path):
        pairs = extract_bash_from_armand0e(armand0e_jsonl)
        for pair in pairs:
            assert len(pair.natural_language) > 0

    def test_skips_failed_commands(self, armand0e_jsonl: Path):
        pairs = extract_bash_from_armand0e(armand0e_jsonl)
        commands = [p.bash_command for p in pairs]
        assert "ls" not in commands  # exit_status=1

    def test_source_is_armand0e(self, armand0e_jsonl: Path):
        pairs = extract_bash_from_armand0e(armand0e_jsonl)
        for pair in pairs:
            assert pair.source == "armand0e"


# ---------------------------------------------------------------------------
# Tests: extract_bash_from_vfable
# ---------------------------------------------------------------------------


class TestExtractVfable:
    def test_extracts_valid_pairs(self, vfable_jsonl: Path):
        pairs = extract_bash_from_vfable(vfable_jsonl)
        assert len(pairs) >= 2

    def test_skips_unvalidated(self, vfable_jsonl: Path):
        pairs = extract_bash_from_vfable(vfable_jsonl)
        commands = [p.bash_command for p in pairs]
        assert "ls -la" not in commands  # not confirmed

    def test_source_is_vfable(self, vfable_jsonl: Path):
        pairs = extract_bash_from_vfable(vfable_jsonl)
        for pair in pairs:
            assert pair.source == "vfable"


# ---------------------------------------------------------------------------
# Tests: extract_from_jsonl auto-detect
# ---------------------------------------------------------------------------


class TestExtractAuto:
    def test_auto_detect_glint(self, glint_jsonl: Path):
        pairs = extract_from_jsonl(glint_jsonl, fmt="auto")
        assert len(pairs) >= 2

    def test_auto_detect_armand0e(self, armand0e_jsonl: Path):
        pairs = extract_from_jsonl(armand0e_jsonl, fmt="auto")
        assert len(pairs) >= 1

    def test_invalid_format_raises(self):
        with pytest.raises(ValueError, match="Unknown format"):
            extract_from_jsonl("dummy.jsonl", fmt="invalid")


# ---------------------------------------------------------------------------
# Tests: load_training_data
# ---------------------------------------------------------------------------


class TestLoadTrainingData:
    def test_includes_builtin_by_default(self):
        pairs = load_training_data()
        assert len(pairs) >= len(BUILTIN_PAIRS)

    def test_excludes_builtin_when_requested(self):
        pairs = load_training_data(include_builtin=False)
        assert all(p.source != "builtin" for p in pairs)

    def test_quality_filter(self):
        pairs = load_training_data(min_quality=0.9)
        assert all(p.quality_score >= 0.9 for p in pairs)

    def test_deduplication(self, glint_jsonl: Path):
        pairs1 = load_training_data(str(glint_jsonl), include_builtin=True)
        keys = [(p.natural_language.lower().strip(), p.bash_command.strip()) for p in pairs1]
        assert len(keys) == len(set(keys))

    def test_training_pair_to_dict(self):
        pair = TrainingPair(
            natural_language="find all python files",
            bash_command='find . -name "*.py"',
            source="test",
            quality_score=0.8,
        )
        d = pair.to_dict()
        assert d["natural_language"] == "find all python files"
        assert d["bash_command"] == 'find . -name "*.py"'
        assert d["source"] == "test"
        assert d["quality_score"] == 0.8


# ---------------------------------------------------------------------------
# Tests: _clean_output
# ---------------------------------------------------------------------------


class TestCleanOutput:
    def test_removes_backticks(self):
        assert "find" in _clean_output("```bash\nfind . -name '*.py'\n```")

    def test_removes_prefix(self):
        assert _clean_output("Here is the command: find .").startswith("find")

    def test_preserves_pipes(self):
        cmd = "find . -name '*.py' | xargs grep TODO"
        assert _clean_output(cmd) == cmd

    def test_preserves_chaining(self):
        cmd = "mkdir -p dir && cd dir && git init"
        assert _clean_output(cmd) == cmd

    def test_removes_comments(self):
        result = _clean_output("# comment\nfind . -name '*.py'")
        assert not result.startswith("#")

    def test_strips_whitespace(self):
        assert _clean_output("  find .  ").strip() == "find ."


# ---------------------------------------------------------------------------
# Tests: _quality_score
# ---------------------------------------------------------------------------


class TestQualityScore:
    def test_basic_command_gets_base_score(self):
        score = _quality_score("git status", "show git status")
        assert 0.0 <= score <= 1.0

    def test_complex_command_gets_higher_score(self):
        score_simple = _quality_score("git log", "show log")
        score_complex = _quality_score(
            "find . -name '*.py' -exec wc -l {} + | awk '$1 > 100' | sort -rn",
            "find all python files over 100 lines sorted by line count"
        )
        assert score_complex > score_simple
