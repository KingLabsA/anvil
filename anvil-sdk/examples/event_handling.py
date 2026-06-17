"""Event handling example."""

from anvil_sdk import AnvilClient, Event


def on_task_completed(event: Event) -> None:
    print(f"Task completed: {event.data.get('task_id')}")


def on_error(event: Event) -> None:
    print(f"Error: {event.data.get('message')}")


def on_any_event(event: Event) -> None:
    print(f"[{event.type}] {event.timestamp}")


with AnvilClient(api_url="http://localhost:8000") as client:
    client.events.on("task.completed", on_task_completed)
    client.events.on("error", on_error)
    client.events.on("*", on_any_event)

    print("Listening for events... (Ctrl+C to stop)")
    client.events.listen()
