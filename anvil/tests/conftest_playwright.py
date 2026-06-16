"""Playwright configuration for E2E tests."""

import pytest


@pytest.fixture(scope="session")
def browser_type_launch_args():
    """Configure browser launch arguments."""
    return {
        "headless": True,  # Set to False to see the browser
        "slow_mo": 100,  # Slow down actions for visibility
    }


@pytest.fixture(scope="session")
def browser_context_args(browser_type_launch_args):
    """Configure browser context."""
    return {
        "viewport": {"width": 1920, "height": 1080},
        "ignore_https_errors": True,
    }
