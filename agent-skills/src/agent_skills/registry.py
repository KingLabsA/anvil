"""Skill registry: install, publish, list, and download agent skills."""

from __future__ import annotations

import json
import logging
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.request import urlopen

import yaml

logger = logging.getLogger(__name__)

SKILLS_DIR = Path.home() / ".agent_skills"
REGISTRY_URL = "https://agentskills.org/api/v1"
LOCAL_REGISTRY = SKILLS_DIR / "registry.json"


@dataclass
class SkillMeta:
    """Metadata for a skill definition."""

    name: str
    version: str = "0.1.0"
    description: str = ""
    category: str = "general"
    tools: list[str] = field(default_factory=list)
    triggers: list[str] = field(default_factory=list)
    author: str = ""
    license: str = "MIT"
    tags: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    install_path: str | None = None
    downloaded: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "category": self.category,
            "tools": self.tools,
            "triggers": self.triggers,
            "author": self.author,
            "license": self.license,
            "tags": self.tags,
            "dependencies": self.dependencies,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SkillMeta:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    @classmethod
    def from_yaml(cls, path: str | Path) -> SkillMeta:
        path = Path(path)
        with open(path) as f:
            data = yaml.safe_load(f)
        meta = cls.from_dict(data)
        meta.install_path = str(path.parent)
        return meta


