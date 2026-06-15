"""Specialized micro-agents for the agent swarm."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from agent_swarm.models import AgentConfig, AgentRole as PydanticAgentRole


class AgentRole(str, Enum):
    """Roles that micro-agents can assume."""

    READER = "reader"
    EDITOR = "editor"
    BASH = "bash"
    VERIFIER = "verifier"
    PLANNER = "planner"


@dataclass
class ToolDef:
    """Definition of a tool available to an agent."""

    name: str
    description: str
    parameters: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentMessage:
    """A message in the agent swarm conversation."""

    role: str
    content: str
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


READER_TOOLS = [
    ToolDef(name="read", description="Read file contents at a given path", parameters={"path": {"type": "string"}}),
    ToolDef(name="grep", description="Search file contents for a pattern", parameters={"pattern": {"type": "string"}, "path": {"type": "string"}}),
    ToolDef(name="glob", description="Find files matching a pattern", parameters={"pattern": {"type": "string"}}),
]

EDITOR_TOOLS = [
    ToolDef(name="edit", description="Edit a file by replacing a string", parameters={"file_path": {"type": "string"}, "old_string": {"type": "string"}, "new_string": {"type": "string"}}),
    ToolDef(name="write", description="Write content to a file", parameters={"file_path": {"type": "string"}, "content": {"type": "string"}}),
]

BASH_TOOLS = [
    ToolDef(name="bash", description="Execute a shell command", parameters={"command": {"type": "string"}, "timeout": {"type": "integer"}}),
]

VERIFIER_TOOLS = [
    ToolDef(name="bash", description="Execute shell commands for testing", parameters={"command": {"type": "string"}}),
    ToolDef(name="read", description="Read files to verify changes", parameters={"path": {"type": "string"}}),
    ToolDef(name="grep", description="Search for patterns in files", parameters={"pattern": {"type": "string"}, "path": {"type": "string"}}),
]

PLANNER_TOOLS = [
    ToolDef(name="question", description="Ask the user a clarifying question", parameters={"question": {"type": "string"}}),
    ToolDef(name="glob", description="Find files to understand project structure", parameters={"pattern": {"type": "string"}}),
    ToolDef(name="read", description="Read files for context", parameters={"path": {"type": "string"}}),
]

# System prompts for each agent role
SYSTEM_PROMPTS: dict[str, str] = {
    "reader": (
        "You are a Reader agent. Your job is to explore the codebase, "
        "read files, search for patterns, and gather context. You do NOT "
        "edit files or run commands. When you have enough context, hand off "
        "to the Editor, Bash, or Verifier agent as appropriate.\n\n"
        "Guidelines:\n"
        "- Start by understanding the project structure\n"
        "- Read relevant files thoroughly before handing off\n"
        "- Use grep/glob to find relevant code\n"
        "- Summarize your findings in the handoff context"
    ),
    "editor": (
        "You are an Editor agent. Your job is to write and modify code. "
        "You make precise, targeted edits. After editing, hand off to the "
        "Verifier to check your work.\n\n"
        "Guidelines:\n"
        "- Make minimal, focused changes\n"
        "- Preserve existing code style and conventions\n"
        "- Add comments only when asked\n"
        "- After editing, always hand off to the Verifier"
    ),
    "bash": (
        "You are a Bash agent. Your job is to execute shell commands to "
        "install dependencies, run tests, start servers, and perform "
        "system operations. You do NOT edit files directly.\n\n"
        "Guidelines:\n"
        "- Always use absolute paths\n"
        "- Set reasonable timeouts (60s default)\n"
        "- Handle errors gracefully\n"
        "- Report results clearly for the next agent"
    ),
    "verifier": (
        "You are a Verifier agent. Your job is to validate that changes "
        "work correctly by running tests, checking linting, and verifying "
        "the code does what was intended.\n\n"
        "Guidelines:\n"
        "- Run the project's test suite first\n"
        "- Check for type errors if a typechecker is available\n"
        "- Run linters to catch style issues\n"
        "- If tests fail, hand off to the Editor with specific details\n"
        "- If all checks pass, report success"
    ),
    "planner": (
        "You are a Planner agent. Your job is to break down tasks, define "
        "the approach, and coordinate which agents should handle which steps. "
        "You ask clarifying questions when requirements are ambiguous.\n\n"
        "Guidelines:\n"
        "- Break complex tasks into subtasks\n"
        "- Assign subtasks to the most appropriate agent role\n"
        "- Ask questions when requirements are unclear\n"
        "- Track progress across agent handoffs"
    ),
}


@dataclass
class BaseAgent:
    """Base class for all micro-agents in the swarm.

    Each agent has:
    - A role defining its specialization
    - A set of tools it can use
    - A system prompt for LLM interactions
    - A list of roles it can hand off to
    - A context history of messages

    Attributes:
        role: The agent's specialization role.
        tools: List of tool definitions available to this agent.
        system_prompt: System prompt for LLM interactions.
        can_handoff_to: List of roles this agent can transfer control to.
        _context: Internal message history.
    """

    role: AgentRole
    tools: list[ToolDef]
    system_prompt: str
    can_handoff_to: list[AgentRole]
    _context: list[AgentMessage] = field(default_factory=list, repr=False)

    def add_message(self, message: AgentMessage) -> None:
        """Add a message to the agent's context history.

        Args:
            message: The message to add.
        """
        self._context.append(message)

    def get_context(self) -> list[AgentMessage]:
        """Return a copy of the agent's context history."""
        return list(self._context)

    def clear_context(self) -> None:
        """Clear the agent's context history."""
        self._context.clear()

    def tool_names(self) -> list[str]:
        """Return the names of available tools."""
        return [t.name for t in self.tools]

    def can_handle(self, tool_name: str) -> bool:
        """Check if this agent can use the given tool.

        Args:
            tool_name: Name of the tool to check.

        Returns:
            True if the agent has access to this tool.
        """
        return tool_name in self.tool_names()

    def to_dict(self) -> dict[str, Any]:
        """Serialize the agent to a dictionary."""
        return {
            "role": self.role.value,
            "tools": [t.name for t in self.tools],
            "system_prompt": self.system_prompt,
            "can_handoff_to": [r.value for r in self.can_handoff_to],
            "context": [
                {"role": m.role, "content": m.content, "metadata": m.metadata}
                for m in self._context
            ],
        }

    def get_config(self) -> AgentConfig:
        """Get a Pydantic AgentConfig for this agent."""
        return AgentConfig(
            role=PydanticAgentRole(self.role.value),
            system_prompt=self.system_prompt,
            tools=[],  # Handled by for_role
            can_handoff_to=[PydanticAgentRole(r.value) for r in self.can_handoff_to],
        )

    def execute(self, task: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
        """Execute a task within this agent's specialization.

        This is a local execution method that processes the task based on
        the agent's role and available tools. It does not call an LLM; instead
        it records the execution plan and returns structured output.

        For LLM-based execution, use execute_with_llm() which integrates
        with litellm for actual model calls.

        Args:
            task: The task description to execute.
            context: Optional context from previous agent handoffs.

        Returns:
            Dictionary with execution results including:
            - role: The agent's role
            - task: The task description
            - plan: List of planned tool calls
            - context: Enriched context for handoff
            - status: Execution status
        """
        context = context or {}

        # Determine primary tool based on role
        role_primary_tools: dict[str, str] = {
            "reader": "read",
            "editor": "edit",
            "bash": "bash",
            "verifier": "bash",
            "planner": "question",
        }

        primary_tool = role_primary_tools.get(self.role.value, "read")

        # Build execution plan
        plan = [ToolCall(name=primary_tool, confidence=1.0, args={"task": task})]

        # Add secondary tools based on role
        if self.role == AgentRole.READER:
            plan.append(ToolCall(name="grep", confidence=0.8, args={"pattern": task}))
            plan.append(ToolCall(name="glob", confidence=0.6, args={"pattern": "**/*"}))
        elif self.role == AgentRole.EDITOR:
            plan.append(ToolCall(name="write", confidence=0.7, args={"task": task}))
        elif self.role == AgentRole.VERIFIER:
            plan.append(ToolCall(name="read", confidence=0.8, args={"task": "verify output"}))

        # Record execution in context
        self.add_message(AgentMessage(
            role="assistant",
            content=f"[{self.role.value}] Executing: {task}",
            metadata={"plan": [tc.to_dict() for tc in plan], **context},
        ))

        # Build handoff recommendations
        recommended_handoff = None
        if self.can_handoff_to:
            # Pick the most likely handoff target based on role logic
            handoff_priority: dict[str, list[str]] = {
                "reader": ["editor", "verifier", "bash", "planner"],
                "editor": ["verifier", "reader", "bash", "planner"],
                "bash": ["reader", "editor", "verifier", "planner"],
                "verifier": ["editor", "reader", "bash", "planner"],
                "planner": ["reader", "editor", "bash", "verifier"],
            }
            priority_list = handoff_priority.get(self.role.value, [])
            for target in priority_list:
                target_role = AgentRole(target)
                if target_role in self.can_handoff_to:
                    recommended_handoff = target_role.value
                    break

        return {
            "role": self.role.value,
            "task": task,
            "plan": [tc.to_dict() for tc in plan],
            "context": {
                **context,
                "executed_by": self.role.value,
                "primary_tool": primary_tool,
            },
            "recommended_handoff": recommended_handoff,
            "status": "completed",
        }


@dataclass
class ToolCall:
    """A tool call planned by an agent."""

    name: str
    confidence: float = 1.0
    args: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "confidence": self.confidence,
            "args": self.args,
        }


