"""Slack integration for team collaboration."""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class SlackIntegration:
    """Integrate Anvil with Slack for notifications and collaboration."""

    def __init__(
        self,
        webhook_url: str | None = None,
        bot_token: str | None = None,
    ):
        self.webhook_url = webhook_url or os.getenv("SLACK_WEBHOOK_URL", "")
        self.bot_token = bot_token or os.getenv("SLACK_BOT_TOKEN", "")
        self.api_base = "https://slack.com/api"
        self._client: httpx.Client | None = None

    @property
    def client(self) -> httpx.Client:
        if self._client is None or self._client.is_closed:
            headers: dict[str, str] = {"Content-Type": "application/json"}
            if self.bot_token:
                headers["Authorization"] = f"Bearer {self.bot_token}"
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

    def send_message(
        self,
        channel: str,
        text: str,
        blocks: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Send a message to a Slack channel.

        Args:
            channel: Channel ID or name (e.g. ``#general``).
            text: Fallback text for notifications.
            blocks: Optional Block Kit blocks for rich formatting.

        Returns:
            The Slack API response as a dict.
        """
        payload: dict[str, Any] = {"channel": channel, "text": text}
        if blocks:
            payload["blocks"] = blocks

        try:
            resp = self.client.post("/chat.postMessage", json=payload)
            resp.raise_for_status()
            data = resp.json()
            if not data.get("ok"):
                logger.error("Slack API error: %s", data.get("error"))
            return data
        except httpx.HTTPStatusError as e:
            logger.error("Slack HTTP error %s: %s", e.response.status_code, e.response.text)
            return {"ok": False, "error": f"http_{e.response.status_code}"}
        except httpx.RequestError as e:
            logger.error("Slack request error: %s", e)
            return {"ok": False, "error": str(e)}

    def send_webhook(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Send a payload to the configured incoming webhook URL.

        Args:
            payload: The JSON payload to send.

        Returns:
            A dict with ``ok`` status.
        """
        if not self.webhook_url:
            logger.warning("No Slack webhook URL configured")
            return {"ok": False, "error": "no_webhook_url"}

        try:
            resp = httpx.post(self.webhook_url, json=payload, timeout=15.0)
            if resp.status_code == 200 and resp.text == "ok":
                return {"ok": True}
            logger.error("Slack webhook error %s: %s", resp.status_code, resp.text)
            return {"ok": False, "error": resp.text}
        except httpx.RequestError as e:
            logger.error("Slack webhook request error: %s", e)
            return {"ok": False, "error": str(e)}

    def send_code_review(self, channel: str, pr_url: str, review: dict[str, Any]) -> dict[str, Any]:
        """Send a code review summary to Slack.

        Args:
            channel: Slack channel to post to.
            pr_url: URL of the pull request.
            review: Review data with ``title``, ``status``, and ``issues`` keys.

        Returns:
            The Slack API response.
        """
        blocks: list[dict[str, Any]] = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": "Code Review Complete"},
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*PR:* <{pr_url}|{review.get('title', 'PR')}>",
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"*Status:* {review.get('status', 'Reviewed')}\n"
                        f"*Issues Found:* {len(review.get('issues', []))}"
                    ),
                },
            },
        ]

        issues = review.get("issues", [])
        if issues:
            issues_text = "\n".join(f"* {issue}" for issue in issues[:5])
            if len(issues) > 5:
                issues_text += f"\n_...and {len(issues) - 5} more_"
            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*Issues:*\n{issues_text}"},
            })

        return self.send_message(channel, "Code review complete", blocks)

    def send_deployment_update(
        self,
        channel: str,
        service: str,
        status: str,
        version: str,
    ) -> dict[str, Any]:
        """Send a deployment status update to Slack.

        Args:
            channel: Slack channel to post to.
            service: Name of the deployed service.
            status: Deployment status (``success`` or ``failure``).
            version: Version string that was deployed.

        Returns:
            The Slack API response.
        """
        emoji = ":white_check_mark:" if status == "success" else ":x:"
        text = f"{emoji} *{service}* deployed {status} (v{version})"
        return self.send_message(channel, text)

    def send_alert(
        self,
        channel: str,
        title: str,
        message: str,
        severity: str = "warning",
    ) -> dict[str, Any]:
        """Send an alert to Slack.

        Args:
            channel: Slack channel to post to.
            title: Alert title.
            message: Alert body.
            severity: One of ``info``, ``warning``, ``error``.

        Returns:
            The Slack API response.
        """
        severity_emoji = {"info": ":information_source:", "warning": ":warning:", "error": ":rotating_light:"}
        emoji = severity_emoji.get(severity, ":warning:")

        blocks: list[dict[str, Any]] = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"{emoji} *{title}*\n{message}",
                },
            },
        ]

        return self.send_message(channel, title, blocks)

    def create_interactive_message(
        self,
        channel: str,
        text: str,
        actions: list[dict[str, str]],
    ) -> dict[str, Any]:
        """Send a message with interactive buttons.

        Args:
            channel: Slack channel to post to.
            text: Message text.
            actions: List of action dicts with ``label``, ``id``, and
                optional ``value`` keys.

        Returns:
            The Slack API response.
        """
        blocks: list[dict[str, Any]] = [
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": text},
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": action["label"]},
                        "action_id": action["id"],
                        "value": action.get("value", ""),
                    }
                    for action in actions
                ],
            },
        ]

        return self.send_message(channel, text, blocks)
