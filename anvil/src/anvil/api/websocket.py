"""WebSocket server for real-time collaboration."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Optional

from fastapi import WebSocket, WebSocketDisconnect
from pydantic import BaseModel


# ============================================================================
# WebSocket Models
# ============================================================================

class WSMessage(BaseModel):
    """WebSocket message model."""
    type: str
    payload: dict[str, Any]
    timestamp: str = ""
    sender_id: str = ""
    
    def __init__(self, **data):
        super().__init__(**data)
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()


class WSCursorUpdate(BaseModel):
    """Cursor position update."""
    user_id: str
    file_path: str
    line: int
    column: int
    selection_start: Optional[int] = None
    selection_end: Optional[int] = None


class WSFileChange(BaseModel):
    """File change notification."""
    user_id: str
    file_path: str
    change_type: str  # "create", "modify", "delete"
    content: Optional[str] = None
    timestamp: str = ""


class WSPresenceUpdate(BaseModel):
    """User presence update."""
    user_id: str
    username: str
    status: str  # "online", "away", "offline"
    current_file: Optional[str] = None
    last_active: str = ""


# ============================================================================
# Connection Manager
# ============================================================================

class ConnectionManager:
    """Manages WebSocket connections for real-time collaboration."""
    
    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}
        self.user_sessions: dict[str, dict[str, Any]] = {}
        self.file_locks: dict[str, str] = {}  # file_path -> user_id
    
    async def connect(self, websocket: WebSocket, user_id: str, username: str):
        """Accept and register a new WebSocket connection."""
        await websocket.accept()
        self.active_connections[user_id] = websocket
        self.user_sessions[user_id] = {
            "username": username,
            "status": "online",
            "current_file": None,
            "last_active": datetime.now().isoformat(),
        }
        
        # Broadcast presence update
        await self.broadcast_presence(user_id, username, "online")
    
    def disconnect(self, user_id: str):
        """Remove a WebSocket connection."""
        if user_id in self.active_connections:
            del self.active_connections[user_id]
        
        if user_id in self.user_sessions:
            username = self.user_sessions[user_id]["username"]
            del self.user_sessions[user_id]
            
            # Release any file locks
            files_to_release = [f for f, u in self.file_locks.items() if u == user_id]
            for file_path in files_to_release:
                del self.file_locks[file_path]
    
    async def send_personal_message(self, message: WSMessage, user_id: str):
        """Send a message to a specific user."""
        if user_id in self.active_connections:
            websocket = self.active_connections[user_id]
            await websocket.send_json(message.dict())
    
    async def broadcast_message(self, message: WSMessage, exclude_user: Optional[str] = None):
        """Broadcast a message to all connected users."""
        for user_id, websocket in self.active_connections.items():
            if user_id != exclude_user:
                try:
                    await websocket.send_json(message.dict())
                except Exception:
                    pass
    
    async def broadcast_presence(self, user_id: str, username: str, status: str):
        """Broadcast user presence update."""
        message = WSMessage(
            type="presence",
            payload={
                "user_id": user_id,
                "username": username,
                "status": status,
                "current_file": self.user_sessions.get(user_id, {}).get("current_file"),
                "last_active": datetime.now().isoformat(),
            }
        )
        await self.broadcast_message(message, exclude_user=user_id)
    
    async def broadcast_cursor_update(self, cursor: WSCursorUpdate):
        """Broadcast cursor position update."""
        message = WSMessage(
            type="cursor",
            payload=cursor.dict()
        )
        await self.broadcast_message(message, exclude_user=cursor.user_id)
    
    async def broadcast_file_change(self, change: WSFileChange):
        """Broadcast file change notification."""
        message = WSMessage(
            type="file_change",
            payload=change.dict()
        )
        await self.broadcast_message(message, exclude_user=change.user_id)
    
    def acquire_file_lock(self, file_path: str, user_id: str) -> bool:
        """Acquire a lock on a file for editing."""
        if file_path in self.file_locks and self.file_locks[file_path] != user_id:
            return False
        self.file_locks[file_path] = user_id
        return True
    
    def release_file_lock(self, file_path: str, user_id: str) -> bool:
        """Release a file lock."""
        if file_path in self.file_locks and self.file_locks[file_path] == user_id:
            del self.file_locks[file_path]
            return True
        return False
    
    def get_file_lock_owner(self, file_path: str) -> Optional[str]:
        """Get the user ID of the file lock owner."""
        return self.file_locks.get(file_path)
    
    def get_online_users(self) -> list[dict[str, Any]]:
        """Get list of online users."""
        return [
            {
                "user_id": user_id,
                "username": session["username"],
                "status": session["status"],
                "current_file": session.get("current_file"),
                "last_active": session.get("last_active"),
            }
            for user_id, session in self.user_sessions.items()
        ]
    
    def update_user_activity(self, user_id: str, current_file: Optional[str] = None):
        """Update user's last active timestamp and current file."""
        if user_id in self.user_sessions:
            self.user_sessions[user_id]["last_active"] = datetime.now().isoformat()
            if current_file is not None:
                self.user_sessions[user_id]["current_file"] = current_file