class ReaderAgent(BaseAgent):
    """Agent specialized in reading and searching code.

    The Reader explores the codebase, reads files, searches for patterns,
    and gathers context. It hands off to Editor (to make changes),
    Verifier (to validate), or Bash (to execute commands).

    Transition data: Read→Edit=0.22, Read→Bash=0.37
    """

    def __init__(self) -> None:
        super().__init__(
            role=AgentRole.READER,
            tools=READER_TOOLS,
            system_prompt=SYSTEM_PROMPTS["reader"],
            can_handoff_to=[AgentRole.EDITOR, AgentRole.BASH, AgentRole.VERIFIER, AgentRole.PLANNER],
        )


class EditorAgent(BaseAgent):
    """Agent specialized in writing and editing code.

    The Editor makes precise, targeted edits based on context from
    other agents. After editing, it typically hands off to the Verifier.

    Transition data: Edit→Bash=0.34, Edit→Read=0.28
    """

    def __init__(self) -> None:
        super().__init__(
            role=AgentRole.EDITOR,
            tools=EDITOR_TOOLS,
            system_prompt=SYSTEM_PROMPTS["editor"],
            can_handoff_to=[AgentRole.READER, AgentRole.BASH, AgentRole.VERIFIER, AgentRole.PLANNER],
        )


