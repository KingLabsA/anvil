"""Agent memory system — persistent cross-session learning."""

from __future__ import annotations

import json
import time
import uuid
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any
from dataclasses import dataclass, field, asdict


class MemoryCategory(str, Enum):
    """Categories of memories."""
    PREFERENCE = "preference"  # User preferences
    PROJECT = "project"        # Project-specific context
    PATTERN = "pattern"        # Successful patterns
    MISTAKE = "mistake"        # Things to avoid
    FACT = "fact"              # General facts


@dataclass
class Memory:
    """A single memory item."""
    id: str
    category: MemoryCategory
    content: str
    context: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    last_used: str = field(default_factory=lambda: datetime.now().isoformat())
    use_count: int = 0
    importance: float = 0.5  # 0.0 to 1.0
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "category": self.category.value,
            "content": self.content,
            "context": self.context,
            "created_at": self.created_at,
            "last_used": self.last_used,
            "use_count": self.use_count,
            "importance": self.importance,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Memory:
        """Create from dictionary."""
        return cls(
            id=data["id"],
            category=MemoryCategory(data["category"]),
            content=data["content"],
            context=data.get("context", ""),
            created_at=data.get("created_at", datetime.now().isoformat()),
            last_used=data.get("last_used", datetime.now().isoformat()),
            use_count=data.get("use_count", 0),
            importance=data.get("importance", 0.5),
        )


