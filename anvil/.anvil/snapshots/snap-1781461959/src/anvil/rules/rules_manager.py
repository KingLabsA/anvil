"""Rules manager — load, parse, and merge rule sources."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class Rule:
    """A single parsed rule."""
    source: str
    content: str
    priority: int = 0


class RulesManager:
    """Load, parse, and merge rules from multiple sources.

    Sources (in priority order):
      1. AGENTS.md in project root
      2. .anvil/rules/ directory (*.md files)
      3. Global rules from ~/.config/anvil/rules/
      4. Glob-expanded patterns (e.g. .cursor/rules/*.md)
      5. Config 'instructions' option
    """

    def __init__(self, project_root: str | None = None) -> None:
        self.project_root = Path(project_root) if project_root else Path.cwd()
        self._rules: list[Rule] = []

    def load_all(self) -> list[Rule]:
        """Load rules from all sources, merged by priority."""
        self._rules = []
        self._load_agents_md()
        self._load_anvil_rules_dir()
        self._load_global_rules()
        self._load_glob_patterns()
        return sorted(self._rules, key=lambda r: r.priority, reverse=True)

    def get_merged_content(self) -> str:
        """Get merged rule content from all sources."""
        if not self._rules:
            self.load_all()
        return "\n\n".join(r.content for r in self._rules)

    def _load_agents_md(self) -> None:
        """Load AGENTS.md from project root."""
        agents_path = self.project_root / "AGENTS.md"
        if agents_path.exists():
            content = agents_path.read_text(encoding="utf-8").strip()
            if content:
                self._rules.append(Rule(
                    source=str(agents_path),
                    content=content,
                    priority=100,
                ))

    def _load_anvil_rules_dir(self) -> None:
        """Load .anvil/rules/ directory."""
        rules_dir = self.project_root / ".anvil" / "rules"
        if not rules_dir.exists():
            return
        for f in sorted(rules_dir.glob("*.md")):
            content = f.read_text(encoding="utf-8").strip()
            if content:
                self._rules.append(Rule(
                    source=str(f),
                    content=content,
                    priority=50,
                ))

    def _load_global_rules(self) -> None:
        """Load global rules from ~/.config/anvil/rules/."""
        global_dir = Path.home() / ".config" / "anvil" / "rules"
        if not global_dir.exists():
            return
        for f in sorted(global_dir.glob("*.md")):
            content = f.read_text(encoding="utf-8").strip()
            if content:
                self._rules.append(Rule(
                    source=str(f),
                    content=content,
                    priority=10,
                ))

    def _load_glob_patterns(self) -> None:
        """Load from glob-expanded patterns like .cursor/rules/*.md."""
        cursor_dir = self.project_root / ".cursor" / "rules"
        if cursor_dir.exists():
            for f in sorted(cursor_dir.glob("*.md")):
                content = f.read_text(encoding="utf-8").strip()
                if content:
                    self._rules.append(Rule(
                        source=str(f),
                        content=content,
                        priority=30,
                    ))

    def load_instructions(self, instructions: str) -> None:
        """Add instructions from the config option."""
        if instructions.strip():
            self._rules.append(Rule(
                source="config:instructions",
                content=instructions.strip(),
                priority=90,
            ))

    @staticmethod
    def parse_markdown(text: str) -> list[str]:
        """Parse markdown into rule sections, splitting on ## headers."""
        sections: list[str] = []
        current: list[str] = []
        for line in text.split("\n"):
            if line.startswith("## ") and current:
                sections.append("\n".join(current).strip())
                current = []
            current.append(line)
        if current:
            sections.append("\n".join(current).strip())
        return [s for s in sections if s]
