"""Skill registry — discover, install, and manage skills from GitHub and local sources."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class SkillMetadata:
    """Metadata for a skill."""
    name: str
    description: str
    version: str = "0.1.0"
    author: str = ""
    tags: list[str] = field(default_factory=list)
    source: str = ""  # GitHub URL or local path
    installed: bool = False
    path: str = ""


class SkillRegistry:
    """Registry for discovering and managing skills."""
    
    def __init__(self, skills_dir: Path | None = None):
        """Initialize skill registry.
        
        Args:
            skills_dir: Directory to store installed skills. Defaults to ~/.anvil/skills
        """
        self.skills_dir = skills_dir or (Path.home() / ".anvil" / "skills")
        self.skills_dir.mkdir(parents=True, exist_ok=True)
        self._cache: dict[str, SkillMetadata] = {}
    
    def list_installed(self) -> list[SkillMetadata]:
        """List all installed skills."""
        skills = []
        for skill_dir in self.skills_dir.iterdir():
            if skill_dir.is_dir():
                metadata_file = skill_dir / "metadata.json"
                if metadata_file.exists():
                    try:
                        data = json.loads(metadata_file.read_text())
                        skill = SkillMetadata(
                            name=data["name"],
                            description=data.get("description", ""),
                            version=data.get("version", "0.1.0"),
                            author=data.get("author", ""),
                            tags=data.get("tags", []),
                            source=data.get("source", ""),
                            installed=True,
                            path=str(skill_dir),
                        )
                        skills.append(skill)
                    except (json.JSONDecodeError, KeyError):
                        continue
        return skills
    
    def search(self, query: str, limit: int = 20) -> list[SkillMetadata]:
        """Search for skills by name, description, or tags.
        
        Args:
            query: Search query
            limit: Maximum number of results
            
        Returns:
            List of matching skills
        """
        results = []
        query_lower = query.lower()
        
        # Search installed skills
        for skill in self.list_installed():
            if (query_lower in skill.name.lower() or
                query_lower in skill.description.lower() or
                any(query_lower in tag.lower() for tag in skill.tags)):
                results.append(skill)
        
        # Search GitHub for skills (future: could use GitHub API)
        # For now, just return installed skills
        
        return results[:limit]
    
    def install_from_github(self, repo_url: str, skill_name: str | None = None) -> SkillMetadata:
        """Install a skill from a GitHub repository.
        
        Args:
            repo_url: GitHub repository URL
            skill_name: Name of the skill (defaults to repo name)
            
        Returns:
            Installed skill metadata
        """
        # Parse repo URL
        if not repo_url.startswith("https://github.com/"):
            raise ValueError("Only GitHub repositories are supported")
        
        # Extract owner/repo
        parts = repo_url.replace("https://github.com/", "").rstrip("/").split("/")
        if len(parts) < 2:
            raise ValueError("Invalid GitHub URL")
        
        owner, repo = parts[0], parts[1]
        
        # Default skill name to repo name
        if not skill_name:
            skill_name = repo
        
        # Check if already installed
        skill_dir = self.skills_dir / skill_name
        if skill_dir.exists():
            raise ValueError(f"Skill '{skill_name}' is already installed")
        
        # Clone repository
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            subprocess.run(
                ["git", "clone", "--depth", "1", repo_url, str(tmp_path / repo)],
                check=True,
                capture_output=True,
            )
            
            # Look for SKILL.md
            skill_md = tmp_path / repo / "SKILL.md"
            if not skill_md.exists():
                raise ValueError(f"No SKILL.md found in repository")
            
            # Copy to skills directory
            shutil.copytree(tmp_path / repo, skill_dir)
        
        # Create metadata
        metadata = self._extract_metadata(skill_dir, repo_url)
        metadata.installed = True
        metadata.path = str(skill_dir)
        
        # Save metadata
        metadata_file = skill_dir / "metadata.json"
        metadata_file.write_text(json.dumps({
            "name": metadata.name,
            "description": metadata.description,
            "version": metadata.version,
            "author": metadata.author,
            "tags": metadata.tags,
            "source": metadata.source,
        }, indent=2))
        
        return metadata
    
    def install_from_path(self, path: str | Path, skill_name: str | None = None) -> SkillMetadata:
        """Install a skill from a local path.
        
        Args:
            path: Local path to skill directory
            skill_name: Name for the skill (defaults to directory name)
            
        Returns:
            Installed skill metadata
        """
        source_path = Path(path)
        if not source_path.exists():
            raise ValueError(f"Path does not exist: {path}")
        
        if not source_path.is_dir():
            raise ValueError(f"Path is not a directory: {path}")
        
        # Look for SKILL.md
        skill_md = source_path / "SKILL.md"
        if not skill_md.exists():
            raise ValueError(f"No SKILL.md found in {path}")
        
        # Default skill name to directory name
        if not skill_name:
            skill_name = source_path.name
        
        # Check if already installed
        skill_dir = self.skills_dir / skill_name
        if skill_dir.exists():
            raise ValueError(f"Skill '{skill_name}' is already installed")
        
        # Copy to skills directory
        shutil.copytree(source_path, skill_dir)
        
        # Create metadata
        metadata = self._extract_metadata(skill_dir, str(source_path))
        metadata.installed = True
        metadata.path = str(skill_dir)
        
        # Save metadata
        metadata_file = skill_dir / "metadata.json"
        metadata_file.write_text(json.dumps({
            "name": metadata.name,
            "description": metadata.description,
            "version": metadata.version,
            "author": metadata.author,
            "tags": metadata.tags,
            "source": metadata.source,
        }, indent=2))
        
        return metadata
    
    def uninstall(self, skill_name: str) -> bool:
        """Uninstall a skill.
        
        Args:
            skill_name: Name of the skill to uninstall
            
        Returns:
            True if uninstalled, False if not found
        """
        skill_dir = self.skills_dir / skill_name
        if not skill_dir.exists():
            return False
        
        shutil.rmtree(skill_dir)
        return True
    
    def get_skill(self, skill_name: str) -> SkillMetadata | None:
        """Get metadata for a specific skill.
        
        Args:
            skill_name: Name of the skill
            
        Returns:
            Skill metadata or None if not found
        """
        skill_dir = self.skills_dir / skill_name
        if not skill_dir.exists():
            return None
        
        metadata_file = skill_dir / "metadata.json"
        if not metadata_file.exists():
            return None
        
        try:
            data = json.loads(metadata_file.read_text())
            return SkillMetadata(
                name=data["name"],
                description=data.get("description", ""),
                version=data.get("version", "0.1.0"),
                author=data.get("author", ""),
                tags=data.get("tags", []),
                source=data.get("source", ""),
                installed=True,
                path=str(skill_dir),
            )
        except (json.JSONDecodeError, KeyError):
            return None
    
    def _extract_metadata(self, skill_dir: Path, source: str) -> SkillMetadata:
        """Extract metadata from SKILL.md file.
        
        Args:
            skill_dir: Path to skill directory
            source: Source URL or path
            
        Returns:
            Skill metadata
        """
        skill_md = skill_dir / "SKILL.md"
        content = skill_md.read_text()
        
        # Parse metadata from SKILL.md
        # Look for YAML front matter or metadata section
        name = skill_dir.name
        description = ""
        version = "0.1.0"
        author = ""
        tags = []
        
        # Simple parsing: look for common patterns
        lines = content.split("\n")
        for line in lines[:20]:  # Check first 20 lines
            if line.startswith("# "):
                name = line[2:].strip()
            elif line.lower().startswith("description:"):
                description = line.split(":", 1)[1].strip()
            elif line.lower().startswith("version:"):
                version = line.split(":", 1)[1].strip()
            elif line.lower().startswith("author:"):
                author = line.split(":", 1)[1].strip()
            elif line.lower().startswith("tags:"):
                tags_str = line.split(":", 1)[1].strip()
                tags = [t.strip() for t in tags_str.split(",")]
        
        # If no description found, use first non-empty line after title
        if not description:
            for line in lines[1:]:
                line = line.strip()
                if line and not line.startswith("#"):
                    description = line[:200]
                    break
        
        return SkillMetadata(
            name=name,
            description=description,
            version=version,
            author=author,
            tags=tags,
            source=source,
        )
