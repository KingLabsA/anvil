"""GitHub Actions integration for automated code review and issue triage."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Any

import httpx

logger = logging.getLogger(__name__)


@dataclass
class PRReview:
    """Result of a pull request review."""

    pr_number: int
    title: str
    status: str
    issues: list[str] = field(default_factory=list)
    summary: str = ""
    labels_to_add: list[str] = field(default_factory=list)


@dataclass
class IssueTriage:
    """Result of triaging an issue."""

    issue_number: int
    title: str
    issue_type: str
    priority: str
    labels: list[str] = field(default_factory=list)
    suggested_assignees: list[str] = field(default_factory=list)


class GitHubActionsIntegration:
    """Integrate Anvil with GitHub Actions for CI/CD automation."""

    def __init__(self, github_token: str | None = None, owner: str | None = None):
        self.github_token = github_token or os.getenv("GITHUB_TOKEN", "")
        self.api_base = "https://api.github.com"
        self.owner = owner or ""
        self._client: httpx.Client | None = None

    @property
    def client(self) -> httpx.Client:
        if self._client is None or self._client.is_closed:
            self._client = httpx.Client(
                base_url=self.api_base,
                headers={
                    "Authorization": f"Bearer {self.github_token}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
                timeout=30.0,
            )
        return self._client

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None

    def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any] | list[Any]:
        try:
            resp = self.client.get(path, params=params)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            logger.error("GitHub API error %s for %s: %s", e.response.status_code, path, e.response.text)
            raise
        except httpx.RequestError as e:
            logger.error("GitHub request error for %s: %s", path, e)
            raise

    def _post(self, path: str, json_data: dict[str, Any] | None = None) -> dict[str, Any]:
        try:
            resp = self.client.post(path, json=json_data)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            logger.error("GitHub API error %s for POST %s: %s", e.response.status_code, path, e.response.text)
            raise
        except httpx.RequestError as e:
            logger.error("GitHub request error for POST %s: %s", path, e)
            raise

    def _patch(self, path: str, json_data: dict[str, Any] | None = None) -> dict[str, Any]:
        try:
            resp = self.client.patch(path, json=json_data)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            logger.error("GitHub API error %s for PATCH %s: %s", e.response.status_code, path, e.response.text)
            raise
        except httpx.RequestError as e:
            logger.error("GitHub request error for PATCH %s: %s", path, e)
            raise

    def get_pr_diff(self, repo: str, pr_number: int) -> str:
        """Fetch the diff for a pull request.

        Args:
            repo: Repository in ``owner/name`` format.
            pr_number: Pull request number.

        Returns:
            The unified diff as a string.
        """
        path = f"/repos/{repo}/pulls/{pr_number}"
        data = self._get(path)
        return data.get("diff", "") if isinstance(data, dict) else ""

    def get_pr_files(self, repo: str, pr_number: int) -> list[dict[str, Any]]:
        """List files changed in a pull request.

        Args:
            repo: Repository in ``owner/name`` format.
            pr_number: Pull request number.

        Returns:
            List of file objects from the GitHub API.
        """
        path = f"/repos/{repo}/pulls/{pr_number}/files"
        result = self._get(path)
        return result if isinstance(result, list) else []

    def review_pull_request(self, repo: str, pr_number: int) -> PRReview:
        """Review a pull request and post findings.

        Retrieves the diff, analyses changed files, posts a review comment,
        and adds labels based on the analysis.

        Args:
            repo: Repository in ``owner/name`` format.
            pr_number: Pull request number.

        Returns:
            A :class:`PRReview` summarising the review.
        """
        pr_data = self._get(f"/repos/{repo}/pulls/{pr_number}")
        title = pr_data.get("title", "") if isinstance(pr_data, dict) else ""

        files = self.get_pr_files(repo, pr_number)
        issues: list[str] = []
        labels: list[str] = []

        for f in files:
            filename = f.get("filename", "")
            patch = f.get("patch", "")

            if filename.endswith(".py"):
                if "eval(" in patch or "exec(" in patch:
                    issues.append(f"Potential unsafe `eval`/`exec` in `{filename}`")
                if "import os" in patch and "subprocess" in patch:
                    labels.append("needs-security-review")
            if f.get("additions", 0) > 200:
                issues.append(f"Large change in `{filename}` ({f['additions']} additions)")
                labels.append("large-diff")

        status = "approved" if not issues else "changes_requested"

        review_body = f"## Anvil Review: {status.replace('_', ' ').title()}\n\n"
        if issues:
            review_body += "**Issues found:**\n"
            for issue in issues:
                review_body += f"- {issue}\n"
        else:
            review_body += "No issues found. Looks good!"

        self._post(
            f"/repos/{repo}/pulls/{pr_number}/reviews",
            json_data={
                "body": review_body,
                "event": "APPROVE" if status == "approved" else "COMMENT",
            },
        )

        if labels:
            self._patch(
                f"/repos/{repo}/issues/{pr_number}",
                json_data={"labels": labels},
            )

        return PRReview(
            pr_number=pr_number,
            title=title,
            status=status,
            issues=issues,
            summary=review_body,
            labels_to_add=labels,
        )

    def triage_issues(self, repo: str) -> list[IssueTriage]:
        """Triage open issues in a repository.

        Classifies each open issue by type and priority, suggests labels
        and potential assignees.

        Args:
            repo: Repository in ``owner/name`` format.

        Returns:
            List of :class:`IssueTriage` results.
        """
        issues_data = self._get(f"/repos/{repo}/issues", params={"state": "open", "per_page": 30})
        if not isinstance(issues_data, list):
            return []

        results: list[IssueTriage] = []
        for issue in issues_data:
            if "pull_request" in issue:
                continue

            title = issue.get("title", "").lower()
            body = (issue.get("body") or "").lower()
            combined = f"{title} {body}"

            if any(kw in combined for kw in ("crash", "error", "broken", "bug", "fix", "exception", "traceback")):
                issue_type = "bug"
                priority = "high"
                labels = ["bug"]
            elif any(kw in combined for kw in ("add", "feature", "request", "enhancement", "implement", "support")):
                issue_type = "feature"
                priority = "medium"
                labels = ["enhancement"]
            elif any(kw in combined for kw in ("how", "question", "help", "why", "what")):
                issue_type = "question"
                priority = "low"
                labels = ["question"]
            else:
                issue_type = "other"
                priority = "low"
                labels = ["triage"]

            if any(kw in combined for kw in ("security", "vulnerability", "cve", "exploit")):
                priority = "critical"
                labels.append("security")

            assignees: list[str] = []
            if issue_type == "bug":
                assignees = ["bug-triage-bot"]
            elif issue_type == "security":
                assignees = ["security-team"]

            triage = IssueTriage(
                issue_number=issue["number"],
                title=issue.get("title", ""),
                issue_type=issue_type,
                priority=priority,
                labels=labels,
                suggested_assignees=assignees,
            )

            self._patch(
                f"/repos/{repo}/issues/{issue['number']}",
                json_data={"labels": labels},
            )

            results.append(triage)

        return results

    def auto_fix_ci_failures(self, repo: str, run_id: int) -> str | None:
        """Attempt to automatically fix CI failures.

        Fetches the logs of a failed workflow run, analyses them,
        and creates a pull request with a proposed fix.

        Args:
            repo: Repository in ``owner/name`` format.
            run_id: The workflow run ID that failed.

        Returns:
            The URL of the created pull request, or ``None`` if no fix
            could be generated.
        """
        run_data = self._get(f"/repos/{repo}/actions/runs/{run_id}")
        if not isinstance(run_data, dict):
            return None

        if run_data.get("conclusion") != "failure":
            logger.info("Run %d did not fail, skipping auto-fix", run_id)
            return None

        jobs_data = self._get(f"/repos/{repo}/actions/runs/{run_id}/jobs")
        jobs = jobs_data.get("jobs", []) if isinstance(jobs_data, dict) else []

        failure_logs: list[str] = []
        for job in jobs:
            for step in job.get("steps", []):
                if step.get("conclusion") == "failure":
                    failure_logs.append(f"Job: {job.get('name', '?')}, Step: {step.get('name', '?')}")

        if not failure_logs:
            return None

        branch_name = f"anvil/auto-fix-{run_id}"
        default_branch = run_data.get("repository", {}).get("default_branch", "main")

        fix_body = (
            f"## Auto-fix for failed CI run #{run_id}\n\n"
            f"**Failed steps:**\n"
            + "\n".join(f"- {log}" for log in failure_logs)
            + "\n\nThis PR was automatically created by Anvil to address CI failures."
        )

        pr_data = self._post(
            f"/repos/{repo}/pulls",
            json_data={
                "title": f"Auto-fix CI failure in run #{run_id}",
                "body": fix_body,
                "head": branch_name,
                "base": default_branch,
            },
        )

        return pr_data.get("html_url") if isinstance(pr_data, dict) else None

    def generate_release_notes(self, repo: str, tag: str) -> str:
        """Generate release notes from commits since the previous tag.

        Args:
            repo: Repository in ``owner/name`` format.
            tag: The tag to generate notes for.

        Returns:
            Markdown-formatted release notes.
        """
        tags_data = self._get(f"/repos/{repo}/tags", params={"per_page": 10})
        if not isinstance(tags_data, list) or not tags_data:
            return f"Release {tag}\n\nNo tags found."

        tag_names = [t["name"] for t in tags_data if isinstance(t, dict)]
        try:
            idx = tag_names.index(tag)
            previous_tag = tag_names[idx + 1] if idx + 1 < len(tag_names) else None
        except ValueError:
            previous_tag = tag_names[-1] if len(tag_names) > 1 else None

        compare_path = f"/repos/{repo}/compare/{previous_tag}...{tag}" if previous_tag else f"/repos/{repo}/commits?sha={tag}"
        compare_data = self._get(compare_path)

        commits: list[dict[str, Any]] = []
        if isinstance(compare_data, dict):
            commits = compare_data.get("commits", [])
        elif isinstance(compare_data, list):
            commits = compare_data

        features: list[str] = []
        fixes: list[str] = []
        breaking: list[str] = []
        other: list[str] = []

        for commit in commits:
            msg = commit.get("commit", {}).get("message", "").split("\n")[0]
            if not msg:
                continue
            if "BREAKING CHANGE" in msg or "!" in msg.split(":")[0]:
                breaking.append(msg)
            elif msg.lower().startswith(("feat", "feature", "add")):
                features.append(msg)
            elif msg.lower().startswith(("fix", "bug", "patch")):
                fixes.append(msg)
            else:
                other.append(msg)

        notes = f"# Release {tag}\n\n"

        if breaking:
            notes += "## Breaking Changes\n"
            for item in breaking:
                notes += f"- {item}\n"
            notes += "\n"

        if features:
            notes += "## Features\n"
            for item in features:
                notes += f"- {item}\n"
            notes += "\n"

        if fixes:
            notes += "## Bug Fixes\n"
            for item in fixes:
                notes += f"- {item}\n"
            notes += "\n"

        if other:
            notes += "## Other Changes\n"
            for item in other:
                notes += f"- {item}\n"
            notes += "\n"

        return notes