class BashAgent(BaseAgent):
    """Agent specialized in running shell commands.

    The Bash agent executes system commands, runs tests, installs
    dependencies, and reports results.

    Transition data: Bash→Bash=0.59, Bash→Edit=0.18
    """

    def __init__(self) -> None:
        super().__init__(
            role=AgentRole.BASH,
            tools=BASH_TOOLS,
            system_prompt=SYSTEM_PROMPTS["bash"],
            can_handoff_to=[AgentRole.READER, AgentRole.EDITOR, AgentRole.VERIFIER, AgentRole.PLANNER],
        )


class VerifierAgent(BaseAgent):
    """Agent specialized in verifying code changes and running tests.

    The Verifier runs tests, linters, and type checkers to validate
    changes made by the Editor.
    """

    def __init__(self) -> None:
        super().__init__(
            role=AgentRole.VERIFIER,
            tools=VERIFIER_TOOLS,
            system_prompt=SYSTEM_PROMPTS["verifier"],
            can_handoff_to=[AgentRole.READER, AgentRole.EDITOR, AgentRole.BASH, AgentRole.PLANNER],
        )


class PlannerAgent(BaseAgent):
    """Agent specialized in planning and coordinating work.

    The Planner breaks down tasks, defines approaches, and coordinates
    which agents should handle which steps.
    """

    def __init__(self) -> None:
        super().__init__(
            role=AgentRole.PLANNER,
            tools=PLANNER_TOOLS,
            system_prompt=SYSTEM_PROMPTS["planner"],
            can_handoff_to=[AgentRole.READER, AgentRole.EDITOR, AgentRole.BASH, AgentRole.VERIFIER],
        )


AGENT_CLASSES: dict[AgentRole, type[BaseAgent]] = {
    AgentRole.READER: ReaderAgent,
    AgentRole.EDITOR: EditorAgent,
    AgentRole.BASH: BashAgent,
    AgentRole.VERIFIER: VerifierAgent,
    AgentRole.PLANNER: PlannerAgent,
}


def create_agent(role: AgentRole | str) -> BaseAgent:
    """Factory function to create an agent by role.

    Args:
        role: The agent role to create, either as an AgentRole enum or string.

    Returns:
        A new agent instance of the specified role.

    Raises:
        ValueError: If the role is not recognized.
    """
    if isinstance(role, str):
        role = AgentRole(role)
    agent_class = AGENT_CLASSES.get(role)
    if agent_class is None:
        raise ValueError(f"Unknown agent role: {role}. Available: {list(AGENT_CLASSES.keys())}")
    return agent_class()
