"""Integrations with the FableForge ecosystem."""

from anvil.integrations.agent_swarm import AgentSwarmIntegration
from anvil.integrations.cost_optimizer import CostOptimizerIntegration
from anvil.integrations.discord import DiscordIntegration
from anvil.integrations.error_recovery import ErrorRecoveryIntegration
from anvil.integrations.github_actions import GitHubActionsIntegration
from anvil.integrations.notifications import NotificationManager
from anvil.integrations.scheduler import RoutinesManager, TaskScheduler
from anvil.integrations.slack import SlackIntegration
from anvil.integrations.verifyloop import VerifyLoopIntegration

__all__ = [
    "VerifyLoopIntegration",
    "ErrorRecoveryIntegration",
    "AgentSwarmIntegration",
    "CostOptimizerIntegration",
    "DiscordIntegration",
    "GitHubActionsIntegration",
    "NotificationManager",
    "RoutinesManager",
    "SlackIntegration",
    "TaskScheduler",
]
