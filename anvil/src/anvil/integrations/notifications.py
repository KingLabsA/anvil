"""Slack and Discord notification integration for Anvil."""

from __future__ import annotations

import json
import urllib.request
import urllib.error
from typing import Any
from dataclasses import dataclass


@dataclass
class NotificationConfig:
    """Configuration for notifications."""
    slack_webhook_url: str | None = None
    discord_webhook_url: str | None = None
    notify_on_success: bool = True
    notify_on_failure: bool = True
    notify_on_task_start: bool = False


class NotificationManager:
    """Manages Slack and Discord notifications."""
    
    def __init__(self, config: NotificationConfig | None = None):
        """Initialize notification manager.
        
        Args:
            config: Notification configuration
        """
        self.config = config or NotificationConfig()
    
    def send_slack_notification(self, message: str, color: str = "good") -> bool:
        """Send a notification to Slack.
        
        Args:
            message: Notification message
            color: Message color (good, warning, danger)
        
        Returns:
            True if sent successfully, False otherwise
        """
        if not self.config.slack_webhook_url:
            return False
        
        payload = {
            "attachments": [
                {
                    "color": color,
                    "text": message,
                    "footer": "Anvil - Self-Verified Coding Agent",
                    "ts": int(__import__('time').time()),
                }
            ]
        }
        
        try:
            data = json.dumps(payload).encode('utf-8')
            req = urllib.request.Request(
                self.config.slack_webhook_url,
                data=data,
                headers={'Content-Type': 'application/json'},
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                return response.status == 200
        except Exception as e:
            print(f"Failed to send Slack notification: {e}")
            return False
    
    def send_discord_notification(self, message: str, color: int = 0x00ff00) -> bool:
        """Send a notification to Discord.
        
        Args:
            message: Notification message
            color: Embed color (decimal)
        
        Returns:
            True if sent successfully, False otherwise
        """
        if not self.config.discord_webhook_url:
            return False
        
        payload = {
            "embeds": [
                {
                    "description": message,
                    "color": color,
                    "footer": {
                        "text": "Anvil - Self-Verified Coding Agent",
                    },
                }
            ]
        }
        
        try:
            data = json.dumps(payload).encode('utf-8')
            req = urllib.request.Request(
                self.config.discord_webhook_url,
                data=data,
                headers={'Content-Type': 'application/json'},
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                return response.status in (200, 204)
        except Exception as e:
            print(f"Failed to send Discord notification: {e}")
            return False
    
    def notify_task_start(self, task: str) -> None:
        """Notify that a task has started.
        
        Args:
            task: Task description
        """
        if not self.config.notify_on_task_start:
            return
        
        message = f"🚀 **Task Started**\n\n{task}"
        
        if self.config.slack_webhook_url:
            self.send_slack_notification(message, color="good")
        
        if self.config.discord_webhook_url:
            self.send_discord_notification(message, color=0x00ff00)
    
    def notify_task_complete(self, task: str, success: bool, output: str = "") -> None:
        """Notify that a task has completed.
        
        Args:
            task: Task description
            success: Whether the task succeeded
            output: Task output (optional)
        """
        should_notify = (
            (success and self.config.notify_on_success) or
            (not success and self.config.notify_on_failure)
        )
        
        if not should_notify:
            return
        
        status = "✅" if success else "❌"
        status_text = "Completed" if success else "Failed"
        
        message = f"{status} **Task {status_text}**\n\n{task}"
        
        if output:
            # Truncate long output
            output_preview = output[:500] + "..." if len(output) > 500 else output
            message += f"\n\n```\n{output_preview}\n```"
        
        color = "good" if success else "danger"
        discord_color = 0x00ff00 if success else 0xff0000
        
        if self.config.slack_webhook_url:
            self.send_slack_notification(message, color=color)
        
        if self.config.discord_webhook_url:
            self.send_discord_notification(message, color=discord_color)
    
    def notify_verification(self, file_path: str, passed: bool, failures: list[str] | None = None) -> None:
        """Notify about verification results.
        
        Args:
            file_path: File that was verified
            passed: Whether verification passed
            failures: List of failure messages (optional)
        """
        status = "✅" if passed else "❌"
        status_text = "Passed" if passed else "Failed"
        
        message = f"{status} **Verification {status_text}**\n\nFile: `{file_path}`"
        
        if failures:
            message += "\n\n**Failures:**\n" + "\n".join(f"• {f}" for f in failures[:5])
        
        color = "good" if passed else "danger"
        discord_color = 0x00ff00 if passed else 0xff0000
        
        if self.config.slack_webhook_url:
            self.send_slack_notification(message, color=color)
        
        if self.config.discord_webhook_url:
            self.send_discord_notification(message, color=discord_color)
    
    def notify_error(self, error: str, context: str = "") -> None:
        """Notify about an error.
        
        Args:
            error: Error message
            context: Additional context (optional)
        """
        message = f"⚠️ **Error**\n\n{error}"
        
        if context:
            message += f"\n\nContext: {context}"
        
        if self.config.slack_webhook_url:
            self.send_slack_notification(message, color="danger")
        
        if self.config.discord_webhook_url:
            self.send_discord_notification(message, color=0xff0000)
