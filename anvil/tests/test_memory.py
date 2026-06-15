"""Tests for agent memory system."""

import pytest
from pathlib import Path
from anvil.memory.manager import MemoryManager, Memory, MemoryCategory


@pytest.fixture
def memory_manager(tmp_path):
    """Create a memory manager with a temporary directory."""
    return MemoryManager(memory_dir=tmp_path / "memory")


class TestMemoryManager:
    """Test MemoryManager functionality."""
    
    def test_create_manager(self, memory_manager):
        """Test creating a memory manager."""
        assert memory_manager is not None
        assert memory_manager.memory_dir.exists()
    
    def test_add_memory(self, memory_manager):
        """Test adding a memory."""
        mem = memory_manager.add(
            category=MemoryCategory.PREFERENCE,
            content="User prefers TypeScript",
            context="React project setup",
            importance=0.8,
        )
        assert mem is not None
        assert mem.category == MemoryCategory.PREFERENCE
        assert mem.content == "User prefers TypeScript"
        assert mem.importance == 0.8
    
    def test_get_memory(self, memory_manager):
        """Test getting a memory by ID."""
        mem = memory_manager.add(
            category=MemoryCategory.FACT,
            content="Python 3.11 is installed",
        )
        retrieved = memory_manager.get(mem.id)
        assert retrieved is not None
        assert retrieved.id == mem.id
        assert retrieved.content == mem.content
    
    def test_list_memories(self, memory_manager):
        """Test listing memories."""
        memory_manager.add(MemoryCategory.PREFERENCE, "Pref 1")
        memory_manager.add(MemoryCategory.FACT, "Fact 1")
        memory_manager.add(MemoryCategory.PREFERENCE, "Pref 2")
        
        all_memories = memory_manager.list()
        assert len(all_memories) == 3
        
        prefs = memory_manager.list(category=MemoryCategory.PREFERENCE)
        assert len(prefs) == 2
    
    def test_list_memories_limit(self, memory_manager):
        """Test listing memories with limit."""
        for i in range(10):
            memory_manager.add(MemoryCategory.FACT, f"Fact {i}")
        
        limited = memory_manager.list(limit=5)
        assert len(limited) == 5
    
    def test_recall_memories(self, memory_manager):
        """Test recalling memories by query."""
        memory_manager.add(
            MemoryCategory.PROJECT,
            "React project with TypeScript",
            importance=0.9,
        )
        memory_manager.add(
            MemoryCategory.PROJECT,
            "Python FastAPI backend",
            importance=0.7,
        )
        memory_manager.add(
            MemoryCategory.PREFERENCE,
            "User prefers dark mode",
            importance=0.6,
        )
        
        # Recall React-related memories
        results = memory_manager.recall("React TypeScript", limit=2)
        assert len(results) > 0
        assert "React" in results[0].content or "TypeScript" in results[0].content
    
    def test_recall_empty_query(self, memory_manager):
        """Test recalling with empty query."""
        memory_manager.add(MemoryCategory.FACT, "Some fact")
        results = memory_manager.recall("", limit=5)
        # Should return empty or all memories
        assert isinstance(results, list)
    
    def test_use_memory(self, memory_manager):
        """Test marking a memory as used."""
        mem = memory_manager.add(MemoryCategory.FACT, "Test fact")
        assert mem.use_count == 0
        
        memory_manager.use(mem.id)
        updated = memory_manager.get(mem.id)
        assert updated is not None
        assert updated.use_count == 1
    
    def test_update_memory(self, memory_manager):
        """Test updating a memory."""
        mem = memory_manager.add(
            MemoryCategory.PREFERENCE,
            "Original content",
            importance=0.5,
        )
        
        updated = memory_manager.update(
            mem.id,
            content="Updated content",
            importance=0.9,
        )
        
        assert updated is not None
        assert updated.content == "Updated content"
        assert updated.importance == 0.9
    
    def test_update_nonexistent(self, memory_manager):
        """Test updating a non-existent memory."""
        result = memory_manager.update("nonexistent", content="test")
        assert result is None
    
    def test_delete_memory(self, memory_manager):
        """Test deleting a memory."""
        mem = memory_manager.add(MemoryCategory.FACT, "To delete")
        assert memory_manager.delete(mem.id) is True
        assert memory_manager.get(mem.id) is None
    
    def test_delete_nonexistent(self, memory_manager):
        """Test deleting a non-existent memory."""
        assert memory_manager.delete("nonexistent") is False
    
    def test_clear_all_memories(self, memory_manager):
        """Test clearing all memories."""
        memory_manager.add(MemoryCategory.FACT, "Fact 1")
        memory_manager.add(MemoryCategory.FACT, "Fact 2")
        memory_manager.add(MemoryCategory.PREFERENCE, "Pref 1")
        
        count = memory_manager.clear()
        assert count == 3
        assert len(memory_manager.list()) == 0
    
    def test_clear_by_category(self, memory_manager):
        """Test clearing memories by category."""
        memory_manager.add(MemoryCategory.FACT, "Fact 1")
        memory_manager.add(MemoryCategory.FACT, "Fact 2")
        memory_manager.add(MemoryCategory.PREFERENCE, "Pref 1")
        
        count = memory_manager.clear(category=MemoryCategory.FACT)
        assert count == 2
        assert len(memory_manager.list()) == 1
        assert memory_manager.list()[0].category == MemoryCategory.PREFERENCE
    
    def test_get_context_prompt(self, memory_manager):
        """Test generating context prompt."""
        memory_manager.add(
            MemoryCategory.PROJECT,
            "React project with TypeScript",
            importance=0.9,
        )
        memory_manager.add(
            MemoryCategory.PREFERENCE,
            "User prefers functional components",
            importance=0.8,
        )
        
        prompt = memory_manager.get_context_prompt("React TypeScript", limit=5)
        assert "React" in prompt or "TypeScript" in prompt
        assert "Relevant memories" in prompt
    
    def test_get_context_prompt_empty(self, memory_manager):
        """Test generating context prompt with no memories."""
        prompt = memory_manager.get_context_prompt("test query")
        assert prompt == ""
    
    def test_extract_from_task_success(self, memory_manager):
        """Test extracting memories from a successful task."""
        memories = memory_manager.extract_from_task(
            task="Build a React app with TypeScript",
            result="Successfully created React TypeScript project",
            success=True,
        )
        # Should extract at least a pattern memory
        assert len(memories) > 0
    
    def test_extract_from_task_failure(self, memory_manager):
        """Test extracting memories from a failed task."""
        memories = memory_manager.extract_from_task(
            task="Deploy to production",
            result="Error: deployment failed, connection timeout",
            success=False,
        )
        # Should extract a mistake memory
        assert len(memories) > 0
        assert any(m.category == MemoryCategory.MISTAKE for m in memories)
    
    def test_persistence(self, tmp_path):
        """Test that memories persist across manager instances."""
        memory_dir = tmp_path / "memory"
        
        # Create manager and add memory
        mgr1 = MemoryManager(memory_dir=memory_dir)
        mem = mgr1.add(MemoryCategory.FACT, "Persistent fact")
        
        # Create new manager instance
        mgr2 = MemoryManager(memory_dir=memory_dir)
        retrieved = mgr2.get(mem.id)
        
        assert retrieved is not None
        assert retrieved.content == "Persistent fact"


