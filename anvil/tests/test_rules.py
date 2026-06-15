"""Tests for Anvil rules system — AGENTS.md, .anvil/rules/, global rules, merging."""

from pathlib import Path

import pytest

from anvil.rules.rules_manager import Rule, RulesManager


class TestRule:
    def test_rule_creation(self):
        rule = Rule(source="test.md", content="Be helpful", priority=100)
        assert rule.source == "test.md"
        assert rule.content == "Be helpful"
        assert rule.priority == 100

    def test_rule_default_priority(self):
        rule = Rule(source="test.md", content="test")
        assert rule.priority == 0


class TestRulesManager:
    def test_init_with_default_root(self):
        mgr = RulesManager()
        assert mgr.project_root.exists()

    def test_init_with_custom_root(self, tmp_path):
        mgr = RulesManager(project_root=str(tmp_path))
        assert mgr.project_root == tmp_path


# ---------------------------------------------------------------------------
# Load AGENTS.md from project root
# ---------------------------------------------------------------------------

class TestLoadAgentsMd:
    def test_load_agents_md(self, tmp_path):
        agents_md = tmp_path / "AGENTS.md"
        agents_md.write_text("# Project Rules\n\nAlways write tests.\n\nBe concise.")
        mgr = RulesManager(project_root=str(tmp_path))
        rules = mgr.load_all()
        agents_rules = [r for r in rules if "AGENTS.md" in r.source]
        assert len(agents_rules) >= 1
        assert "Always write tests" in agents_rules[0].content

    def test_load_agents_md_priority(self, tmp_path):
        agents_md = tmp_path / "AGENTS.md"
        agents_md.write_text("Project root rule")
        mgr = RulesManager(project_root=str(tmp_path))
        rules = mgr.load_all()
        agents_rule = [r for r in rules if "AGENTS.md" in r.source]
        assert any(r.priority == 100 for r in agents_rule)

    def test_no_agents_md(self, tmp_path):
        mgr = RulesManager(project_root=str(tmp_path))
        rules = mgr.load_all()
        agents_rules = [r for r in rules if "AGENTS.md" in r.source]
        assert len(agents_rules) == 0


# ---------------------------------------------------------------------------
# Parse rules from markdown
# ---------------------------------------------------------------------------

class TestParseMarkdown:
    def test_parse_sections(self):
        text = """# General Rules

Always write tests.

## Style

Use 4-space indentation.

## Naming

Use snake_case for functions."""
        sections = RulesManager.parse_markdown(text)
        assert len(sections) >= 2
        assert any("Style" in s for s in sections)

    def test_parse_single_section(self):
        text = "Just one section with no headers."
        sections = RulesManager.parse_markdown(text)
        assert len(sections) == 1

    def test_parse_empty_text(self):
        sections = RulesManager.parse_markdown("")
        assert len(sections) == 0


# ---------------------------------------------------------------------------
# Load from .anvil/rules/
# ---------------------------------------------------------------------------

class TestLoadAnvilRules:
    def test_load_rules_directory(self, tmp_path):
        rules_dir = tmp_path / ".anvil" / "rules"
        rules_dir.mkdir(parents=True)
        (rules_dir / "style.md").write_text("# Style Rules\n\nUse 4-space indentation.")
        mgr = RulesManager(project_root=str(tmp_path))
        rules = mgr.load_all()
        style_rules = [r for r in rules if "style" in r.source.lower()]
        assert len(style_rules) >= 1

    def test_rules_directory_priority(self, tmp_path):
        rules_dir = tmp_path / ".anvil" / "rules"
        rules_dir.mkdir(parents=True)
        (rules_dir / "style.md").write_text("Style rule")
        mgr = RulesManager(project_root=str(tmp_path))
        rules = mgr.load_all()
        anvil_rules = [r for r in rules if ".anvil/rules" in r.source]
        assert any(r.priority == 50 for r in anvil_rules)

    def test_multiple_rule_files(self, tmp_path):
        rules_dir = tmp_path / ".anvil" / "rules"
        rules_dir.mkdir(parents=True)
        (rules_dir / "a.md").write_text("Rule A")
        (rules_dir / "b.md").write_text("Rule B")
        (rules_dir / "c.md").write_text("Rule C")
        mgr = RulesManager(project_root=str(tmp_path))
        rules = mgr.load_all()
        anvil_rules = [r for r in rules if ".anvil/rules" in r.source]
        assert len(anvil_rules) == 3


