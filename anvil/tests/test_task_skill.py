"""Tests for the OpenCode-ported task (subagent dispatch) and skill tools."""

from unittest.mock import MagicMock

import pytest

from anvil.core.config import AnvilConfig, ModelConfig
from anvil.core.engine import AnvilEngine, TOOL_DEFINITIONS, ALL_TOOL_NAMES


def _engine(tmp_path=None):
    cfg = AnvilConfig(model=ModelConfig(model="local"))
    if tmp_path is not None:
        cfg.project_root = str(tmp_path)
    return AnvilEngine(cfg)


class TestToolRegistration:
    def test_task_and_skill_registered(self):
        assert "task" in ALL_TOOL_NAMES
        assert "skill" in ALL_TOOL_NAMES

    def test_definitions_have_args(self):
        task = next(t for t in TOOL_DEFINITIONS if t["name"] == "task")
        assert "subagent_type" in task["args"]
        assert "prompt" in task["args"]
        skill = next(t for t in TOOL_DEFINITIONS if t["name"] == "skill")
        assert "name" in skill["args"]


class TestSkillTool:
    def test_skill_requires_name(self):
        eng = _engine()
        r = eng._run_skill({})
        assert r.success is False
        assert "name" in r.error

    def test_skill_not_found(self):
        eng = _engine()
        r = eng._run_skill({"name": "does-not-exist"})
        assert r.success is False
        assert "unknown skill" in r.error

    def test_skill_loads_content(self, tmp_path):
        skill_dir = tmp_path / "skills" / "demo"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("# Demo\n\nStep one.\n")
        eng = _engine(tmp_path)
        r = eng._run_skill({"name": "demo"})
        assert r.success is True
        assert "Skill: demo" in r.output
        assert "Step one." in r.output
        assert "Base directory" in r.output

    def test_available_skill_names(self, tmp_path):
        for name in ("alpha", "beta"):
            d = tmp_path / "skills" / name
            d.mkdir(parents=True)
            (d / "SKILL.md").write_text(f"# {name}")
        eng = _engine(tmp_path)
        assert eng._available_skill_names() == ["alpha", "beta"]


class TestTaskTool:
    def test_task_requires_subagent_type(self):
        eng = _engine()
        r = eng._run_task({"prompt": "do something"})
        assert r.success is False
        assert "subagent_type" in r.error

    def test_task_requires_prompt(self):
        eng = _engine()
        r = eng._run_task({"subagent_type": "explore"})
        assert r.success is False
        assert "prompt" in r.error

    def test_task_unknown_subagent(self):
        eng = _engine()
        r = eng._run_task({"subagent_type": "nope-xyz", "prompt": "x"})
        assert r.success is False
        assert "unknown subagent_type" in r.error

    def test_recursion_guard(self):
        eng = _engine()
        eng._is_subagent = True
        r = eng._run_task({"subagent_type": "explore", "prompt": "x"})
        assert r.success is False
        assert "recursion guard" in r.error

    def test_task_dispatches_subagent(self, monkeypatch):
        eng = _engine()

        # Stub the child engine run so we don't load a real model.
        from anvil.core import engine as engine_mod

        class _FakeResult:
            success = True
            output = "subagent done"
            error = None

        def _fake_run(self, prompt, max_iterations=10):
            return _FakeResult()

        monkeypatch.setattr(engine_mod.AnvilEngine, "run", _fake_run)

        r = eng._run_task(
            {"subagent_type": "explore", "prompt": "find the bug", "description": "hunt"}
        )
        assert r.success is True
        assert "subagent done" in r.output
        assert 'state="completed"' in r.output


class TestPressTool:
    def test_press_registered(self):
        from anvil.core.engine import ALL_TOOL_NAMES
        assert "press" in ALL_TOOL_NAMES

    def test_press_requires_service(self):
        eng = _engine()
        r = eng._run_press({"base_url": "https://x.com"})
        assert r.success is False
        assert "service" in r.error

    def test_press_requires_url_or_spec(self):
        eng = _engine()
        r = eng._run_press({"service": "X"})
        assert r.success is False
        assert "base_url" in r.error

    def test_press_generates_wrapper(self, tmp_path):
        eng = _engine(tmp_path)
        r = eng._run_press({"service": "Demo", "base_url": "https://api.demo.com"})
        assert r.success is True
        assert "Printing Press wrapper" in r.output
        assert "Demo" in r.output
