"""AGENTS.md Rules System — load and merge rules from project and global configs."""

from __future__ import annotations

import fnmatch
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Rule:
    """A single rule extracted from a markdown file."""
    source: str
    content: str
    priority: int = 0
    pattern: str = ""  # glob pattern for file-type targeting

    def matches_file(self, filepath: str) -> bool:
        """Check if this rule applies to a given file path."""
        if not self.pattern:
            return True
        return fnmatch.fnmatch(filepath, self.pattern)


class RulesManager:
    """Load AGENTS.md rules from project root, .anvil/rules/, and global config.

    Rules are prepended to the system prompt to guide agent behavior.
    """

    def __init__(self, project_root: str | None = None, instructions: list[str] | None = None):
        self.project_root = Path(project_root) if project_root else Path.cwd()
        self.instructions = instructions or []
        self._rules: list[Rule] = []
        self._loaded_files: set[str] = set()

    def load_all(self) -> list[Rule]:
        """Load rules from all sources: global, project, and .anvil/rules/."""
        self._rules = []

        global_rules_dir = Path.home() / ".config" / "anvil" / "rules"
        if global_rules_dir.exists():
            for rule_file in sorted(global_rules_dir.glob("*.md")):
                self._load_rule_file(rule_file, source_type="global")

        self._load_agents_md(self.project_root / "AGENTS.md", source_type="project")
        self._load_agents_md(self.project_root / "CLAUDE.md", source_type="project")

        anvil_rules_dir = self.project_root / ".anvil" / "rules"
        if anvil_rules_dir.exists():
            for rule_file in sorted(anvil_rules_dir.glob("*.md")):
                self._load_rule_file(rule_file, source_type="project_rules")

        cursor_rules_dir = self.project_root / ".cursor" / "rules"
        if cursor_rules_dir.exists():
            for rule_file in sorted(cursor_rules_dir.glob("*.md")):
                self._load_rule_file(rule_file, source_type="cursor_rules")

        for instruction in self.instructions:
            rule = Rule(
                source="instruction",
                content=instruction,
                priority=100,
            )
            self._rules.append(rule)

        return self._rules

    def get_system_prompt_rules(self) -> str:
        """Format all rules for prepending to the system prompt."""
        if not self._rules:
            self.load_all()

        if not self._rules:
            return ""

        sections = []
        for rule in sorted(self._rules, key=lambda r: r.priority, reverse=True):
            header = f"[Rule from {rule.source}]"
            if rule.pattern:
                header += f" (applies to: {rule.pattern})"
            sections.append(f"{header}\n{rule.content}")

        return "# Rules\n\n" + "\n\n---\n\n".join(sections)

    def get_rules_for_file(self, filepath: str) -> list[Rule]:
        """Get rules that apply to a specific file."""
        if not self._rules:
            self.load_all()
        return [r for r in self._rules if r.matches_file(filepath)]

    def parse_rules(self, content: str, source: str = "") -> list[Rule]:
        """Extract rules from markdown content.

        Supports:
        - Plain text as rules
        - Code blocks marked as rules
        - Priority markers like [P0], [P1], [P2]
        - File pattern markers like [*.py], [*.ts]
        """
        rules = []
        current_section = ""
        current_lines: list[str] = []

        lines = content.split("\n")
        for line in lines:
            header_match = re.match(r'^(#{1,6})\s+(.+)$', line)
            if header_match:
                if current_lines and current_section:
                    rule = self._make_rule(current_lines, current_section, source)
                    if rule:
                        rules.append(rule)
                    current_lines = []

                current_section = header_match.group(2).strip()
                priority_match = re.search(r'\[P(\d)\]', current_section)
                if priority_match:
                    pass
                pattern_match = re.search(r'\[([\w.*?,]+)\]', current_section)
                if pattern_match:
                    pass
                continue

            current_lines.append(line)

        if current_lines and (current_section or current_lines):
            rule = self._make_rule(current_lines, current_section or "unnamed", source)
            if rule:
                rules.append(rule)

        if not rules and content.strip():
            rules.append(Rule(source=source, content=content.strip(), priority=0))

        return rules

    def _load_rule_file(self, path: Path, source_type: str = "") -> None:
        """Load rules from a markdown file."""
        str_path = str(path)
        if str_path in self._loaded_files:
            return
        if not path.exists():
            return

        try:
            content = path.read_text(encoding="utf-8")
        except OSError:
            return

        self._loaded_files.add(str_path)
        source_label = f"{source_type}:{path.name}" if source_type else path.name
        new_rules = self.parse_rules(content, source=source_label)
        self._rules.extend(new_rules)

    def _load_agents_md(self, path: Path, source_type: str = "") -> None:
        """Load an AGENTS.md or CLAUDE.md file."""
        str_path = str(path)
        if str_path in self._loaded_files:
            return
        if not path.exists():
            return

        try:
            content = path.read_text(encoding="utf-8")
        except OSError:
            return

        self._loaded_files.add(str_path)
        source_label = f"{source_type}:{path.name}" if source_type else path.name
        new_rules = self.parse_rules(content, source=source_label)

        for rule in new_rules:
            rule.priority += 10
        self._rules.extend(new_rules)

    def _make_rule(self, lines: list[str], section: str, source: str) -> Rule | None:
        """Create a Rule from accumulated lines and section header."""
        content = "\n".join(lines).strip()
        if not content:
            return None

        priority = 0
        priority_match = re.search(r'\[P(\d)\]', section)
        if priority_match:
            priority = int(priority_match.group(1))

        pattern = ""
        pattern_match = re.search(r'\[([\w.*?]+)\]', section)
        if pattern_match:
            pattern = pattern_match.group(1)

        return Rule(
            source=source,
            content=content,
            priority=priority,
            pattern=pattern,
        )
