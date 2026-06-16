"""Tests for documentation RAG."""

import pytest
from pathlib import Path
from anvil.codebase.docs_rag import DocumentationRAG, DocChunk, DocSearchResult


@pytest.fixture
def sample_docs(tmp_path):
    """Create sample documentation."""
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    
    (docs_dir / "getting-started.md").write_text("""# Getting Started

## Installation

Install Anvil with pip:

```bash
pip install anvil
```

## Quick Start

Run your first task:

```bash
anvil run "Fix the bug"
```

## Configuration

Create a config file in your project root.
""")
    
    (docs_dir / "api.md").write_text("""# API Reference

## Endpoints

### POST /run
Execute a task.

### GET /health
Health check.
""")
    
    return tmp_path


class TestDocumentationRAG:
    """Test DocumentationRAG functionality."""
    
    def test_index_documentation(self, sample_docs):
        """Test indexing documentation."""
        rag = DocumentationRAG(sample_docs)
        count = rag.index()
        
        assert count > 0
        assert rag.indexed is True
    
    def test_search_documentation(self, sample_docs):
        """Test searching documentation."""
        rag = DocumentationRAG(sample_docs)
        rag.index()
        
        results = rag.search("install")
        assert len(results) > 0
        assert "install" in results[0].chunk.content.lower()
    
    def test_get_context(self, sample_docs):
        """Test getting documentation context."""
        rag = DocumentationRAG(sample_docs)
        rag.index()
        
        context = rag.get_context("install")
        assert "install" in context.lower()
        assert "documentation" in context.lower() or "Getting Started" in context
    
    def test_get_file_doc(self, sample_docs):
        """Test getting documentation for a specific file."""
        rag = DocumentationRAG(sample_docs)
        rag.index()
        
        doc = rag.get_file_doc("getting-started.md")
        assert "Getting Started" in doc
    
    def test_search_empty(self, tmp_path):
        """Test search with no docs."""
        rag = DocumentationRAG(tmp_path)
        results = rag.search("test")
        assert len(results) == 0
    
    def test_search_limit(self, sample_docs):
        """Test search result limit."""
        rag = DocumentationRAG(sample_docs)
        rag.index()
        
        results = rag.search("install", limit=1)
        assert len(results) <= 1


class TestDocChunk:
    """Test DocChunk dataclass."""
    
    def test_create_chunk(self):
        """Test creating a doc chunk."""
        chunk = DocChunk(
            doc_path="docs/test.md",
            section="Installation",
            title="Installation",
            content="# Installation\n\nInstall with pip.",
            hash="abc123",
        )
        
        assert chunk.doc_path == "docs/test.md"
        assert chunk.section == "Installation"
        assert chunk.title == "Installation"
        assert chunk.hash == "abc123"


class TestDocSearchResult:
    """Test DocSearchResult dataclass."""
    
    def test_create_result(self):
        """Test creating a doc search result."""
        chunk = DocChunk(
            doc_path="docs/test.md",
            section="Test",
            title="Test",
            content="Test content",
        )
        result = DocSearchResult(chunk=chunk, score=1.5)
        
        assert result.chunk == chunk
        assert result.score == 1.5
