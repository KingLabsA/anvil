"""Database layer for Anvil - PostgreSQL/SQLite support."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel


# ============================================================================
# Database Configuration
# ============================================================================

DATABASE_URL = "sqlite:///./anvil.db"  # TODO: Use environment variable
DB_PATH = Path("./anvil.db")


# ============================================================================
# Database Models
# ============================================================================

class DBUser(BaseModel):
    """Database user model."""
    id: str
    email: str
    username: str
    hashed_password: str
    is_active: bool = True
    is_admin: bool = False
    created_at: str
    last_login: Optional[str] = None


class DBSession(BaseModel):
    """Database session model."""
    id: str
    user_id: str
    task: str
    success: bool
    created_at: str
    duration_ms: float
    output: Optional[str] = None
    error: Optional[str] = None


class DBAPIKey(BaseModel):
    """Database API key model."""
    id: str
    user_id: str
    key: str
    name: str
    created_at: str
    last_used: Optional[str] = None
    is_active: bool = True


class DBMemory(BaseModel):
    """Database memory model."""
    id: str
    user_id: str
    category: str
    content: str
    context: str = ""
    importance: float = 0.5
    created_at: str
    last_used: str
    use_count: int = 0


# ============================================================================
# Database Manager
# ============================================================================

class DatabaseManager:
    """Database manager for SQLite/PostgreSQL."""
    
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self._init_database()
    
    def _init_database(self):
        """Initialize database tables."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Users table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    email TEXT UNIQUE NOT NULL,
                    username TEXT UNIQUE NOT NULL,
                    hashed_password TEXT NOT NULL,
                    is_active BOOLEAN DEFAULT 1,
                    is_admin BOOLEAN DEFAULT 0,
                    created_at TEXT NOT NULL,
                    last_login TEXT
                )
            """)
            
            # Sessions table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    task TEXT NOT NULL,
                    success BOOLEAN NOT NULL,
                    created_at TEXT NOT NULL,
                    duration_ms REAL NOT NULL,
                    output TEXT,
                    error TEXT,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
            """)
            
            # API keys table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS api_keys (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    key TEXT UNIQUE NOT NULL,
                    name TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    last_used TEXT,
                    is_active BOOLEAN DEFAULT 1,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
            """)
            
            # Memories table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS memories (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    category TEXT NOT NULL,
                    content TEXT NOT NULL,
                    context TEXT DEFAULT '',
                    importance REAL DEFAULT 0.5,
                    created_at TEXT NOT NULL,
                    last_used TEXT NOT NULL,
                    use_count INTEGER DEFAULT 0,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
            """)
            
            # Create indexes
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_created ON sessions(created_at)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_api_keys_user ON api_keys(user_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_api_keys_key ON api_keys(key)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_memories_user ON memories(user_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_memories_category ON memories(category)")
            
            conn.commit()
    
    @contextmanager
    def get_connection(self):
        """Get database connection."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    
    # ========================================================================
    # User Operations
    # ========================================================================
    
    def create_user(self, user: DBUser) -> bool:
        """Create a new user."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO users (id, email, username, hashed_password, is_active, is_admin, created_at, last_login)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    user.id, user.email, user.username, user.hashed_password,
                    user.is_active, user.is_admin, user.created_at, user.last_login
                ))
                conn.commit()
                return True
        except sqlite3.IntegrityError:
            return False
    
    def get_user_by_email(self, email: str) -> Optional[DBUser]:
        """Get user by email."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
            row = cursor.fetchone()
            if row:
                return DBUser(**dict(row))
            return None
    
    def get_user_by_id(self, user_id: str) -> Optional[DBUser]:
        """Get user by ID."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
            row = cursor.fetchone()
            if row:
                return DBUser(**dict(row))
            return None
    
    def update_user_last_login(self, user_id: str) -> bool:
        """Update user's last login time."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE users SET last_login = ? WHERE id = ?
                """, (datetime.now().isoformat(), user_id))
                conn.commit()
                return True
        except Exception:
            return False
    
    # ========================================================================
    # Session Operations
    # ========================================================================
    
    def create_session(self, session: DBSession) -> bool:
        """Create a new session."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO sessions (id, user_id, task, success, created_at, duration_ms, output, error)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    session.id, session.user_id, session.task, session.success,
                    session.created_at, session.duration_ms, session.output, session.error
                ))
                conn.commit()
                return True
        except Exception:
            return False
    
    def get_user_sessions(self, user_id: str, limit: int = 100) -> list[DBSession]:
        """Get user's sessions."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM sessions WHERE user_id = ?
                ORDER BY created_at DESC LIMIT ?
            """, (user_id, limit))
            return [DBSession(**dict(row)) for row in cursor.fetchall()]
    
    def get_session(self, session_id: str) -> Optional[DBSession]:
        """Get session by ID."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM sessions WHERE id = ?", (session_id,))
            row = cursor.fetchone()
            if row:
                return DBSession(**dict(row))
            return None
    
    def delete_session(self, session_id: str, user_id: str) -> bool:
        """Delete a session."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    DELETE FROM sessions WHERE id = ? AND user_id = ?
                """, (session_id, user_id))
                conn.commit()
                return cursor.rowcount > 0
        except Exception:
            return False
    
    # ========================================================================
    # API Key Operations
    # ========================================================================
    
    def create_api_key(self, api_key: DBAPIKey) -> bool:
        """Create a new API key."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO api_keys (id, user_id, key, name, created_at, last_used, is_active)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    api_key.id, api_key.user_id, api_key.key, api_key.name,
                    api_key.created_at, api_key.last_used, api_key.is_active
                ))
                conn.commit()
                return True
        except sqlite3.IntegrityError:
            return False
    
    def get_api_key(self, key: str) -> Optional[DBAPIKey]:
        """Get API key by key value."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM api_keys WHERE key = ? AND is_active = 1", (key,))
            row = cursor.fetchone()
            if row:
                return DBAPIKey(**dict(row))
            return None
    
    def get_user_api_keys(self, user_id: str) -> list[DBAPIKey]:
        """Get user's API keys."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM api_keys WHERE user_id = ? AND is_active = 1
                ORDER BY created_at DESC
            """, (user_id,))
            return [DBAPIKey(**dict(row)) for row in cursor.fetchall()]
    
    def update_api_key_last_used(self, key: str) -> bool:
        """Update API key's last used time."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE api_keys SET last_used = ? WHERE key = ?
                """, (datetime.now().isoformat(), key))
                conn.commit()
                return True
        except Exception:
            return False
    
    def revoke_api_key(self, key_id: str, user_id: str) -> bool:
        """Revoke an API key."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE api_keys SET is_active = 0 WHERE id = ? AND user_id = ?
                """, (key_id, user_id))
                conn.commit()
                return cursor.rowcount > 0
        except Exception:
            return False
    
    # ========================================================================
    # Memory Operations
    # ========================================================================
    
    def create_memory(self, memory: DBMemory) -> bool:
        """Create a new memory."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO memories (id, user_id, category, content, context, importance, created_at, last_used, use_count)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    memory.id, memory.user_id, memory.category, memory.content,
                    memory.context, memory.importance, memory.created_at,
                    memory.last_used, memory.use_count
                ))
                conn.commit()
                return True
        except Exception:
            return False
    
    def get_user_memories(self, user_id: str, category: Optional[str] = None, limit: int = 100) -> list[DBMemory]:
        """Get user's memories."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if category:
                cursor.execute("""
                    SELECT * FROM memories WHERE user_id = ? AND category = ?
                    ORDER BY importance DESC, use_count DESC LIMIT ?
                """, (user_id, category, limit))
            else:
                cursor.execute("""
                    SELECT * FROM memories WHERE user_id = ?
                    ORDER BY importance DESC, use_count DESC LIMIT ?
                """, (user_id, limit))
            return [DBMemory(**dict(row)) for row in cursor.fetchall()]
    
    def update_memory_usage(self, memory_id: str) -> bool:
        """Update memory usage statistics."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE memories 
                    SET use_count = use_count + 1, last_used = ?
                    WHERE id = ?
                """, (datetime.now().isoformat(), memory_id))
                conn.commit()
                return True
        except Exception:
            return False
    
    def delete_memory(self, memory_id: str, user_id: str) -> bool:
        """Delete a memory."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    DELETE FROM memories WHERE id = ? AND user_id = ?
                """, (memory_id, user_id))
                conn.commit()
                return cursor.rowcount > 0
        except Exception:
            return False


# ============================================================================
# Global Database Instance
# ============================================================================

db = DatabaseManager()