# ---------------------------------------------------------------------------
# Global rules from ~/.config/anvil/rules/
# ---------------------------------------------------------------------------

class TestGlobalRules:
    def test_global_rules_loading(self):
        global_dir = Path.home() / ".config" / "anvil" / "rules"
        if not global_dir.exists():
            pytest.skip("Global rules directory does not exist")
        mgr = RulesManager()
        rules = mgr.load_all()
        global_rules = [r for r in rules if ".config/anvil" in r.source]
        for rule in global_rules:
            assert rule.priority == 10


# ---------------------------------------------------------------------------
# Merge project + global rules
# ---------------------------------------------------------------------------

class TestMergeRules:
    def test_merged_rules_sorted_by_priority(self, tmp_path):
        agents_md = tmp_path / "AGENTS.md"
        agents_md.write_text("High priority rule from AGENTS.md")
        rules_dir = tmp_path / ".anvil" / "rules"
        rules_dir.mkdir(parents=True)
        (rules_dir / "local.md").write_text("Medium priority rule")
        mgr = RulesManager(project_root=str(tmp_path))
        rules = mgr.load_all()
        priorities = [r.priority for r in rules]
        for i in range(len(priorities) - 1):
            assert priorities[i] >= priorities[i + 1]

    def test_merged_content_contains_all(self, tmp_path):
        agents_md = tmp_path / "AGENTS.md"
        agents_md.write_text("AGENTS.md content")
        rules_dir = tmp_path / ".anvil" / "rules"
        rules_dir.mkdir(parents=True)
        (rules_dir / "extra.md").write_text("Extra rule content")
        mgr = RulesManager(project_root=str(tmp_path))
        content = mgr.get_merged_content()
        assert "AGENTS.md content" in content
        assert "Extra rule content" in content


# ---------------------------------------------------------------------------
# Glob pattern expansion (.cursor/rules/*.md)
# ---------------------------------------------------------------------------

class TestGlobPatterns:
    def test_load_cursor_rules(self, tmp_path):
        cursor_dir = tmp_path / ".cursor" / "rules"
        cursor_dir.mkdir(parents=True)
        (cursor_dir / "guide.md").write_text("Cursor rule content")
        mgr = RulesManager(project_root=str(tmp_path))
        rules = mgr.load_all()
        cursor_rules = [r for r in rules if ".cursor" in r.source]
        assert len(cursor_rules) >= 1
        assert "Cursor rule content" in cursor_rules[0].content

    def test_cursor_rules_priority(self, tmp_path):
        cursor_dir = tmp_path / ".cursor" / "rules"
        cursor_dir.mkdir(parents=True)
        (cursor_dir / "guide.md").write_text("Cursor rule")
        mgr = RulesManager(project_root=str(tmp_path))
        rules = mgr.load_all()
        cursor_rules = [r for r in rules if ".cursor" in r.source]
        assert any(r.priority == 30 for r in cursor_rules)


# ---------------------------------------------------------------------------
# Instructions config option
# ---------------------------------------------------------------------------

class TestInstructionsConfig:
    def test_load_instructions(self):
        mgr = RulesManager()
        mgr.load_instructions("Always be helpful and concise.")
        rules = mgr._rules
        assert any(r.content == "Always be helpful and concise." for r in rules)

    def test_instructions_priority(self):
        mgr = RulesManager()
        mgr.load_instructions("Test instruction")
        rules = mgr._rules
        assert any(r.priority == 90 for r in rules)

    def test_empty_instructions_ignored(self):
        mgr = RulesManager()
        mgr.load_instructions("")
        rules = mgr._rules
        assert all("config:instructions" not in r.source for r in rules)

    def test_instructions_with_other_rules(self, tmp_path):
        agents_md = tmp_path / "AGENTS.md"
        agents_md.write_text("Project rule")
        mgr = RulesManager(project_root=str(tmp_path))
        mgr.load_all()
        mgr.load_instructions("Config instruction")
        assert any("Config instruction" in r.content for r in mgr._rules)
        assert any("Project rule" in r.content for r in mgr._rules)
