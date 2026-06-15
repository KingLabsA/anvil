"""Permission system for Anvil agents.

Controls what tools each agent can use and whether each invocation
requires user confirmation, is silently allowed, or is outright denied.

Resolution order (most specific wins, last match takes precedence):
    1. Per-agent rules override global rules
    2. More-specific glob patterns override less-specific ones
    3. Within the same specificity, later entries override earlier ones
"""

from __future__ import annotations

import fnmatch
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Union


class PermissionAction(str, Enum):
    """What to do when a tool is invoked."""
    ALLOW = "allow"
    ASK = "ask"
    DENY = "deny"


# Type alias — a single rule can map a glob pattern to an action.
PermissionRule = dict[str, Union[str, "PermissionAction"]]


def _parse_action(value: Any) -> PermissionAction:
    """Normalise strings or PermissionAction values into PermissionAction."""
    if isinstance(value, PermissionAction):
        return value
    if isinstance(value, str):
        return PermissionAction(value.lower().strip())
    raise ValueError(f"Cannot parse permission action from {value!r}")


def _action_priority(action: PermissionAction) -> int:
    """More restrictive = higher priority when specificity ties."""
    return {"allow": 0, "ask": 1, "deny": 2}[action.value]


def _pattern_specificity(pattern: str) -> int:
    """Estimate how specific a glob pattern is.

    Rules of thumb:
      - Exact tool name (no wildcards) → highest specificity
      - Prefix wildcard like ``bash_*`` → medium
      - Bare ``*`` → lowest
    """
    if pattern == "*":
        return 0
    if "*" not in pattern and "?" not in pattern:
        return 100
    prefix, _, _ = pattern.partition("*")
    return max(1, len(prefix))


@dataclass
class PermissionConfig:
    """Per-scope permission rules.

    Attributes:
        rules: Mapping from tool-name glob pattern to action.
               e.g. ``{"read": "allow", "bash git push *": "ask", "bash *": "allow", "*": "deny"}``
               For the ``bash`` tool, keys can include the command prefix
               separated by a space: ``"bash rm *": "deny"``.
    """

    rules: dict[str, str | PermissionAction] = field(default_factory=dict)

    # ── convenience constructors ──────────────────────────────────────

    @classmethod
    def permissive(cls) -> PermissionConfig:
        """Allow everything."""
        return cls(rules={"*": PermissionAction.ALLOW})

    @classmethod
    def readonly(cls) -> PermissionConfig:
        """Read-only: allow read/grep/glob/ls, deny write/edit/bash."""
        return cls(rules={
            "read": PermissionAction.ALLOW,
            "grep": PermissionAction.ALLOW,
            "glob": PermissionAction.ALLOW,
            "ls": PermissionAction.ALLOW,
            "bash git status *": PermissionAction.ALLOW,
            "bash git log *": PermissionAction.ALLOW,
            "bash git diff *": PermissionAction.ALLOW,
            "bash": PermissionAction.DENY,
            "write": PermissionAction.DENY,
            "edit": PermissionAction.DENY,
        })

    @classmethod
    def strict(cls) -> PermissionConfig:
        """Ask before anything destructive, allow reads."""
        return cls(rules={
            "read": PermissionAction.ALLOW,
            "grep": PermissionAction.ALLOW,
            "glob": PermissionAction.ALLOW,
            "ls": PermissionAction.ALLOW,
            "bash git status *": PermissionAction.ALLOW,
            "bash git log *": PermissionAction.ALLOW,
            "bash git diff *": PermissionAction.ALLOW,
            "write": PermissionAction.ASK,
            "edit": PermissionAction.ASK,
            "bash": PermissionAction.ASK,
        })

    # ── serialisation ─────────────────────────────────────────────────

    def to_dict(self) -> dict[str, str]:
        return {k: v.value if isinstance(v, PermissionAction) else v for k, v in self.rules.items()}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PermissionConfig:
        rules: dict[str, str | PermissionAction] = {}
        for key, value in data.items():
            if isinstance(value, PermissionAction):
                rules[key] = value
            elif isinstance(value, str):
                rules[key] = value
            else:
                raise ValueError(f"Invalid permission value for {key!r}: {value!r}")
        return cls(rules=rules)


