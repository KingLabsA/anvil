"""Scheduled tasks and routines for Anvil."""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ScheduledTask:
    """A scheduled task definition."""

    name: str
    interval_seconds: int
    handler: Callable[[], None]
    enabled: bool = True
    last_run: datetime | None = None
    next_run: datetime | None = None
    run_count: int = 0
    error_count: int = 0
    last_error: str | None = None


class TaskScheduler:
    """Schedule and run recurring tasks in a background thread."""

    def __init__(self) -> None:
        self.tasks: list[ScheduledTask] = []
        self._running = False
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()

    def add_task(
        self,
        name: str,
        interval_seconds: int,
        handler: Callable[[], None],
        run_immediately: bool = False,
    ) -> ScheduledTask:
        """Add a recurring task.

        Args:
            name: Unique task name.
            interval_seconds: Seconds between executions.
            handler: Zero-argument callable to execute.
            run_immediately: Whether to run the task once before the
                first interval elapses.

        Returns:
            The created :class:`ScheduledTask`.

        Raises:
            ValueError: If a task with the same name already exists.
        """
        with self._lock:
            if any(t.name == name for t in self.tasks):
                raise ValueError(f"Task '{name}' already exists")

        now = datetime.now()
        task = ScheduledTask(
            name=name,
            interval_seconds=interval_seconds,
            handler=handler,
            next_run=now if run_immediately else now + timedelta(seconds=interval_seconds),
        )

        with self._lock:
            self.tasks.append(task)

        logger.info("Scheduled task '%s' every %ds", name, interval_seconds)
        return task

    def remove_task(self, name: str) -> bool:
        """Remove a task by name.

        Args:
            name: The task name to remove.

        Returns:
            ``True`` if the task was found and removed.
        """
        with self._lock:
            before = len(self.tasks)
            self.tasks = [t for t in self.tasks if t.name != name]
            removed = len(self.tasks) < before

        if removed:
            logger.info("Removed task '%s'", name)
        return removed

    def enable_task(self, name: str) -> None:
        """Enable a disabled task."""
        with self._lock:
            for task in self.tasks:
                if task.name == name:
                    task.enabled = True
                    task.next_run = datetime.now() + timedelta(seconds=task.interval_seconds)
                    logger.info("Enabled task '%s'", name)
                    return
        raise ValueError(f"Task '{name}' not found")

    def disable_task(self, name: str) -> None:
        """Disable a task without removing it."""
        with self._lock:
            for task in self.tasks:
                if task.name == name:
                    task.enabled = False
                    logger.info("Disabled task '%s'", name)
                    return
        raise ValueError(f"Task '{name}' not found")

    def run_now(self, task_name: str) -> None:
        """Run a task immediately, outside the normal schedule.

        Args:
            task_name: The task to run.

        Raises:
            ValueError: If the task is not found.
        """
        with self._lock:
            task = next((t for t in self.tasks if t.name == task_name), None)

        if task is None:
            raise ValueError(f"Task '{task_name}' not found")

        self._execute_task(task)

    def _execute_task(self, task: ScheduledTask) -> None:
        """Execute a single task with error handling."""
        try:
            logger.debug("Running task '%s'", task.name)
            task.handler()
            task.last_run = datetime.now()
            task.run_count += 1
            task.next_run = datetime.now() + timedelta(seconds=task.interval_seconds)
            logger.debug("Task '%s' completed successfully", task.name)
        except Exception as e:
            task.error_count += 1
            task.last_error = str(e)
            task.next_run = datetime.now() + timedelta(seconds=task.interval_seconds)
            logger.error("Task '%s' failed: %s", task.name, e, exc_info=True)

    def _loop(self) -> None:
        """Background loop that checks and runs due tasks."""
        logger.info("Scheduler started with %d task(s)", len(self.tasks))
        while self._running:
            now = datetime.now()
            with self._lock:
                due_tasks = [
                    t for t in self.tasks
                    if t.enabled and t.next_run is not None and t.next_run <= now
                ]

            for task in due_tasks:
                if self._running:
                    self._execute_task(task)

            time.sleep(1)

        logger.info("Scheduler stopped")

    def start(self, blocking: bool = False) -> None:
        """Start the scheduler.

        Args:
            blocking: If ``True``, run in the current thread.
                If ``False``, run in a background daemon thread.
        """
        if self._running:
            logger.warning("Scheduler is already running")
            return

        self._running = True

        if blocking:
            self._loop()
        else:
            self._thread = threading.Thread(target=self._loop, daemon=True, name="anvil-scheduler")
            self._thread.start()

    def stop(self, timeout: float = 10.0) -> None:
        """Stop the scheduler.

        Args:
            timeout: Maximum seconds to wait for the background thread.
        """
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=timeout)
            self._thread = None

    def get_status(self) -> list[dict[str, Any]]:
        """Get the status of all scheduled tasks.

        Returns:
            List of dicts with task name, enabled state, run count,
            error count, last run, and next run.
        """
        with self._lock:
            return [
                {
                    "name": t.name,
                    "enabled": t.enabled,
                    "interval_seconds": t.interval_seconds,
                    "run_count": t.run_count,
                    "error_count": t.error_count,
                    "last_error": t.last_error,
                    "last_run": t.last_run.isoformat() if t.last_run else None,
                    "next_run": t.next_run.isoformat() if t.next_run else None,
                }
                for t in self.tasks
            ]


