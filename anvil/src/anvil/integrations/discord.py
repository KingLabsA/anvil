"""Discord integration for team collaboration."""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class DiscordIntegration:
    """Integrate Anvil with Discord for notifications and collaboration."""

    def __init__(
        self,
        webhook_url: str | None = None,
        bot_token: str | None = None,
    ):
        self.webhook_url = webhook_url or os.getenv("DISCORD_WEBHOOK_URL", "")
        self.bot_token = bot_token or os.getenv("DISCORD_BOT_TOKEN", "")
        self.api_base = "https://discord.com/api/v10"
        self._client: httpx.Client | None = None

    @property
    def client(self) -> httpx.Client:
        if self._client is None or self._client.is_closed:
            headers: dict[str, str] = {"Content-Type": "application/json"}
            if self.bot_token:
                headers["Authorization"] = f"Bot {self.bot_token}"
            self._client = httpx.Client(
                base_url=self.api_base,
                headers=headers,
                timeout=15.0,
            )
        return self._client

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None

    def send_webhook(
        self,
        content: str,
        embeds: list[dict[str, Any]] | None = None,
        username: str | None = None,
        avatar_url: str | None = None,
    ) -> dict[str, Any]:
        """Send a message via Discord webhook.

        Args:
            content: Plain text message content.
            embeds: Optional list of embed objects.
            username: Override the webhook's default username.
            avatar_url: Override the webhook's default avatar.

        Returns:
            The Discord API response as a dict.
        """
        if not self.webhook_url:
            logger.warning("No Discord webhook URL configured")
            return {"error": "no_webhook_url"}

        payload: dict[str, Any] = {"content": content}
        if embeds:
            payload["embeds"] = embeds
        if username:
            payload["username"] = username
        if avatar_url:
            payload["avatar_url"] = avatar_url

        try:
            resp = httpx.post(self.webhook_url, json=payload, timeout=15.0)
            if resp.status_code in (200, 204):
                return {"ok": True}
            logger.error("Discord webhook error %s: %s", resp.status_code, resp.text)
            return {"error": resp.text, "status_code": resp.status_code}
        except httpx.RequestError as e:
            logger.error("Discord webhook request error: %s", e)
            return {"error": str(e)}

    def send_message(
        self,
        channel_id: str,
        content: str,
        embeds: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Send a message to a Discord channel via the bot API.

        Requires ``bot_token`` to be configured.

        Args:
            channel_id: The Discord channel ID.
            content: Plain text message content.
            embeds: Optional list of embed objects.

        Returns:
            The Discord API response as a dict.
        """
        if not self.bot_token:
            logger.warning("No Discord bot token configured; falling back to webhook")
            return self.send_webhook(content, embeds)

        payload: dict[str, Any] = {"content": content}
        if embeds:
            payload["embeds"] = embeds

        try:
            resp = self.client.post(f"/channels/{channel_id}/messages", json=payload)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            logger.error("Discord API error %s: %s", e.response.status_code, e.response.text)
            return {"error": e.response.text, "status_code": e.response.status_code}
        except httpx.RequestError as e:
            logger.error("Discord request error: %s", e)
            return {"error": str(e)}

    def send_code_review(self, pr_url: str, review: dict[str, Any]) -> dict[str, Any]:
        """Send a code review summary to Discord.

        Uses the webhook if no channel ID is specified.

        Args:
            pr_url: URL of the pull request.
            review: Review data with ``title``, ``status``, and ``issues`` keys.

        Returns:
            The Discord API response.
        """
        is_approved = review.get("status") == "approved"
        color = 0x00FF00 if is_approved else 0xFF9900
        status_emoji = ":white_check_mark:" if is_approved else ":warning:"

        issues = review.get("issues", [])
        description = (
            f"**PR:** [{review.get('title', 'PR')}]({pr_url})\n"
            f"**Status:** {review.get('status', 'Reviewed')}\n"
            f"**Issues Found:** {len(issues)}"
        )

        embed: dict[str, Any] = {
            "title": f"{status_emoji} Code Review Complete",
            "description": description,
            "color": color,
            "footer": {"text": "Anvil - Self-Verified Coding Agent"},
        }

        if issues:
            issues_text = "\n".join(f"- {issue}" for issue in issues[:5])
            if len(issues) > 5:
                issues_text += f"\n*...and {len(issues) - 5} more*"
            embed["fields"] = [{"name": "Issues", "value": issues_text}]

        return self.send_webhook("", embeds=[embed])

    def send_deployment_update(self, service: str, status: str, version: str) -> dict[str, Any]:
        """Send a deployment status update to Discord.

        Args:
            service: Name of the deployed service.
            status: Deployment status (``success`` or ``failure``).
            version: Version string that was deployed.

        Returns:
            The Discord API response.
        """
        is_success = status == "success"
        color = 0x00FF00 if is_success else 0xFF0000
        emoji = ":white_check_mark:" if is_success else ":x:"

        embed: dict[str, Any] = {
            "title": f"{emoji} Deployment {status.title()}",
            "description": f"**Service:** {service}\n**Version:** {version}",
            "color": color,
            "footer": {"text": "Anvil - Self-Verified Coding Agent"},
        }

        return self.send_webhook("", embeds=[embed])

    def send_alert(
        self,
        title: str,
        message: str,
        severity: str = "warning",
    ) -> dict[str, Any]:
        """Send an alert to Discord.

        Args:
            title: Alert title.
            message: Alert body.
            severity: One of ``info``, ``warning``, ``error``.

        Returns:
            The Discord API response.
        """
        colors = {"info": 0x3498DB, "warning": 0xFF9900, "error": 0xFF0000}
        emoji_map = {"info": ":information_source:", "warning": ":warning:", "error": ":rotating_light:"}

        embed: dict[str, Any] = {
            "title": f"{emoji_map.get(severity, ':warning:')} {title}",
            "description": message,
            "color": colors.get(severity, 0xFF9900),
            "footer": {"text": "Anvil - Self-Verified Coding Agent"},
        }

        return self.send_webhook("", embeds=[embed])