class SkillRegistry:
    """Registry for managing agent skills.

    Install, publish, list, and download skill definitions that capture
    recurring patterns from agent behavior (traces).
    """

    def __init__(self, registry_dir: str | Path | None = None):
        self.registry_dir = Path(registry_dir) if registry_dir else SKILLS_DIR
        self.registry_dir.mkdir(parents=True, exist_ok=True)
        self._skills: dict[str, SkillMeta] = {}
        self._load_registry()

    def _load_registry(self) -> None:
        """Load the local skill registry from disk."""
        if LOCAL_REGISTRY.exists():
            with open(LOCAL_REGISTRY) as f:
                data = json.load(f)
            self._skills = {name: SkillMeta.from_dict(meta) for name, meta in data.items()}
        else:
            self._load_builtin_skills()

    def _load_builtin_skills(self) -> None:
        """Load built-in skill definitions."""
        builtin_dir = Path(__file__).parent / "skills"
        if builtin_dir.exists():
            for yaml_file in builtin_dir.glob("*.yaml"):
                try:
                    meta = SkillMeta.from_yaml(yaml_file)
                    meta.downloaded = True
                    self._skills[meta.name] = meta
                except Exception as e:
                    logger.warning(f"Failed to load skill {yaml_file}: {e}")

    def _save_registry(self) -> None:
        """Persist the skill registry to disk."""
        data = {name: meta.to_dict() for name, meta in self._skills.items()}
        with open(LOCAL_REGISTRY, "w") as f:
            json.dump(data, f, indent=2)

    def install(self, skill_name: str, source: str | None = None) -> SkillMeta:
        """Install a skill from the registry or a local path.

        Args:
            skill_name: Name of the skill to install.
            source: Optional local path or URL to install from.

        Returns:
            The installed SkillMeta.

        Raises:
            ValueError: If the skill is not found.
        """
        if source and Path(source).exists():
            return self._install_from_path(skill_name, source)

        # Check local registry first
        if skill_name in self._skills:
            meta = self._skills[skill_name]
            meta.downloaded = True
            self._save_registry()
            logger.info(f"Skill '{skill_name}' installed (local)")
            return meta

        # Try loading from built-in skills
        builtin_path = Path(__file__).parent / "skills" / f"{skill_name}.yaml"
        if builtin_path.exists():
            meta = SkillMeta.from_yaml(builtin_path)
            meta.downloaded = True
            self._skills[skill_name] = meta
            self._save_registry()
            logger.info(f"Skill '{skill_name}' installed (builtin)")
            return meta

        raise ValueError(f"Skill '{skill_name}' not found. Available: {list(self._skills.keys())}")

    def _install_from_path(self, skill_name: str, source: str) -> SkillMeta:
        """Install a skill from a local file path."""
        source_path = Path(source)

        if source_path.is_dir():
            yaml_files = list(source_path.glob("*.yaml"))
            if not yaml_files:
                raise ValueError(f"No YAML files found in {source}")
            yaml_path = yaml_files[0]
        elif source_path.suffix in (".yaml", ".yml"):
            yaml_path = source_path
        else:
            raise ValueError(f"Unsupported file type: {source}")

        meta = SkillMeta.from_yaml(yaml_path)
        meta.name = skill_name
        meta.install_path = str(source_path.parent if source_path.is_file() else source_path)
        meta.downloaded = True

        # Copy skill files to local registry
        dest = self.registry_dir / "installed" / skill_name
        dest.mkdir(parents=True, exist_ok=True)
        if source_path.is_dir():
            shutil.copytree(source_path, dest, dirs_exist_ok=True)
        else:
            shutil.copy2(source_path, dest / source_path.name)

        meta.install_path = str(dest)
        self._skills[skill_name] = meta
        self._save_registry()

        logger.info(f"Skill '{skill_name}' installed from {source}")
        return meta

    def publish(self, skill_path: str | Path) -> SkillMeta:
        """Publish a skill to the local registry.

        Args:
            skill_path: Path to the skill YAML definition file.

        Returns:
            The published SkillMeta.
        """
        skill_path = Path(skill_path)
        meta = SkillMeta.from_yaml(skill_path)

        # Copy to published directory
        dest = self.registry_dir / "published" / meta.name
        dest.mkdir(parents=True, exist_ok=True)
        shutil.copy2(skill_path, dest / skill_path.name)
        if skill_path.parent.is_dir():
            for other_file in skill_path.parent.iterdir():
                if other_file != skill_path and other_file.is_file():
                    shutil.copy2(other_file, dest / other_file.name)

        meta.install_path = str(dest)
        self._skills[meta.name] = meta
        self._save_registry()

        logger.info(f"Skill '{meta.name}' v{meta.version} published")
        return meta

    def list_skills(self, category: str | None = None) -> list[SkillMeta]:
        """List all installed and available skills.

        Args:
            category: Optional filter by category.

        Returns:
            List of SkillMeta objects.
        """
        skills = list(self._skills.values())
        if category:
            skills = [s for s in skills if s.category == category]
        return sorted(skills, key=lambda s: s.name)

    def download(self, skill_name: str) -> SkillMeta:
        """Download a skill from the remote registry.

        Args:
            skill_name: Name of the skill to download.

        Returns:
            The downloaded SkillMeta.

        Raises:
            ValueError: If the skill is not found in the remote registry.
        """
        # Attempt to download from remote registry
        try:
            url = f"{REGISTRY_URL}/skills/{skill_name}"
            with urlopen(url, timeout=10) as response:
                data = json.loads(response.read())
            meta = SkillMeta.from_dict(data)
            meta.downloaded = True

            dest = self.registry_dir / "downloaded" / skill_name
            dest.mkdir(parents=True, exist_ok=True)
            with open(dest / "skill.yaml", "w") as f:
                yaml.dump(data, f)
            meta.install_path = str(dest)

            self._skills[skill_name] = meta
            self._save_registry()
            logger.info(f"Skill '{skill_name}' downloaded from registry")
            return meta
        except Exception as e:
            logger.warning(f"Failed to download from remote: {e}")
            # Fall back to local/builtin
            if skill_name in self._skills:
                return self._skills[skill_name]
            raise ValueError(f"Skill '{skill_name}' not found locally or remotely")

    def get_skill(self, skill_name: str) -> SkillMeta | None:
        """Get a specific skill by name.

        Args:
            skill_name: Name of the skill.

        Returns:
            SkillMeta or None if not found.
        """
        return self._skills.get(skill_name)

    def uninstall(self, skill_name: str) -> bool:
        """Uninstall a skill from the local registry.

        Args:
            skill_name: Name of the skill to uninstall.

        Returns:
            True if the skill was uninstalled, False if not found.
        """
        if skill_name not in self._skills:
            return False

        meta = self._skills[skill_name]
        if meta.install_path and Path(meta.install_path).exists():
            shutil.rmtree(Path(meta.install_path), ignore_errors=True)

        del self._skills[skill_name]
        self._save_registry()
        logger.info(f"Skill '{skill_name}' uninstalled")
        return True