class MemoryManager:
    """Manages agent memory storage and retrieval."""
    
    def __init__(self, memory_dir: Path | None = None):
        """Initialize memory manager.
        
        Args:
            memory_dir: Directory to store memories. Defaults to ~/.anvil/memory
        """
        self.memory_dir = memory_dir or (Path.home() / ".anvil" / "memory")
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self.memories: dict[str, Memory] = {}
        self._load_memories()
    
    def _load_memories(self) -> None:
        """Load all memories from disk."""
        memories_file = self.memory_dir / "memories.json"
        if memories_file.exists():
            try:
                data = json.loads(memories_file.read_text())
                self.memories = {
                    m["id"]: Memory.from_dict(m)
                    for m in data.get("memories", [])
                }
            except (json.JSONDecodeError, KeyError, ValueError):
                self.memories = {}
    
    def _save_memories(self) -> None:
        """Save all memories to disk."""
        memories_file = self.memory_dir / "memories.json"
        data = {
            "memories": [m.to_dict() for m in self.memories.values()],
            "updated_at": datetime.now().isoformat(),
        }
        memories_file.write_text(json.dumps(data, indent=2))
    
    def add(
        self,
        category: MemoryCategory,
        content: str,
        context: str = "",
        importance: float = 0.5,
    ) -> Memory:
        """Add a new memory.
        
        Args:
            category: Memory category
            content: Memory content
            context: Context in which this was learned
            importance: Importance score (0.0 to 1.0)
            
        Returns:
            Created memory
        """
        # Generate unique ID using uuid4 to avoid collisions
        mem_id = f"mem_{uuid.uuid4().hex[:12]}"
        
        memory = Memory(
            id=mem_id,
            category=category,
            content=content,
            context=context,
            importance=importance,
        )
        
        self.memories[mem_id] = memory
        self._save_memories()
        
        return memory
    
    def get(self, memory_id: str) -> Memory | None:
        """Get a memory by ID."""
        return self.memories.get(memory_id)
    
    def list(
        self,
        category: MemoryCategory | None = None,
        limit: int = 50,
    ) -> list[Memory]:
        """List memories, optionally filtered by category.
        
        Args:
            category: Filter by category
            limit: Maximum number of memories to return
            
        Returns:
            List of memories, sorted by importance and use_count
        """
        memories = list(self.memories.values())
        
        if category:
            memories = [m for m in memories if m.category == category]
        
        # Sort by importance (desc) then use_count (desc)
        memories.sort(key=lambda m: (m.importance, m.use_count), reverse=True)
        
        return memories[:limit]
    
    def recall(self, query: str, limit: int = 5) -> list[Memory]:
        """Recall relevant memories for a query.
        
        Simple keyword matching for now. Could be enhanced with embeddings.
        
        Args:
            query: Query string
            limit: Maximum memories to return
            
        Returns:
            List of relevant memories
        """
        query_lower = query.lower()
        query_words = set(query_lower.split())
        
        scored_memories = []
        for memory in self.memories.values():
            # Simple keyword matching
            content_lower = memory.content.lower()
            context_lower = memory.context.lower()
            
            # Count matching words
            matches = sum(1 for word in query_words if word in content_lower or word in context_lower)
            
            if matches > 0:
                # Score = matches * importance
                score = matches * memory.importance
                scored_memories.append((score, memory))
        
        # Sort by score descending
        scored_memories.sort(key=lambda x: x[0], reverse=True)
        
        return [m for _, m in scored_memories[:limit]]
    
    def use(self, memory_id: str) -> None:
        """Mark a memory as used (increments use_count, updates last_used)."""
        if memory_id in self.memories:
            memory = self.memories[memory_id]
            memory.use_count += 1
            memory.last_used = datetime.now().isoformat()
            self._save_memories()
    
    def update(
        self,
        memory_id: str,
        content: str | None = None,
        context: str | None = None,
        importance: float | None = None,
    ) -> Memory | None:
        """Update a memory.
        
        Args:
            memory_id: Memory ID
            content: New content (optional)
            context: New context (optional)
            importance: New importance (optional)
            
        Returns:
            Updated memory, or None if not found
        """
        if memory_id not in self.memories:
            return None
        
        memory = self.memories[memory_id]
        
        if content is not None:
            memory.content = content
        if context is not None:
            memory.context = context
        if importance is not None:
            memory.importance = max(0.0, min(1.0, importance))
        
        self._save_memories()
        return memory
    
    def delete(self, memory_id: str) -> bool:
        """Delete a memory.
        
        Args:
            memory_id: Memory ID
            
        Returns:
            True if deleted, False if not found
        """
        if memory_id not in self.memories:
            return False
        
        del self.memories[memory_id]
        self._save_memories()
        return True
    
    def clear(self, category: MemoryCategory | None = None) -> int:
        """Clear memories.
        
        Args:
            category: Clear only this category (None = clear all)
            
        Returns:
            Number of memories cleared
        """
        if category is None:
            count = len(self.memories)
            self.memories.clear()
        else:
            to_delete = [
                mem_id for mem_id, mem in self.memories.items()
                if mem.category == category
            ]
            for mem_id in to_delete:
                del self.memories[mem_id]
            count = len(to_delete)
        
        self._save_memories()
        return count
    
    def get_context_prompt(self, query: str, limit: int = 5) -> str:
        """Generate a context prompt with relevant memories.
        
        Args:
            query: Current task/query
            limit: Maximum memories to include
            
        Returns:
            Formatted context string for system prompt
        """
        memories = self.recall(query, limit)
        
        if not memories:
            return ""
        
        lines = ["Relevant memories from past interactions:"]
        
        for memory in memories:
            category_label = {
                MemoryCategory.PREFERENCE: "Preference",
                MemoryCategory.PROJECT: "Project",
                MemoryCategory.PATTERN: "Pattern",
                MemoryCategory.MISTAKE: "Avoid",
                MemoryCategory.FACT: "Fact",
            }.get(memory.category, "Memory")
            
            lines.append(f"- [{category_label}] {memory.content}")
            
            # Mark as used
            self.use(memory.id)
        
        return "\n".join(lines)
    
    def extract_from_task(
        self,
        task: str,
        result: str,
        success: bool,
    ) -> list[Memory]:
        """Extract memories from a completed task.
        
        Simple heuristic extraction. Could be enhanced with LLM.
        
        Args:
            task: Original task
            result: Task result/output
            success: Whether task succeeded
            
        Returns:
            List of extracted memories
        """
        extracted = []
        
        # Extract project context
        if any(word in task.lower() for word in ["react", "next", "typescript"]):
            extracted.append(self.add(
                category=MemoryCategory.PROJECT,
                content=f"Working with {task.split()[0]} project",
                context=task[:100],
                importance=0.6,
            ))
        
        # Extract preferences from user feedback
        if "prefer" in result.lower() or "like" in result.lower():
            extracted.append(self.add(
                category=MemoryCategory.PREFERENCE,
                content=result[:200],
                context=task[:100],
                importance=0.7,
            ))
        
        # Extract mistakes from failures
        if not success and "error" in result.lower():
            extracted.append(self.add(
                category=MemoryCategory.MISTAKE,
                content=f"Failed: {result[:200]}",
                context=task[:100],
                importance=0.8,
            ))
        
        # Extract patterns from successes
        if success and len(result) > 100:
            extracted.append(self.add(
                category=MemoryCategory.PATTERN,
                content=f"Success: {result[:200]}",
                context=task[:100],
                importance=0.6,
            ))
        
        return extracted
