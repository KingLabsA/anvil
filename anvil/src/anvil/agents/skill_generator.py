"""Generate skills from patterns and examples."""

from __future__ import annotations

import json
import re
import textwrap
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class GeneratedSkill:
    """A generated skill with documentation and implementation."""

    name: str
    description: str
    skill_md: str
    implementation: str
    metadata: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    examples: list[str] = field(default_factory=list)


SKILL_MD_TEMPLATE = """\
# {name}

{description}

## When to use

{trigger_conditions}

## Steps

{steps}

## Verification

{verification}

## Examples

{examples}
"""


class SkillGenerator:
    """Generate skills from patterns and examples.

    Creates complete skill packages including SKILL.md documentation,
    implementation hints, and metadata. Skills are generated from
    pattern clusters, example task descriptions, or manual specifications.
    """

    def __init__(self, skills_dir: Path | None = None) -> None:
        self.skills_dir = skills_dir or Path.home() / ".anvil" / "skills"
        self.skills_dir.mkdir(parents=True, exist_ok=True)
        self._generated: dict[str, GeneratedSkill] = {}

    def generate_skill(self, name: str, examples: list[str], **kwargs: Any) -> GeneratedSkill:
        """Generate a skill from example task descriptions.

        Parameters
        ----------
        name : str
            Name for the skill.
        examples : list[str]
            Example task descriptions that this skill handles.
        **kwargs
            Additional metadata: ``description``, ``tags``, ``task_type``.

        Returns
        -------
        GeneratedSkill
            Complete generated skill.
        """
        description = kwargs.get("description", f"Auto-generated skill for {name}")
        tags = kwargs.get("tags", [])
        task_type = kwargs.get("task_type", "general")

        trigger_conditions = self._generate_triggers(name, examples, task_type)
        steps = self._generate_steps(examples, task_type)
        verification = self._generate_verification(task_type)
        examples_text = self._format_examples(examples)

        skill_md = SKILL_MD_TEMPLATE.format(
            name=name,
            description=description,
            trigger_conditions=trigger_conditions,
            steps=steps,
            verification=verification,
            examples=examples_text,
        )

        implementation = self._generate_implementation(name, task_type, steps)

        metadata = {
            "name": name,
            "description": description,
            "version": "0.1.0",
            "author": "anvil-auto",
            "tags": tags or [task_type],
            "task_type": task_type,
            "auto_generated": True,
        }

        skill = GeneratedSkill(
            name=name,
            description=description,
            skill_md=skill_md,
            implementation=implementation,
            metadata=metadata,
            tags=tags or [task_type],
            examples=examples[:5],
        )

        self._generated[name] = skill
        return skill

    def generate_from_pattern_cluster(
        self,
        cluster_id: str,
        label: str,
        patterns: list[dict[str, Any]],
    ) -> GeneratedSkill:
        """Generate a skill from a pattern cluster.

        Parameters
        ----------
        cluster_id : str
            Identifier for the source cluster.
        label : str
            Human-readable label for the cluster.
        patterns : list[dict]
            Pattern dicts with ``description``, ``task_type``, ``verification_steps``.

        Returns
        -------
        GeneratedSkill
            Skill generated from the cluster patterns.
        """
        name = self._cluster_to_name(cluster_id, label)
        examples = [p.get("description", "") for p in patterns[:5] if p.get("description")]
        task_type = patterns[0].get("task_type", "general") if patterns else "general"

        verify_steps: list[str] = []
        for p in patterns:
            verify_steps.extend(p.get("verification_steps", []))
        verify_steps = list(dict.fromkeys(verify_steps))[:5]

        description = f"Skill for {label} tasks (from Fable-5 cluster {cluster_id})"

        trigger_lines = [f"- User asks to {label.lower()}", f"- Task involves {task_type} patterns"]
        trigger_conditions = "\n".join(trigger_lines)

        step_lines: list[str] = []
        for i, p in enumerate(patterns[:5], 1):
            desc = p.get("description", f"Step {i}")
            step_lines.append(f"{i}. {desc}")
        steps = "\n".join(step_lines) if step_lines else "1. Analyze the task\n2. Execute changes\n3. Verify results"

        verification = "\n".join(f"- {v}" for v in verify_steps) if verify_steps else "- Run tests\n- Check lint"

        examples_text = "\n".join(f"- {ex}" for ex in examples) if examples else "- (no examples)"

        skill_md = SKILL_MD_TEMPLATE.format(
            name=name,
            description=description,
            trigger_conditions=trigger_conditions,
            steps=steps,
            verification=verification,
            examples=examples_text,
        )

        implementation = self._generate_implementation(name, task_type, steps)

        metadata = {
            "name": name,
            "description": description,
            "version": "0.1.0",
            "author": "anvil-auto",
            "tags": [task_type],
            "source_cluster": cluster_id,
            "auto_generated": True,
        }

        skill = GeneratedSkill(
            name=name,
            description=description,
            skill_md=skill_md,
            implementation=implementation,
            metadata=metadata,
            tags=[task_type],
            examples=examples,
        )

        self._generated[name] = skill
        return skill

    def register_skill(self, skill: GeneratedSkill) -> Path:
        """Register a generated skill by writing it to the skills directory.

        Creates a directory under ``skills_dir`` containing ``SKILL.md``
        and ``metadata.json``.

        Parameters
        ----------
        skill : GeneratedSkill
            The skill to register.

        Returns
        -------
        Path
            Path to the created skill directory.
        """
        skill_dir = self.skills_dir / skill.name
        skill_dir.mkdir(parents=True, exist_ok=True)

        skill_md_path = skill_dir / "SKILL.md"
        skill_md_path.write_text(skill.skill_md, encoding="utf-8")

        metadata_path = skill_dir / "metadata.json"
        metadata_path.write_text(json.dumps(skill.metadata, indent=2), encoding="utf-8")

        if skill.implementation:
            impl_path = skill_dir / "impl.py"
            impl_path.write_text(skill.implementation, encoding="utf-8")

        return skill_dir

    def list_generated(self) -> list[GeneratedSkill]:
        """Return all skills generated in this session.

        Returns
        -------
        list[GeneratedSkill]
            Generated skills.
        """
        return list(self._generated.values())

    # ── private helpers ────────────────────────────────────────────────

    def _generate_triggers(self, name: str, examples: list[str], task_type: str) -> str:
        lines = [
            f"- User asks to perform {task_type} tasks",
            f"- Task matches patterns like: {name}",
        ]
        for ex in examples[:3]:
            lines.append(f'- Example: "{ex[:80]}"')
        return "\n".join(lines)

    def _generate_steps(self, examples: list[str], task_type: str) -> str:
        step_templates: dict[str, list[str]] = {
            "auth": [
                "Identify the authentication framework in use",
                "Locate existing auth configuration",
                "Implement or update authentication logic",
                "Add authorization checks where needed",
                "Test authentication flow",
                "Verify no security regressions",
            ],
            "api": [
                "Identify the API framework and existing routes",
                "Define the new endpoint(s) and request/response schemas",
                "Implement the endpoint handler",
                "Add input validation and error handling",
                "Write tests for the new endpoint",
                "Verify with integration tests",
            ],
            "database": [
                "Analyze existing schema and migrations",
                "Design the new table(s) or migration",
                "Write the migration code",
                "Apply migration and verify schema",
                "Update any affected queries or models",
                "Run tests to verify data integrity",
            ],
            "testing": [
                "Identify the test framework in use",
                "Analyze the code to be tested",
                "Write unit tests for happy path",
                "Write tests for edge cases and errors",
                "Run tests and verify coverage",
                "Fix any failing tests",
            ],
            "frontend": [
                "Identify the UI framework and component library",
                "Analyze existing component patterns",
                "Implement the new component or page",
                "Add responsive styles",
                "Test across viewports",
                "Verify accessibility",
            ],
            "debugging": [
                "Reproduce the issue",
                "Identify the root cause",
                "Implement the fix",
                "Verify the fix resolves the issue",
                "Check for regressions",
                "Add regression test if applicable",
            ],
        }

        steps = step_templates.get(task_type, [
            "Analyze the current codebase and task requirements",
            "Identify relevant files and dependencies",
            "Plan the implementation approach",
            "Implement the changes",
            "Run tests and verification",
            "Review changes for correctness",
        ])
        return "\n".join(f"{i}. {step}" for i, step in enumerate(steps, 1))

    def _generate_verification(self, task_type: str) -> str:
        common = [
            "- Run relevant tests",
            "- Check lint/typecheck passes",
            "- Verify no regressions in existing functionality",
        ]
        task_specific: dict[str, list[str]] = {
            "auth": ["- Verify auth flow end-to-end", "- Check for security vulnerabilities"],
            "api": ["- Test all endpoint methods", "- Verify response schemas"],
            "database": ["- Verify migration applied correctly", "- Check data integrity"],
            "testing": ["- Verify coverage meets threshold", "- Check all edge cases covered"],
            "frontend": ["- Test responsive layout", "- Verify accessibility compliance"],
            "debugging": ["- Confirm original issue is resolved", "- Add regression test"],
        }
        specific = task_specific.get(task_type, [])
        return "\n".join(common + specific)

    def _format_examples(self, examples: list[str]) -> str:
        if not examples:
            return "- (no examples provided)"
        return "\n".join(f'- "{ex}"' for ex in examples[:5])

    def _generate_implementation(self, name: str, task_type: str, steps: str) -> str:
        return textwrap.dedent(f"""\
            \"\"\"Implementation hints for the {name} skill.

            Auto-generated — review and customize as needed.
            \"\"\"

            from __future__ import annotations

            from typing import Any


            SKILL_NAME = "{name}"
            TASK_TYPE = "{task_type}"


            def get_checklist() -> list[str]:
                \"\"\"Return the verification checklist for this skill.\"\"\"
                return [
                    "Analyze the codebase",
                    "Plan the approach",
                    "Implement changes",
                    "Run tests",
                    "Verify results",
                ]


            def get_tools() -> list[str]:
                \"\"\"Return recommended tools for this skill.\"\"\"
                tool_map = {{
                    "auth": ["bash", "read", "edit", "write", "grep"],
                    "api": ["bash", "read", "edit", "write", "grep", "glob"],
                    "database": ["bash", "read", "edit", "write"],
                    "testing": ["bash", "read", "write", "grep", "glob"],
                    "frontend": ["bash", "read", "edit", "write", "grep", "glob"],
                    "debugging": ["bash", "read", "grep", "glob", "edit"],
                    "general": ["bash", "read", "write", "edit", "grep", "glob"],
                }}
                return tool_map.get(TASK_TYPE, tool_map["general"])
            """)

    def _cluster_to_name(self, cluster_id: str, label: str) -> str:
        clean = re.sub(r"[^a-zA-Z0-9_]", "_", label.lower())
        clean = re.sub(r"_+", "_", clean).strip("_")
        name = f"auto_{clean}" if clean else f"auto_{cluster_id}"
        return name[:40]
