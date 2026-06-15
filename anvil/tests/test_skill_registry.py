"""Tests for skill registry functionality."""

import json
import shutil
import tempfile
from pathlib import Path

import pytest

from anvil.skills.registry import SkillRegistry, SkillMetadata


@pytest.fixture
def temp_skills_dir(tmp_path):
    """Create a temporary skills directory."""
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    return skills_dir


@pytest.fixture
def sample_skill_dir(tmp_path):
    """Create a sample skill directory with SKILL.md."""
    skill_dir = tmp_path / "test-skill"
    skill_dir.mkdir()
    
    # Create SKILL.md
    skill_md = skill_dir / "SKILL.md"
    skill_md.write_text("""# Test Skill

Description: A test skill for unit testing
Version: 1.0.0
Author: Test Author
Tags: test, unit, testing

This is a test skill used for unit testing the skill registry.
""")
    
    # Create a sample script
    script = skill_dir / "script.py"
    script.write_text("print('Hello from test skill')")
    
    return skill_dir


@pytest.fixture
def registry(temp_skills_dir):
    """Create a SkillRegistry instance with temp directory."""
    return SkillRegistry(skills_dir=temp_skills_dir)


class TestSkillRegistry:
    """Test SkillRegistry functionality."""
    
    def test_init_creates_directory(self, tmp_path):
        """Test that registry creates skills directory if it doesn't exist."""
        skills_dir = tmp_path / "new_skills"
        assert not skills_dir.exists()
        registry = SkillRegistry(skills_dir=skills_dir)
        assert skills_dir.exists()
    
    def test_list_installed_empty(self, registry):
        """Test listing skills when none are installed."""
        skills = registry.list_installed()
        assert skills == []
    
    def test_install_from_path(self, registry, sample_skill_dir):
        """Test installing a skill from a local path."""
        skill = registry.install_from_path(sample_skill_dir)
        assert skill.name == "Test Skill"  # Extracted from SKILL.md
        assert skill.installed is True
        assert skill.version == "1.0.0"
        assert skill.author == "Test Author"
        assert "test" in skill.tags
        assert "unit" in skill.tags
        assert "testing" in skill.tags
    
    def test_install_from_path_custom_name(self, registry, sample_skill_dir):
        """Test installing with a custom name."""
        skill = registry.install_from_path(sample_skill_dir, skill_name="custom-name")
        # Custom name is used for directory, but metadata name comes from SKILL.md
        assert skill.name == "Test Skill"
        assert "custom-name" in skill.path
    
    def test_install_from_path_already_exists(self, registry, sample_skill_dir):
        """Test that installing an existing skill raises an error."""
        registry.install_from_path(sample_skill_dir)
        with pytest.raises(ValueError, match="already installed"):
            registry.install_from_path(sample_skill_dir)
    
    def test_install_from_path_invalid_path(self, registry, tmp_path):
        """Test installing from a non-existent path."""
        with pytest.raises(ValueError, match="does not exist"):
            registry.install_from_path(tmp_path / "nonexistent")
    
    def test_install_from_path_no_skill_md(self, registry, tmp_path):
        """Test installing from a path without SKILL.md."""
        skill_dir = tmp_path / "no-skill-md"
        skill_dir.mkdir()
        with pytest.raises(ValueError, match="No SKILL.md"):
            registry.install_from_path(skill_dir)
    
    def test_list_installed_after_install(self, registry, sample_skill_dir):
        """Test listing skills after installation."""
        registry.install_from_path(sample_skill_dir)
        skills = registry.list_installed()
        assert len(skills) == 1
        assert skills[0].name == "Test Skill"
        assert skills[0].installed is True
    
    def test_uninstall(self, registry, sample_skill_dir):
        """Test uninstalling a skill."""
        registry.install_from_path(sample_skill_dir)
        assert registry.uninstall("test-skill") is True
        skills = registry.list_installed()
        assert len(skills) == 0
    
    def test_uninstall_nonexistent(self, registry):
        """Test uninstalling a non-existent skill."""
        assert registry.uninstall("nonexistent") is False
    
    def test_get_skill(self, registry, sample_skill_dir):
        """Test getting skill metadata."""
        registry.install_from_path(sample_skill_dir)
        skill = registry.get_skill("test-skill")
        assert skill is not None
        assert skill.name == "Test Skill"
        assert skill.version == "1.0.0"
    
    def test_get_skill_nonexistent(self, registry):
        """Test getting a non-existent skill."""
        skill = registry.get_skill("nonexistent")
        assert skill is None
    
    def test_search_by_name(self, registry, sample_skill_dir):
        """Test searching skills by name."""
        registry.install_from_path(sample_skill_dir)
        results = registry.search("test")
        assert len(results) == 1
        assert results[0].name == "Test Skill"  # Extracted from SKILL.md
    
    def test_search_by_description(self, registry, sample_skill_dir):
        """Test searching skills by description."""
        registry.install_from_path(sample_skill_dir)
        results = registry.search("unit testing")
        assert len(results) == 1
    
    def test_search_by_tag(self, registry, sample_skill_dir):
        """Test searching skills by tag."""
        registry.install_from_path(sample_skill_dir)
        results = registry.search("testing")
        assert len(results) == 1
    
    def test_search_no_results(self, registry, sample_skill_dir):
        """Test searching with no matches."""
        registry.install_from_path(sample_skill_dir)
        results = registry.search("nonexistent")
        assert len(results) == 0
    
    def test_search_limit(self, registry, tmp_path):
        """Test search respects limit."""
        # Install multiple skills
        for i in range(5):
            skill_dir = tmp_path / f"skill-{i}"
            skill_dir.mkdir()
            (skill_dir / "SKILL.md").write_text(f"# Skill {i}\nDescription: Test skill {i}")
            registry.install_from_path(skill_dir)
        
        results = registry.search("skill", limit=3)
        assert len(results) == 3


