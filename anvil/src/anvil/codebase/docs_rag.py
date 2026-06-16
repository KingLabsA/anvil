"""Documentation RAG (Retrieval-Augmented Generation) for Anvil."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


@dataclass
class DocChunk:
    """A chunk of documentation."""
    doc_path: str
    section: str
    title: str
    content: str
    hash: str = ""


@dataclass
class DocSearchResult:
    """A documentation search result."""
    chunk: DocChunk
    score: float


class DocumentationRAG:
    """Search and use documentation with retrieval-augmented generation."""
    
    # Directories to search for documentation
    DOC_DIRS = [
        "docs",
        "doc",
        "documentation",
        ".github",
    ]
    
    # File extensions to index
    DOC_EXTENSIONS = {
        ".md", ".rst", ".txt", ".mdx",
    }
    
    def __init__(self, project_root: str | Path):
        self.project_root = Path(project_root)
        self.chunks: list[DocChunk] = []
        self.indexed = False
    
    def index(self) -> int:
        """Index all documentation files."""
        self.chunks = []
        
        for doc_dir_name in self.DOC_DIRS:
            doc_dir = self.project_root / doc_dir_name
            if not doc_dir.exists():
                continue
            
            for doc_file in doc_dir.rglob("*"):
                if doc_file.suffix not in self.DOC_EXTENSIONS:
                    continue
                
                try:
                    content = doc_file.read_text(encoding="utf-8")
                    rel_path = str(doc_file.relative_to(self.project_root))
                    chunks = self._chunk_doc(rel_path, content)
                    self.chunks.extend(chunks)
                except Exception:
                    continue
        
        self.indexed = True
        return len(self.chunks)
    
    def _chunk_doc(self, doc_path: str, content: str) -> list[DocChunk]:
        """Chunk a documentation file by sections."""
        chunks = []
        current_title = "Introduction"
        current_lines = []
        
        for line in content.split("\n"):
            # Detect section headers
            if re.match(r"^#{1,4}\s+", line):
                # Save previous section
                if current_lines:
                    chunks.append(DocChunk(
                        doc_path=doc_path,
                        section=current_title,
                        title=current_title,
                        content="\n".join(current_lines).strip(),
                        hash=hashlib.md5("\n".join(current_lines).encode()).hexdigest() if current_lines else "",
                    ))
                # Start new section
                current_title = line.lstrip("#").strip()
                current_lines = [line]
            else:
                current_lines.append(line)
        
        # Save last section
        if current_lines:
            chunks.append(DocChunk(
                doc_path=doc_path,
                section=current_title,
                title=current_title,
                content="\n".join(current_lines).strip(),
                hash=hashlib.md5("\n".join(current_lines).encode()).hexdigest() if current_lines else "",
            ))
        
        return chunks
    
    def search(self, query: str, limit: int = 5) -> list[DocSearchResult]:
        """Search documentation."""
        if not self.indexed:
            self.index()
        
        query_lower = query.lower()
        query_words = set(query_lower.split())
        
        results: list[DocSearchResult] = []
        
        for chunk in self.chunks:
            score = 0.0
            content_lower = chunk.content.lower()
            title_lower = chunk.title.lower()
            
            # Title match
            if query_lower in title_lower:
                score += 5.0
            
            # Keyword matches
            for word in query_words:
                if word in content_lower:
                    score += 1.0
            
            # Exact phrase match
            if query_lower in content_lower:
                score += 3.0
            
            if score > 0:
                results.append(DocSearchResult(chunk=chunk, score=score))
        
        results.sort(key=lambda x: x.score, reverse=True)
        return results[:limit]
    
    def get_context(self, query: str, max_chars: int = 4000) -> str:
        """Get relevant documentation context for a query."""
        results = self.search(query, limit=3)
        
        if not results:
            return ""
        
        context_parts = [f"Relevant documentation for: {query}"]
        total_chars = 0
        
        for result in results:
            content = result.chunk.content
            if total_chars + len(content) > max_chars:
                remaining = max_chars - total_chars
                content = content[:remaining] + "..."
            
            context_parts.append(
                f"\n## {result.chunk.title} (from {result.chunk.doc_path})\n\n{content}"
            )
            total_chars += len(content)
        
        return "\n".join(context_parts)
    
    def get_file_doc(self, file_path: str) -> str:
        """Get documentation for a specific file."""
        if not self.indexed:
            self.index()
        
        file_chunks = [c for c in self.chunks if file_path in c.doc_path]
        if not file_chunks:
            return ""
        
        return "\n\n".join(c.content for c in file_chunks)