class TestMemory:
    """Test Memory dataclass."""
    
    def test_create_memory(self):
        """Test creating a memory."""
        mem = Memory(
            id="test_id",
            category=MemoryCategory.FACT,
            content="Test content",
            context="Test context",
            importance=0.7,
        )
        assert mem.id == "test_id"
        assert mem.category == MemoryCategory.FACT
        assert mem.content == "Test content"
        assert mem.importance == 0.7
    
    def test_memory_defaults(self):
        """Test memory default values."""
        mem = Memory(
            id="test_id",
            category=MemoryCategory.FACT,
            content="Test",
        )
        assert mem.context == ""
        assert mem.use_count == 0
        assert mem.importance == 0.5
    
    def test_memory_to_dict(self):
        """Test converting memory to dict."""
        mem = Memory(
            id="test_id",
            category=MemoryCategory.FACT,
            content="Test content",
            importance=0.8,
        )
        data = mem.to_dict()
        assert data["id"] == "test_id"
        assert data["category"] == "fact"
        assert data["content"] == "Test content"
        assert data["importance"] == 0.8
    
    def test_memory_from_dict(self):
        """Test creating memory from dict."""
        data = {
            "id": "test_id",
            "category": "preference",
            "content": "Test content",
            "context": "Test context",
            "importance": 0.9,
            "use_count": 5,
        }
        mem = Memory.from_dict(data)
        assert mem.id == "test_id"
        assert mem.category == MemoryCategory.PREFERENCE
        assert mem.content == "Test content"
        assert mem.use_count == 5


class TestMemoryCategory:
    """Test MemoryCategory enum."""
    
    def test_category_values(self):
        """Test category enum values."""
        assert MemoryCategory.PREFERENCE.value == "preference"
        assert MemoryCategory.PROJECT.value == "project"
        assert MemoryCategory.PATTERN.value == "pattern"
        assert MemoryCategory.MISTAKE.value == "mistake"
        assert MemoryCategory.FACT.value == "fact"
    
    def test_category_from_string(self):
        """Test creating category from string."""
        cat = MemoryCategory("preference")
        assert cat == MemoryCategory.PREFERENCE
