"""Tests for extension system."""

import pytest
import json
from pathlib import Path
from anvil.extensions.manager import ExtensionManager, ExtensionMetadata


@pytest.fixture
def temp_extensions_dir(tmp_path):
    """Create a temporary extensions directory."""
    ext_dir = tmp_path / "extensions"
    ext_dir.mkdir()
    return ext_dir


@pytest.fixture
def sample_extension(tmp_path):
    """Create a sample extension."""
    ext_dir = tmp_path / "sample-ext"
    ext_dir.mkdir()
    
    # Create extension.json
    manifest = {
        "name": "sample-ext",
        "version": "0.1.0",
        "description": "Sample extension",
        "author": "Test",
        "main": "main.py",
        "tools": ["sample_tool"],
        "hooks": ["on_task_start"],
    }
    (ext_dir / "extension.json").write_text(json.dumps(manifest))
    
    # Create main.py
    main_code = """
def sample_tool(input_text: str) -> str:
    return f"Processed: {input_text}"

def on_task_start(task: str) -> None:
    pass
"""
    (ext_dir / "main.py").write_text(main_code)
    
    return ext_dir


class TestExtensionManager:
    """Test ExtensionManager functionality."""
    
    def test_create_manager(self, temp_extensions_dir):
        """Test creating an extension manager."""
        mgr = ExtensionManager(extensions_dir=temp_extensions_dir)
        assert mgr is not None
        assert mgr.extensions_dir == temp_extensions_dir
    
    def test_install_extension(self, temp_extensions_dir, sample_extension):
        """Test installing an extension."""
        mgr = ExtensionManager(extensions_dir=temp_extensions_dir)
        metadata = mgr.install(str(sample_extension))
        
        assert metadata.name == "sample-ext"
        assert metadata.version == "0.1.0"
        assert "sample_tool" in metadata.tools
        assert "on_task_start" in metadata.hooks
    
    def test_list_extensions(self, temp_extensions_dir, sample_extension):
        """Test listing extensions."""
        mgr = ExtensionManager(extensions_dir=temp_extensions_dir)
        mgr.install(str(sample_extension))
        
        exts = mgr.list_extensions()
        assert len(exts) == 1
        assert exts[0].name == "sample-ext"
    
    def test_get_extension(self, temp_extensions_dir, sample_extension):
        """Test getting an extension by name."""
        mgr = ExtensionManager(extensions_dir=temp_extensions_dir)
        mgr.install(str(sample_extension))
        
        ext = mgr.get_extension("sample-ext")
        assert ext is not None
        assert ext.metadata.name == "sample-ext"
        assert ext.enabled is True
    
    def test_enable_disable_extension(self, temp_extensions_dir, sample_extension):
        """Test enabling and disabling extensions."""
        mgr = ExtensionManager(extensions_dir=temp_extensions_dir)
        mgr.install(str(sample_extension))
        
        # Disable
        assert mgr.disable("sample-ext") is True
        ext = mgr.get_extension("sample-ext")
        assert ext.enabled is False
        
        # Enable
        assert mgr.enable("sample-ext") is True
        ext = mgr.get_extension("sample-ext")
        assert ext.enabled is True
    
    def test_uninstall_extension(self, temp_extensions_dir, sample_extension):
        """Test uninstalling an extension."""
        mgr = ExtensionManager(extensions_dir=temp_extensions_dir)
        mgr.install(str(sample_extension))
        
        assert mgr.uninstall("sample-ext") is True
        assert mgr.get_extension("sample-ext") is None
        assert len(mgr.list_extensions()) == 0
    
    def test_get_tool(self, temp_extensions_dir, sample_extension):
        """Test getting a tool from an extension."""
        mgr = ExtensionManager(extensions_dir=temp_extensions_dir)
        mgr.install(str(sample_extension))
        
        tool = mgr.get_tool("sample_tool")
        assert tool is not None
        result = tool("test")
        assert result == "Processed: test"
    
    def test_list_tools(self, temp_extensions_dir, sample_extension):
        """Test listing all tools from extensions."""
        mgr = ExtensionManager(extensions_dir=temp_extensions_dir)
        mgr.install(str(sample_extension))
        
        tools = mgr.list_tools()
        assert "sample_tool" in tools
    
    def test_call_hook(self, temp_extensions_dir, sample_extension):
        """Test calling hooks."""
        mgr = ExtensionManager(extensions_dir=temp_extensions_dir)
        mgr.install(str(sample_extension))
        
        # Should not raise
        results = mgr.call_hook("on_task_start", "test task")
        assert isinstance(results, list)
    
    def test_disabled_extension_tools_not_available(self, temp_extensions_dir, sample_extension):
        """Test that disabled extensions' tools are not available."""
        mgr = ExtensionManager(extensions_dir=temp_extensions_dir)
        mgr.install(str(sample_extension))
        
        # Tool should be available
        assert mgr.get_tool("sample_tool") is not None
        
        # Disable extension
        mgr.disable("sample-ext")
        
        # Tool should not be available
        assert mgr.get_tool("sample_tool") is None
    
    def test_install_nonexistent_source(self, temp_extensions_dir):
        """Test installing from a nonexistent source."""
        mgr = ExtensionManager(extensions_dir=temp_extensions_dir)
        
        with pytest.raises(Exception):
            mgr.install("/nonexistent/path")
    
    def test_uninstall_nonexistent_extension(self, temp_extensions_dir):
        """Test uninstalling a nonexistent extension."""
        mgr = ExtensionManager(extensions_dir=temp_extensions_dir)
        
        assert mgr.uninstall("nonexistent") is False
    
    def test_enable_nonexistent_extension(self, temp_extensions_dir):
        """Test enabling a nonexistent extension."""
        mgr = ExtensionManager(extensions_dir=temp_extensions_dir)
        
        assert mgr.enable("nonexistent") is False
    
    def test_disable_nonexistent_extension(self, temp_extensions_dir):
        """Test disabling a nonexistent extension."""
        mgr = ExtensionManager(extensions_dir=temp_extensions_dir)
        
        assert mgr.disable("nonexistent") is False


class TestExtensionMetadata:
    """Test ExtensionMetadata dataclass."""
    
    def test_create_metadata(self):
        """Test creating extension metadata."""
        metadata = ExtensionMetadata(
            name="test-ext",
            version="1.0.0",
            description="Test extension",
            author="Test Author",
            tools=["tool1", "tool2"],
            hooks=["hook1"],
        )
        
        assert metadata.name == "test-ext"
        assert metadata.version == "1.0.0"
        assert metadata.description == "Test extension"
        assert metadata.author == "Test Author"
        assert metadata.tools == ["tool1", "tool2"]
        assert metadata.hooks == ["hook1"]
    
    def test_metadata_defaults(self):
        """Test metadata default values."""
        metadata = ExtensionMetadata(
            name="test",
            version="0.1.0",
            description="",
            author="",
        )
        
        assert metadata.tools == []
        assert metadata.hooks == []
