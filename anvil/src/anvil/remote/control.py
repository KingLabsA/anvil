"""Remote control for continuing sessions from any device."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Optional


@dataclass
class RemoteSession:
    """A remote session that can be accessed from multiple devices."""

    session_id: str
    share_token: str
    created_at: datetime
    expires_at: datetime
    active: bool = True
    devices: list[str] = field(default_factory=list)

    def is_expired(self) -> bool:
        return datetime.now() > self.expires_at

    def add_device(self, device_id: str) -> None:
        if device_id not in self.devices:
            self.devices.append(device_id)

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "share_token": self.share_token,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "devices": list(self.devices),
            "active": self.active and not self.is_expired(),
        }


class RemoteControl:
    """Enable remote control of Anvil sessions."""

    def __init__(self, anvil_engine: Any) -> None:
        self.anvil = anvil_engine
        self.sessions: dict[str, RemoteSession] = {}
        self.share_links: dict[str, str] = {}

    def create_share_link(self, session_id: str, expires_hours: int = 24) -> str:
        """Create a shareable link for a session."""
        share_token = str(uuid.uuid4())

        remote_session = RemoteSession(
            session_id=session_id,
            share_token=share_token,
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(hours=expires_hours),
        )

        self.sessions[session_id] = remote_session
        self.share_links[share_token] = session_id

        share_url = f"https://anvil.fableforge.ai/share/{share_token}"
        return share_url

    def access_shared_session(self, share_token: str, device_id: str) -> Optional[str]:
        """Access a shared session from a new device."""
        if share_token not in self.share_links:
            return None

        session_id = self.share_links[share_token]
        remote_session = self.sessions.get(session_id)

        if not remote_session or remote_session.is_expired():
            return None

        remote_session.add_device(device_id)
        return session_id

    def revoke_share_link(self, share_token: str) -> None:
        """Revoke a share link."""
        if share_token in self.share_links:
            session_id = self.share_links[share_token]
            del self.share_links[share_token]
            if session_id in self.sessions:
                del self.sessions[session_id]

    def get_active_sessions(self) -> list[dict[str, Any]]:
        """Get all active remote sessions."""
        return [s.to_dict() for s in self.sessions.values()]

    def cleanup_expired(self) -> int:
        """Remove expired sessions. Returns count of removed sessions."""
        expired_tokens = [
            token for token, sid in self.share_links.items()
            if sid in self.sessions and self.sessions[sid].is_expired()
        ]
        for token in expired_tokens:
            session_id = self.share_links.pop(token)
            self.sessions.pop(session_id, None)
        return len(expired_tokens)


class TeleportManager:
    """Teleport sessions between devices."""

    def __init__(self, remote_control: RemoteControl) -> None:
        self.remote_control = remote_control

    def teleport_to_web(self, session_id: str) -> str:
        """Teleport a terminal session to web."""
        return self.remote_control.create_share_link(session_id)

    def teleport_to_mobile(self, session_id: str) -> str:
        """Teleport a session to mobile app."""
        share_url = self.remote_control.create_share_link(session_id)
        mobile_url = f"anvil://session/{share_url}"
        return mobile_url

    def pull_from_web(self, share_token: str, device_id: str) -> Optional[str]:
        """Pull a web session to local terminal."""
        return self.remote_control.access_shared_session(share_token, device_id)