class PermissionManager:
    """Resolve the effective permission for a tool invocation.

    Resolution strategy
    -------------------
    1. Collect candidate rules from *global*, then *agent* configs.
    2. For ``bash`` tool, also try ``"bash <command-prefix>"`` patterns.
    3. Among matching rules, pick the one with the **highest specificity**.
    4. Ties in specificity broken by **last-defined wins** (later entries
       in the merged rule dict override earlier ones).

    Parameters
    ----------
    global_config : PermissionConfig
        The project-wide default permission set.
    """

    def __init__(self, global_config: PermissionConfig | None = None):
        self.global_config = global_config or PermissionConfig.permissive()

    # ── public API ────────────────────────────────────────────────────

    def check_permission(
        self,
        tool: str,
        args: dict[str, Any],
        agent_config: PermissionConfig | None = None,
    ) -> PermissionAction:
        """Return the effective action for a tool call.

        Resolution strategy
        -------------------
        1. Collect candidate lookup keys from tool name and (for bash) command prefixes.
        2. Merge global rules with agent-specific overrides (agent wins on ties).
        3. Among all matching rules, pick the one with the **highest specificity**.
        4. Ties in specificity broken by **last-defined wins** (later entries in the
           merged dict override earlier ones).

        Parameters
        ----------
        tool : str
            Tool name (e.g. ``"bash"``, ``"write"``).
        args : dict
            The arguments that will be passed to the tool.
            For ``bash``, ``args["command"]`` is inspected for prefix matching.
        agent_config : PermissionConfig, optional
            Per-agent overrides that take priority over global rules.
        """
        merged = self._merge_rules(agent_config)

        # Build candidate lookup keys for this invocation.
        keys = [tool, "*"]

        # For bash, add "bash <command-prefix>" patterns.
        if tool == "bash":
            command = args.get("command", "")
            parts = command.split()
            for end in range(len(parts), 0, -1):
                prefix = " ".join(parts[:end])
                keys.append(f"bash {prefix}")
            keys.append("bash")

        # Scan all rules and collect matches with specificity.
        # Among matches with equal specificity, later entries win.
        best_action: PermissionAction | None = None
        best_specificity = -1

        for pattern, raw_action in merged.items():
            action = _parse_action(raw_action)
            if self._matches(pattern, keys):
                specificity = _pattern_specificity(pattern)
                # Higher specificity wins OR same specificity with later rule wins.
                if specificity >= best_specificity:
                    best_action = action
                    best_specificity = specificity

        return best_action or PermissionAction.DENY

    def is_allowed(
        self,
        tool: str,
        args: dict[str, Any],
        agent_config: PermissionConfig | None = None,
    ) -> bool:
        """Convenience: True if the action is ALLOW (no user confirmation needed)."""
        return self.check_permission(tool, args, agent_config) == PermissionAction.ALLOW

    def needs_confirmation(
        self,
        tool: str,
        args: dict[str, Any],
        agent_config: PermissionConfig | None = None,
    ) -> bool:
        """Convenience: True if the action is ASK (user must confirm)."""
        return self.check_permission(tool, args, agent_config) == PermissionAction.ASK

    def is_denied(
        self,
        tool: str,
        args: dict[str, Any],
        agent_config: PermissionConfig | None = None,
    ) -> bool:
        """Convenience: True if the action is DENY (tool call rejected)."""
        return self.check_permission(tool, args, agent_config) == PermissionAction.DENY

    # ── internal ───────────────────────────────────────────────────────

    @staticmethod
    def _matches(pattern: str, keys: list[str]) -> bool:
        """Check whether *pattern* (possibly a glob) matches any of *keys*.

        A pattern like ``"bash git push *"`` matches the key ``"bash git push origin main"``
        because fnmatch treats the key as the name and the pattern as the glob spec.
        A plain pattern like ``"read"`` matches the exact key ``"read"``.
        """
        for key in keys:
            if pattern == key:
                return True
            # pattern is the glob, key is the string to test against it
            if fnmatch.fnmatch(key, pattern):
                return True
        return False

    def _merge_rules(self, agent_config: PermissionConfig | None) -> dict[str, str | PermissionAction]:
        """Merge global rules with agent-specific overrides.

        Agent rules come **after** global rules so they win on ties.
        """
        merged: dict[str, str | PermissionAction] = {}
        merged.update(self.global_config.rules)
        if agent_config:
            merged.update(agent_config.rules)
        return merged