# ============================================================================
# WebSocket Handler
# ============================================================================

class WebSocketHandler:
    """Handles WebSocket connections and messages."""
    
    def __init__(self, manager: ConnectionManager):
        self.manager = manager
    
    async def handle_connection(self, websocket: WebSocket, user_id: str, username: str):
        """Handle a WebSocket connection."""
        await self.manager.connect(websocket, user_id, username)
        
        try:
            # Send initial state
            await self.send_initial_state(websocket, user_id)
            
            # Message loop
            while True:
                data = await websocket.receive_json()
                message = WSMessage(**data)
                await self.handle_message(websocket, user_id, message)
        
        except WebSocketDisconnect:
            self.manager.disconnect(user_id)
            await self.manager.broadcast_presence(user_id, username, "offline")
        except Exception as e:
            print(f"WebSocket error: {e}")
            self.manager.disconnect(user_id)
    
    async def send_initial_state(self, websocket: WebSocket, user_id: str):
        """Send initial state to newly connected user."""
        # Send list of online users
        online_users = self.manager.get_online_users()
        message = WSMessage(
            type="initial_state",
            payload={
                "online_users": online_users,
                "file_locks": self.manager.file_locks,
            }
        )
        await websocket.send_json(message.dict())
    
    async def handle_message(self, websocket: WebSocket, user_id: str, message: WSMessage):
        """Handle an incoming WebSocket message."""
        self.manager.update_user_activity(user_id)
        
        if message.type == "cursor":
            cursor = WSCursorUpdate(**message.payload)
            cursor.user_id = user_id
            await self.manager.broadcast_cursor_update(cursor)
        
        elif message.type == "file_change":
            change = WSFileChange(**message.payload)
            change.user_id = user_id
            change.timestamp = datetime.now().isoformat()
            await self.manager.broadcast_file_change(change)
        
        elif message.type == "file_lock_acquire":
            file_path = message.payload.get("file_path")
            if file_path:
                success = self.manager.acquire_file_lock(file_path, user_id)
                response = WSMessage(
                    type="file_lock_response",
                    payload={
                        "file_path": file_path,
                        "success": success,
                        "owner": self.manager.get_file_lock_owner(file_path),
                    }
                )
                await websocket.send_json(response.dict())
                
                if success:
                    await self.manager.broadcast_message(
                        WSMessage(
                            type="file_lock_update",
                            payload={
                                "file_path": file_path,
                                "owner": user_id,
                                "action": "acquired",
                            }
                        )
                    )
        
        elif message.type == "file_lock_release":
            file_path = message.payload.get("file_path")
            if file_path:
                success = self.manager.release_file_lock(file_path, user_id)
                if success:
                    await self.manager.broadcast_message(
                        WSMessage(
                            type="file_lock_update",
                            payload={
                                "file_path": file_path,
                                "owner": None,
                                "action": "released",
                            }
                        )
                    )
        
        elif message.type == "presence":
            status = message.payload.get("status", "online")
            username = self.manager.user_sessions.get(user_id, {}).get("username", "Unknown")
            await self.manager.broadcast_presence(user_id, username, status)
        
        elif message.type == "chat":
            # Broadcast chat message to all users
            chat_message = WSMessage(
                type="chat",
                payload={
                    "user_id": user_id,
                    "username": self.manager.user_sessions.get(user_id, {}).get("username", "Unknown"),
                    "message": message.payload.get("message", ""),
                    "timestamp": datetime.now().isoformat(),
                }
            )
            await self.manager.broadcast_message(chat_message)
        
        elif message.type == "ping":
            # Respond with pong
            pong = WSMessage(type="pong", payload={})
            await websocket.send_json(pong.dict())


# ============================================================================
# Global Instances
# ============================================================================

connection_manager = ConnectionManager()
websocket_handler = WebSocketHandler(connection_manager)