class RoutinesManager:
    """Manage predefined routines built on top of :class:`TaskScheduler`."""

    def __init__(self, anvil_engine: Any, scheduler: TaskScheduler | None = None) -> None:
        self.anvil = anvil_engine
        self.scheduler = scheduler or TaskScheduler()
        self._register_default_routines()

    def _register_default_routines(self) -> None:
        """Register the default set of routines."""
        self.scheduler.add_task(
            name="daily_pr_review",
            interval_seconds=86400,
            handler=self._daily_pr_review,
        )

        self.scheduler.add_task(
            name="weekly_dependency_audit",
            interval_seconds=604800,
            handler=self._weekly_dependency_audit,
        )

        self.scheduler.add_task(
            name="hourly_ci_check",
            interval_seconds=3600,
            handler=self._hourly_ci_check,
        )

    def _daily_pr_review(self) -> None:
        """Review all open pull requests."""
        logger.info("Running daily PR review")
        try:
            if hasattr(self.anvil, "github"):
                gh = self.anvil.github
                if hasattr(gh, "get_open_prs"):
                    prs = gh.get_open_prs()
                    for pr in prs:
                        try:
                            gh.review_pull_request(pr["repo"], pr["number"])
                        except Exception as e:
                            logger.error("Failed to review PR #%s in %s: %s", pr["number"], pr["repo"], e)
        except Exception as e:
            logger.error("Daily PR review failed: %s", e)

    def _weekly_dependency_audit(self) -> None:
        """Audit project dependencies for outdated or vulnerable packages."""
        logger.info("Running weekly dependency audit")
        try:
            if hasattr(self.anvil, "run_command"):
                result = self.anvil.run_command("pip list --outdated --format=json")
                if result and hasattr(result, "strip"):
                    import json
                    outdated = json.loads(result)
                    if outdated:
                        logger.warning("Found %d outdated dependencies", len(outdated))
        except Exception as e:
            logger.error("Weekly dependency audit failed: %s", e)

    def _hourly_ci_check(self) -> None:
        """Check for recent CI failures and attempt auto-fixes."""
        logger.info("Running hourly CI check")
        try:
            if hasattr(self.anvil, "github"):
                gh = self.anvil.github
                if hasattr(gh, "get_recent_failed_runs"):
                    runs = gh.get_recent_failed_runs()
                    for run in runs:
                        try:
                            gh.auto_fix_ci_failures(run["repo"], run["id"])
                        except Exception as e:
                            logger.error("Failed to auto-fix run %s in %s: %s", run["id"], run["repo"], e)
        except Exception as e:
            logger.error("Hourly CI check failed: %s", e)

    def start(self, blocking: bool = False) -> None:
        """Start all routines.

        Args:
            blocking: If ``True``, block the current thread.
        """
        self.scheduler.start(blocking=blocking)

    def stop(self) -> None:
        """Stop all routines."""
        self.scheduler.stop()
