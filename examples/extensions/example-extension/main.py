"""Example extension demonstrating Anvil's extension system."""


def example_tool(input_text: str) -> str:
    """Example tool that transforms text.
    
    Args:
        input_text: Input text to transform
    
    Returns:
        Transformed text
    """
    return f"[Example Tool] {input_text.upper()}"


def on_task_start(task: str) -> None:
    """Hook called when a task starts.
    
    Args:
        task: Task description
    """
    print(f"[Example Extension] Task started: {task}")


def on_task_complete(task: str, success: bool) -> None:
    """Hook called when a task completes.
    
    Args:
        task: Task description
        success: Whether the task succeeded
    """
    status = "succeeded" if success else "failed"
    print(f"[Example Extension] Task {status}: {task}")
