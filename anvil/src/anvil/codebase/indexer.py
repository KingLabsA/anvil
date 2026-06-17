"""Codebase embeddings and semantic search for Anvil."""

from __future__ import annotations

import json
import hashlib
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional
import re

logger = logging.getLogger(__name__)


@dataclass
class CodeChunk:
    """A chunk of code with metadata."""
    file_path: str
    line_start: int
    line_end: int
    content: str
    language: str
    functions: list[str] = field(default_factory=list)
    classes: list[str] = field(default_factory=list)
    imports: list[str] = field(default_factory=list)
    hash: str = ""
    embedding: Optional[list[float]] = field(default=None, repr=False)


@dataclass
class SearchResult:
    """A search result with relevance score."""
    chunk: CodeChunk
    score: float
    match_reason: str


class CodebaseIndex:
    """Index and search the codebase using embeddings."""
    
    # File extensions to index
    INDEXABLE_EXTENSIONS = {
        ".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".go", ".rs",
        ".rb", ".php", ".sql", ".yaml", ".yml", ".json", ".toml",
        ".md", ".txt", ".html", ".css", ".scss", ".vue", ".svelte",
    }
    
    # Directories to skip
    SKIP_DIRS = {
        "node_modules", ".git", "__pycache__", ".venv", "venv",
        "dist", "build", ".next", ".nuxt", "coverage", ".mypy_cache",
        "target", "vendor", ".bundle", ".tox", ".eggs",
    }
    
    def __init__(self, project_root: str | Path, embedding_model: str = "all-MiniLM-L6-v2"):
        self.project_root = Path(project_root)
        self.embedding_model = embedding_model
        self.chunks: list[CodeChunk] = []
        self.file_hashes: dict[str, str] = {}
        self.indexed = False
        self._vector_index = None
        self._embedding_model_instance = None
    
    def index(self, max_files: int = 1000) -> int:
        """Index the codebase by chunking files.
        
        Args:
            max_files: Maximum number of files to index
            
        Returns:
            Number of chunks created
        """
        self.chunks = []
        file_count = 0
        
        for file_path in self._walk_files():
            if file_count >= max_files:
                break
            
            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
                if not content.strip():
                    continue
                
                # Calculate hash for change detection
                file_hash = hashlib.md5(content.encode()).hexdigest()
                rel_path = str(file_path.relative_to(self.project_root))
                
                # Skip unchanged files
                if rel_path in self.file_hashes and self.file_hashes[rel_path] == file_hash:
                    continue
                self.file_hashes[rel_path] = file_hash
                
                # Chunk the file
                language = self._detect_language(file_path)
                chunks = self._chunk_file(rel_path, content, language)
                self.chunks.extend(chunks)
                file_count += 1
                
            except Exception:
                continue
        
        self.indexed = True
        return len(self.chunks)
    
    def _walk_files(self):
        """Walk the project directory and yield indexable files."""
        for file_path in sorted(self.project_root.rglob("*")):
            if not file_path.is_file():
                continue
            
            # Skip non-indexable extensions
            if file_path.suffix not in self.INDEXABLE_EXTENSIONS:
                continue
            
            # Skip hidden/special directories
            rel_path = str(file_path.relative_to(self.project_root))
            if any(part.startswith(".") or part in self.SKIP_DIRS for part in rel_path.split("/")):
                continue
            
            yield file_path
    
    def _detect_language(self, file_path: Path) -> str:
        """Detect programming language from file extension."""
        ext_map = {
            ".py": "python", ".js": "javascript", ".ts": "typescript",
            ".jsx": "javascript", ".tsx": "typescript", ".java": "java",
            ".go": "go", ".rs": "rust", ".rb": "ruby", ".php": "php",
            ".sql": "sql", ".yaml": "yaml", ".yml": "yaml",
            ".json": "json", ".toml": "toml", ".md": "markdown",
            ".html": "html", ".css": "css", ".scss": "scss",
            ".vue": "vue", ".svelte": "svelte",
        }
        return ext_map.get(file_path.suffix.lower(), "text")
    
    def _chunk_file(self, file_path: str, content: str, language: str, max_lines: int = 100) -> list[CodeChunk]:
        """Chunk a file into smaller pieces."""
        lines = content.split("\n")
        chunks = []
        
        # Try to chunk by function/class boundaries
        boundaries = self._find_boundaries(lines, language)
        
        if boundaries:
            # Chunk at boundaries
            for i, start in enumerate(boundaries):
                end = boundaries[i + 1] if i + 1 < len(boundaries) else len(lines)
                chunk_lines = lines[start:end]
                chunk_content = "\n".join(chunk_lines).strip()
                
                if chunk_content:
                    chunk = CodeChunk(
                        file_path=file_path,
                        line_start=start + 1,
                        line_end=end,
                        content=chunk_content,
                        language=language,
                        functions=self._extract_functions(chunk_content, language),
                        classes=self._extract_classes(chunk_content, language),
                        imports=self._extract_imports(chunk_content, language),
                        hash=hashlib.md5(chunk_content.encode()).hexdigest(),
                    )
                    chunks.append(chunk)
        else:
            # Fallback: chunk by line count
            for i in range(0, len(lines), max_lines):
                chunk_lines = lines[i:i + max_lines]
                chunk_content = "\n".join(chunk_lines).strip()
                if chunk_content:
                    chunk = CodeChunk(
                        file_path=file_path,
                        line_start=i + 1,
                        line_end=min(i + max_lines, len(lines)),
                        content=chunk_content,
                        language=language,
                        functions=self._extract_functions(chunk_content, language),
                        classes=self._extract_classes(chunk_content, language),
                        imports=self._extract_imports(chunk_content, language),
                        hash=hashlib.md5(chunk_content.encode()).hexdigest(),
                    )
                    chunks.append(chunk)
        
        return chunks
    
    def _find_boundaries(self, lines: list[str], language: str) -> list[int]:
        """Find function/class boundaries in code."""
        boundaries = [0]
        
        if language in ("python",):
            for i, line in enumerate(lines):
                stripped = line.strip()
                if re.match(r"^(def |class |async def )", stripped):
                    if i not in boundaries:
                        boundaries.append(i)
        elif language in ("javascript", "typescript", "java", "go", "rust"):
            for i, line in enumerate(lines):
                stripped = line.strip()
                if re.match(r"^(function |class |const |let |var |export |async |pub |fn )", stripped):
                    if i not in boundaries:
                        boundaries.append(i)
        elif language in ("html", "vue", "svelte"):
            for i, line in enumerate(lines):
                stripped = line.strip()
                if re.match(r"^(<script|<template|<style|<template>)", stripped):
                    if i not in boundaries:
                        boundaries.append(i)
        
        boundaries.append(len(lines))
        return sorted(set(boundaries))
    
    def _extract_functions(self, content: str, language: str) -> list[str]:
        """Extract function names from code."""
        functions = []
        
        if language in ("python",):
            for match in re.finditer(r"(?:def|async\s+def)\s+(\w+)", content):
                functions.append(match.group(1))
        elif language in ("javascript", "typescript"):
            for match in re.finditer(r"(?:function\s+(\w+)|(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?(?:function|\())", content):
                name = match.group(1) or match.group(2)
                if name:
                    functions.append(name)
        elif language == "go":
            for match in re.finditer(r"func\s+(?:\([^)]+\)\s+)?(\w+)", content):
                functions.append(match.group(1))
        elif language == "rust":
            for match in re.finditer(r"(?:pub\s+)?(?:async\s+)?fn\s+(\w+)", content):
                functions.append(match.group(1))
        
        return functions[:20]  # Limit to 20 functions per chunk
    
    def _extract_classes(self, content: str, language: str) -> list[str]:
        """Extract class names from code."""
        classes = []
        
        if language in ("python",):
            for match in re.finditer(r"class\s+(\w+)", content):
                classes.append(match.group(1))
        elif language in ("javascript", "typescript", "java"):
            for match in re.finditer(r"class\s+(\w+)", content):
                classes.append(match.group(1))
        
        return classes[:10]  # Limit to 10 classes per chunk
    
    def _extract_imports(self, content: str, language: str) -> list[str]:
        """Extract import statements from code."""
        imports = []
        
        if language == "python":
            for match in re.finditer(r"(?:from\s+(\S+)\s+)?import\s+(\S+)", content):
                imports.append(match.group(2) or match.group(1))
        elif language in ("javascript", "typescript"):
            for match in re.finditer(r"(?:import\s+\{[^}]+\}\s+from\s+['\"]([^'\"]+)['\"]|import\s+(\S+))", content):
                imports.append(match.group(1) or match.group(2))
        elif language == "go":
            for match in re.finditer(r'import\s+(?:\([^)]+\)|"([^"]+)")', content):
                if match.group(1):
                    imports.append(match.group(1))
        
        return imports[:10]  # Limit to 10 imports per chunk
    
    def search(self, query: str, limit: int = 10) -> list[SearchResult]:
        """Search the codebase using keyword matching.
        
        Args:
            query: Search query
            limit: Maximum number of results
            
        Returns:
            List of search results
        """
        if not self.indexed:
            self.index()
        
        query_lower = query.lower()
        query_words = set(query_lower.split())
        
        results: list[SearchResult] = []
        
        for chunk in self.chunks:
            score = 0.0
            reasons = []
            
            # Score by keyword matches in content
            content_lower = chunk.content.lower()
            for word in query_words:
                if word in content_lower:
                    score += 1.0
                    reasons.append(f"keyword '{word}' found")
            
            # Bonus for function/class matches
            for func in chunk.functions:
                if func.lower() in query_lower:
                    score += 3.0
                    reasons.append(f"function '{func}' matches")
            
            for cls in chunk.classes:
                if cls.lower() in query_lower:
                    score += 3.0
                    reasons.append(f"class '{cls}' matches")
            
            # Bonus for exact phrase match
            if query_lower in content_lower:
                score += 5.0
                reasons.append("exact phrase match")
            
            if score > 0:
                results.append(SearchResult(
                    chunk=chunk,
                    score=score,
                    match_reason=", ".join(reasons[:3]),
                ))
        
        # Sort by score descending
        results.sort(key=lambda x: x.score, reverse=True)
        return results[:limit]
    
    def get_file_context(self, file_path: str) -> str:
        """Get full context for a file."""
        if not self.indexed:
            self.index()
        
        file_chunks = [c for c in self.chunks if c.file_path == file_path]
        if not file_chunks:
            return ""
        
        context_parts = []
        for chunk in file_chunks:
            context_parts.append(f"Lines {chunk.line_start}-{chunk.line_end}:")
            context_parts.append(chunk.content)
        
        return "\n\n".join(context_parts)
    
    def get_related_files(self, file_path: str, limit: int = 5) -> list[str]:
        """Find files related to a given file based on imports and shared functions."""
        if not self.indexed:
            self.index()
        
        target_chunks = [c for c in self.chunks if c.file_path == file_path]
        if not target_chunks:
            return []
        
        # Get all imports and functions from target file
        all_imports = set()
        all_functions = set()
        for chunk in target_chunks:
            all_imports.update(chunk.imports)
            all_functions.update(chunk.functions)
        
        # Score other files by shared imports/functions
        file_scores: dict[str, float] = {}
        for chunk in self.chunks:
            if chunk.file_path == file_path:
                continue
            
            score = 0.0
            for imp in chunk.imports:
                if imp in all_imports:
                    score += 1.0
            
            for func in chunk.functions:
                if func in all_functions:
                    score += 2.0
            
            if score > 0:
                file_scores[chunk.file_path] = file_scores.get(chunk.file_path, 0) + score
        
        # Sort and return top files
        sorted_files = sorted(file_scores.items(), key=lambda x: x[1], reverse=True)
        return [f[0] for f in sorted_files[:limit]]
    
    def get_stats(self) -> dict[str, Any]:
        """Get index statistics."""
        if not self.indexed:
            return {"indexed": False}
        
        languages = {}
        for chunk in self.chunks:
            lang = chunk.language
            languages[lang] = languages.get(lang, 0) + 1
        
        files = set(c.file_path for c in self.chunks)
        
        return {
            "indexed": True,
            "total_chunks": len(self.chunks),
            "total_files": len(files),
            "languages": languages,
        }
    
    def save_index(self, path: str | Path) -> None:
        """Save the index to a file."""
        index_data = {
            "file_hashes": self.file_hashes,
            "chunks": [
                {
                    "file_path": c.file_path,
                    "line_start": c.line_start,
                    "line_end": c.line_end,
                    "language": c.language,
                    "functions": c.functions,
                    "classes": c.classes,
                    "imports": c.imports,
                    "hash": c.hash,
                }
                for c in self.chunks
            ],
        }
        Path(path).write_text(json.dumps(index_data, indent=2))
    
    def load_index(self, path: str | Path) -> bool:
        """Load the index from a file."""
        try:
            data = json.loads(Path(path).read_text())
            self.file_hashes = data.get("file_hashes", {})
            self.chunks = [
                CodeChunk(
                    file_path=c["file_path"],
                    line_start=c["line_start"],
                    line_end=c["line_end"],
                    content="",  # Content not stored in index
                    language=c["language"],
                    functions=c.get("functions", []),
                    classes=c.get("classes", []),
                    imports=c.get("imports", []),
                    hash=c.get("hash", ""),
                )
                for c in data.get("chunks", [])
            ]
            self.indexed = True
            return True
        except Exception:
            return False
    
    def build_semantic_index(self) -> bool:
        """Build semantic search index using embeddings.
        
        Returns:
            True if semantic index was built successfully, False otherwise
        """
        if not self.indexed:
            self.index()
        
        try:
            from sentence_transformers import SentenceTransformer
            import numpy as np
            
            logger.info(f"Loading embedding model: {self.embedding_model}")
            self._embedding_model_instance = SentenceTransformer(self.embedding_model)
            
            # Generate embeddings for all chunks
            texts = [chunk.content for chunk in self.chunks]
            if not texts:
                logger.warning("No chunks to embed")
                return False
            
            logger.info(f"Generating embeddings for {len(texts)} chunks")
            embeddings = self._embedding_model_instance.encode(
                texts,
                show_progress_bar=True,
                convert_to_numpy=True
            )
            
            # Attach embeddings to chunks
            for chunk, embedding in zip(self.chunks, embeddings):
                chunk.embedding = embedding.tolist()
            
            # Build FAISS index
            try:
                import faiss
                
                embeddings_array = embeddings.astype(np.float32)
                self._vector_index = faiss.IndexFlatL2(embeddings_array.shape[1])
                self._vector_index.add(embeddings_array)
                logger.info(f"Built FAISS index with {self._vector_index.ntotal} vectors")
                return True
                
            except ImportError:
                logger.warning("FAISS not available, semantic search will use numpy fallback")
                self._vector_index = embeddings
                return True
                
        except ImportError as e:
            logger.warning(f"Semantic indexing not available: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to build semantic index: {e}")
            return False
    
    def semantic_search(self, query: str, limit: int = 10) -> list[SearchResult]:
        """Search the codebase using semantic similarity.
        
        Args:
            query: Search query
            limit: Maximum number of results
            
        Returns:
            List of search results ranked by semantic similarity
        """
        if not self.indexed:
            self.index()
        
        # Build semantic index if not already built
        if self._vector_index is None:
            if not self.build_semantic_index():
                # Fall back to keyword search
                logger.info("Falling back to keyword search")
                return self.search(query, limit)
        
        try:
            import numpy as np
            
            # Generate query embedding
            query_embedding = self._embedding_model_instance.encode(
                [query],
                convert_to_numpy=True
            )[0]
            
            # Search
            if hasattr(self._vector_index, 'search'):
                # FAISS index
                distances, indices = self._vector_index.search(
                    np.array([query_embedding], dtype=np.float32),
                    min(limit, len(self.chunks))
                )
                
                results = []
                for idx, distance in zip(indices[0], distances[0]):
                    if idx < 0 or idx >= len(self.chunks):
                        continue
                    chunk = self.chunks[idx]
                    # Convert distance to similarity score (lower distance = higher score)
                    score = 1.0 / (1.0 + distance)
                    results.append(SearchResult(
                        chunk=chunk,
                        score=score,
                        match_reason="semantic similarity"
                    ))
                
                return results
            else:
                # Numpy fallback
                embeddings = self._vector_index
                query_vec = query_embedding.reshape(1, -1)
                
                # Calculate cosine similarity
                norms = np.linalg.norm(embeddings, axis=1) * np.linalg.norm(query_vec)
                similarities = np.dot(embeddings, query_vec.T).flatten() / norms
                
                # Get top indices
                top_indices = np.argsort(similarities)[-limit:][::-1]
                
                results = []
                for idx in top_indices:
                    chunk = self.chunks[idx]
                    results.append(SearchResult(
                        chunk=chunk,
                        score=float(similarities[idx]),
                        match_reason="semantic similarity"
                    ))
                
                return results
                
        except Exception as e:
            logger.error(f"Semantic search failed: {e}")
            # Fall back to keyword search
            return self.search(query, limit)
    
    def get_context_for_task(self, task: str, max_chunks: int = 10, use_semantic: bool = True) -> str:
        """Get relevant code context for a task.
        
        Args:
            task: Task description
            max_chunks: Maximum number of chunks to retrieve
            use_semantic: Whether to use semantic search (falls back to keyword if unavailable)
            
        Returns:
            Formatted context string with relevant code chunks
        """
        if use_semantic and self._vector_index is not None:
            results = self.semantic_search(task, limit=max_chunks)
        else:
            results = self.search(task, limit=max_chunks)
        
        if not results:
            return ""
        
        context_parts = []
        for result in results:
            chunk = result.chunk
            header = f"File: {chunk.file_path} (lines {chunk.line_start}-{chunk.line_end})"
            if result.match_reason != "semantic similarity":
                header += f" [{result.match_reason}]"
            context_parts.append(f"{header}\n{chunk.content}")
        
        return "\n\n".join(context_parts)
