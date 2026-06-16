"""Tests for browser automation."""

import pytest
from anvil.browser.automator import BrowserAutomator, BrowserAction, BrowserState


class TestBrowserAutomator:
    """Test browser automator."""
    
    def test_init(self):
        automator = BrowserAutomator()
        assert automator.is_running is False
        assert automator.state.is_connected is False
    
    def test_connect_disconnect(self):
        automator = BrowserAutomator()
        assert automator.connect() is True
        assert automator.is_running is True
        assert automator.state.is_connected is True
        
        automator.disconnect()
        assert automator.is_running is False
        assert automator.state.is_connected is False
    
    def test_navigate(self):
        automator = BrowserAutomator()
        automator.connect()
        state = automator.navigate("https://example.com")
        assert state.url == "https://example.com"
        assert len(automator.actions) == 1
    
    def test_click(self):
        automator = BrowserAutomator()
        automator.connect()
        state = automator.click("#button")
        assert len(automator.actions) == 1
        assert automator.actions[0].action == "click"
    
    def test_type_text(self):
        automator = BrowserAutomator()
        automator.connect()
        state = automator.type_text("#input", "hello")
        assert len(automator.actions) == 1
        assert automator.actions[0].value == "hello"
    
    def test_screenshot(self):
        automator = BrowserAutomator()
        automator.connect()
        path = automator.screenshot("test.png")
        assert path == "test.png"
        assert automator.state.screenshot_path == "test.png"
    
    def test_get_actions_history(self):
        automator = BrowserAutomator()
        automator.connect()
        automator.navigate("https://example.com")
        automator.click("#button")
        
        history = automator.get_actions_history()
        assert len(history) == 2
        assert history[0].action == "navigate"
        assert history[1].action == "click"
    
    def test_clear_actions(self):
        automator = BrowserAutomator()
        automator.connect()
        automator.navigate("https://example.com")
        automator.clear_actions()
        assert len(automator.actions) == 0


class TestBrowserAction:
    """Test browser action dataclass."""
    
    def test_create_action(self):
        action = BrowserAction(
            action="click",
            target="#button",
            value="",
            options={"timeout": 5000},
        )
        assert action.action == "click"
        assert action.target == "#button"
        assert action.options["timeout"] == 5000


class TestBrowserState:
    """Test browser state dataclass."""
    
    def test_create_state(self):
        state = BrowserState(
            url="https://example.com",
            title="Example",
            is_connected=True,
            screenshot_path="screenshot.png",
        )
        assert state.url == "https://example.com"
        assert state.is_connected is True
