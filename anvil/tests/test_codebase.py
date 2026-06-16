"""Tests for codebase indexer."""

import pytest
from pathlib import Path
from anvil.codebase.indexer import CodebaseIndex, CodeChunk, SearchResult


@pytest.fixture
def sample_project(tmp_path):
    """Create a sample project for testing."""
    # Create Python files
    (tmp_path / "main.py").write_text("""import os
from utils import helper

def main():
    print("Hello, world!")

class App:
    def __init__(self):
        self.name = "test"
""")
    
    (tmp_path / "utils.py").write_text("""def helper():
    return "helper"

class Calculator:
    def add(self, a, b):
        return a + b
""")
    
    # Create JS file
    (tmp_path / "index.js").write_text("""import React from 'react';

function App() {
    return <div>Hello</div>;
}

class Component extends React.Component {
    render() {
        return <div>Component</div>;
    }
}
""")
    
    # Create non-indexable file
    (tmp_path / "image.png").write_bytes(b'\x89PNG\r\n\x1a\n')
    
    return tmp_path


class TestCodebaseIndex:
    """Test CodebaseIndex functionality."""
    
    def test_index_project(self, sample_project):
        """Test indexing a project."""
        indexer = CodebaseIndex(sample_project)
        count = indexer.index()
        
        assert count > 0
        stats = indexer.get_stats()
        assert stats["indexed"] is True
        assert stats["total_chunks"] > 0
        assert stats["total_files"] > 0
    
    def test_index_detects_languages(self, sample_project):
        """Test language detection."""
        indexer = CodebaseIndex(sample_project)
        indexer.index()
        
        stats = indexer.get_stats()
        assert "python" in stats["languages"]
        assert "javascript" in stats["languages"]
    
    def test_index_excludes_non_indexable(self, sample_project):
        """Test that non-indexable files are excluded."""
        indexer = CodebaseIndex(sample_project)
        indexer.index()
        
        # Should not index .png files
        languages = indexer.get_stats()["languages"]
        assert "png" not in languages
    
    def test_search_by_keyword(self, sample_project):
        """Test keyword search."""
        indexer = CodebaseIndex(sample_project)
        indexer.index()
        
        results = indexer.search("helper")
        assert len(results) > 0
        assert any("helper" in r.match_reason for r in results)
    
    def test_search_by_function(self, sample_project):
        """Test function name search."""
        indexer = CodebaseIndex(sample_project)
        indexer.index()
        
        results = indexer.search("main")
        assert len(results) > 0
    
    def test_search_by_class(self, sample_project):
        """Test class name search."""
        indexer = CodebaseIndex(sample_project)
        indexer.index()
        
        results = indexer.search("Component")
        assert len(results) > 0
    
    def test_search_limit(self, sample_project):
        """Test search result limit."""
        indexer = CodebaseIndex(sample_project)
        indexer.index()
        
        results = indexer.search("function", limit=2)
        assert len(results) <= 2
    
    def test_get_file_context(self, sample_project):
        """Test getting file context."""
        indexer = CodebaseIndex(sample_project)
        indexer.index()
        
        context = indexer.get_file_context("main.py")
        assert "main" in context.lower()
    
    def test_get_related_files(self, sample_project):
        """Test finding related files."""
        indexer = CodebaseIndex(sample_project)
        indexer.index()
        
        related = indexer.get_related_files("main.py", limit=3)
        assert isinstance(related, list)
    
    def test_stats_empty_index(self, tmp_path):
        """Test stats for empty index."""
        indexer = CodebaseIndex(tmp_path)
        stats = indexer.get_stats()
        assert stats["indexed"] is False
    
    def test_stats_after_index(self, sample_project):
        """Test stats after indexing."""
        indexer = CodebaseIndex(sample_project)
        indexer.index()
        
        stats = indexer.get_stats()
        assert stats["indexed"] is True
        assert stats["total_chunks"] > 0
        assert stats["total_files"] > 0
        assert "python" in stats["languages"]


class TestCodeChunk:
    """Test CodeChunk dataclass."""
    
    def test_create_chunk(self):
        """Test creating a code chunk."""
        chunk = CodeChunk(
            file_path="test.py",
            line_start=1,
            line_end=10,
            content="def test(): pass",
            language="python",
            functions=["test"],
            classes=["TestClass"],
            imports=["os"],
            hash="abc123",
        )
        
        assert chunk.file_path == "test.py"
        assert chunk.line_start == 1
        assert chunk.line_end == 10
        assert chunk.language == "python"
        assert chunk.functions == ["test"]
        assert chunk.classes == ["TestClass"]
        assert chunk.imports == ["os"]
        assert chunk.hash == "abc123"


class TestSearchResult:
    """Test SearchResult dataclass."""
    
    def test_create_result(self):
        """Test creating a search result."""
        chunk = CodeChunk(
            file_path="test.py",
            line_start=1,
            line_end=10,
            content="test",
            language="python",
        )
        result = SearchResult(chunk=chunk, score=1.5, match_reason="keyword match")
        
        assert result.chunk == chunk
        assert result.score == 1.5
        assert result.match_reason == "keyword match"
