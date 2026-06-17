"""Event system for SDK."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable, Optional


@dataclass
class Event:
    """An event emitted by the Anvil server."""

    type: str
    data: dict[str, Any]
    timestamp: str


class EventManager:
    """Manage events from the Anvil server.

    Supports registering handlers for specific event types and
    listening for events via a persistent WebSocket connection.

    Example::

        client.events.on("task.completed", lambda e: print(e.data))
        client.events.listen()
    """

    def __init__(self, client: Any) -> None:
        self.client = client
        self.handlers: dict[str, list[Callable[[Event], None]]] = {}

    def on(self, event_type: str, handler: Callable[[Event], None]) -> None:
        """Register a handler for an event type.

        Args:
            event_type: Event type string to listen for.
            handler: Callback invoked with the Event when it arrives.
        """
        self.handlers.setdefault(event_type, []).append(handler)

    def off(self, event_type: str, handler: Callable[[Event], None]) -> None:
        """Remove a previously registered handler.

        Args:
            event_type: Event type the handler was registered for.
            handler: The handler callback to remove.
        """
        if event_type in self.handlers:
            self.handlers[event_type] = [
                h for h in self.handlers[event_type] if h is not handler
            ]

    def emit(self, event: Event) -> None:
        """Dispatch an event to all registered handlers.

        Handlers registered for ``"*"`` receive all events.

        Args:
            event: The event to dispatch.
        """
        for handler in self.handlers.get(event.type, []):
            handler(event)
        for handler in self.handlers.get("*", []):
            handler(event)

    def listen(self) -> None:
        """Start listening for events via WebSocket.

        Blocks the current thread, dispatching incoming events to
        registered handlers. Reconnects automatically on disconnect.
        """
        import websockets

        ws_url = self.client.api_url.replace("http", "ws") + "/ws/events"

        with websockets.connect(ws_url) as ws:
            for message in ws:
                data = json.loads(message)
                event = Event(
                    type=data["type"],
                    data=data.get("data", {}),
                    timestamp=data.get("timestamp", ""),
                )
                self.emit(event)
