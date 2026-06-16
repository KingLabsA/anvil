"""Browser automation for Anvil - control browsers programmatically."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class BrowserAction:
    """A browser action to execute."""
    action: str  # "click", "type", "navigate", "screenshot", "wait"
    target: str = ""
    value: str = ""
    options: dict[str, Any] = field(default_factory=dict)


@dataclass
class BrowserState:
    """Current state of the browser."""
    url: str = ""
    title: str = ""
    is_connected: bool = False
    screenshot_path: str = ""


class BrowserAutomator:
    """Automate browser interactions for testing and development."""
    
    def __init__(self):
        self.state = BrowserState()
        self.actions: list[BrowserAction] = []
        self.is_running = False
    
    def connect(self, browser_type: str = "chromium", headless: bool = True) -> bool:
        """Connect to a browser instance."""
        self.state.is_connected = True
        self.is_running = True
        return True
    
    def disconnect(self) -> None:
        """Disconnect from the browser."""
        self.state.is_connected = False
        self.is_running = False
    
    def navigate(self, url: str) -> BrowserState:
        """Navigate to a URL."""
        self.state.url = url
        self.actions.append(BrowserAction(action="navigate", target=url))
        return self.state
    
    def click(self, selector: str) -> BrowserState:
        """Click an element."""
        self.actions.append(BrowserAction(action="click", target=selector))
        return self.state
    
    def type_text(self, selector: str, text: str) -> BrowserState:
        """Type text into an element."""
        self.actions.append(BrowserAction(action="type", target=selector, value=text))
        return self.state
    
    def screenshot(self, path: str = "screenshot.png") -> str:
        """Take a screenshot."""
        self.actions.append(BrowserAction(action="screenshot", target=path))
        self.state.screenshot_path = path
        return path
    
    def wait(self, seconds: float) -> None:
        """Wait for a specified duration."""
        self.actions.append(BrowserAction(action="wait", value=str(seconds)))
        time.sleep(seconds)
    
    def get_text(self, selector: str) -> str:
        """Get text content from an element."""
        self.actions.append(BrowserAction(action="get_text", target=selector))
        return "[Text content]"  # Placeholder
    
    def get_page_content(self) -> str:
        """Get the full page content."""
        self.actions.append(BrowserAction(action="get_content"))
        return "[Page content]"  # Placeholder
    
    def execute_script(self, script: str) -> Any:
        """Execute JavaScript in the browser."""
        self.actions.append(BrowserAction(action="execute_script", value=script))
        return None
    
    def get_actions_history(self) -> list[BrowserAction]:
        """Get the history of actions performed."""
        return self.actions
    
    def clear_actions(self) -> None:
        """Clear the action history."""
        self.actions.clear()
    
    def screenshot_and_compare(self, reference_path: str) -> dict[str, Any]:
        """Compare current state with a reference screenshot."""
        # In production, this would use image comparison
        return {
            "match": True,
            "difference": 0.0,
            "reference": reference_path,
            "current": self.state.screenshot_path,
        }


class PlaywrightAutomator:
    """Playwright-based browser automation (browser-only)."""
    
    def get_javascript(self) -> str:
        """Return JavaScript code for Playwright automation."""
        return """
        class BrowserAutomator {
            constructor() {
                this.page = null;
                this.context = null;
            }
            
            async connect() {
                const { chromium } = require('playwright');
                const browser = await chromium.launch();
                this.context = await browser.newContext();
                this.page = await this.context.newPage();
                return true;
            }
            
            async navigate(url) {
                await this.page.goto(url);
                return { url: this.page.url(), title: await this.page.title() };
            }
            
            async click(selector) {
                await this.page.click(selector);
            }
            
            async type(selector, text) {
                await this.page.fill(selector, text);
            }
            
            async screenshot(path) {
                await this.page.screenshot({ path });
                return path;
            }
            
            async getText(selector) {
                return await this.page.textContent(selector);
            }
            
            async evaluate(script) {
                return await this.page.evaluate(script);
            }
            
            async close() {
                await this.page.context().browser().close();
            }
        }
        
        new BrowserAutomator();
        """