class TestSkillMetadata:
    """Test SkillMetadata dataclass."""
    
    def test_create_metadata(self):
        """Test creating SkillMetadata."""
        metadata = SkillMetadata(
            name="test",
            description="Test skill",
            version="1.0.0",
            author="Author",
            tags=["tag1", "tag2"],
            source="https://github.com/test/test",
            installed=True,
            path="/path/to/skill"
        )
        assert metadata.name == "test"
        assert metadata.description == "Test skill"
        assert metadata.version == "1.0.0"
        assert metadata.author == "Author"
        assert metadata.tags == ["tag1", "tag2"]
        assert metadata.source == "https://github.com/test/test"
        assert metadata.installed is True
        assert metadata.path == "/path/to/skill"
    
    def test_metadata_defaults(self):
        """Test SkillMetadata default values."""
        metadata = SkillMetadata(name="test", description="Test")
        assert metadata.version == "0.1.0"
        assert metadata.author == ""
        assert metadata.tags == []
        assert metadata.source == ""
        assert metadata.installed is False
        assert metadata.path == ""


class TestMetadataExtraction:
    """Test metadata extraction from SKILL.md."""
    
    def test_extract_full_metadata(self, registry, sample_skill_dir):
        """Test extracting all metadata fields."""
        skill = registry.install_from_path(sample_skill_dir)
        assert skill.name == "Test Skill"  # From SKILL.md title
        assert skill.version == "1.0.0"
        assert skill.author == "Test Author"
        assert "test" in skill.tags
        assert "unit" in skill.tags
    
    def test_extract_minimal_metadata(self, registry, tmp_path):
        """Test extracting metadata from minimal SKILL.md."""
        skill_dir = tmp_path / "minimal-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("# Minimal Skill\n\nJust a description.")
        
        skill = registry.install_from_path(skill_dir)
        assert skill.name == "Minimal Skill"
        assert skill.description == "Just a description."
        assert skill.version == "0.1.0"  # Default
        assert skill.author == ""  # Default
    
    def test_metadata_json_saved(self, registry, sample_skill_dir):
        """Test that metadata.json is saved after installation."""
        registry.install_from_path(sample_skill_dir)
        metadata_file = registry.skills_dir / "test-skill" / "metadata.json"
        assert metadata_file.exists()
        
        data = json.loads(metadata_file.read_text())
        assert data["name"] == "Test Skill"
        assert data["version"] == "1.0.0"
        assert data["author"] == "Test Author"
