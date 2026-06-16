"""Onboarding system for new Anvil users."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Optional
from pathlib import Path


@dataclass
class OnboardingStep:
    """A single onboarding step."""
    id: str
    title: str
    description: str
    action: str  # "click", "type", "watch", "complete"
    target: Optional[str] = None  # CSS selector or element ID
    content: Optional[str] = None  # Content to display or type
    completed: bool = False
    skippable: bool = True


@dataclass
class OnboardingTour:
    """A complete onboarding tour."""
    id: str
    name: str
    description: str
    steps: list[OnboardingStep] = field(default_factory=list)
    current_step: int = 0
    
    def next_step(self) -> Optional[OnboardingStep]:
        """Get the next step in the tour."""
        if self.current_step < len(self.steps):
            step = self.steps[self.current_step]
            self.current_step += 1
            return step
        return None
    
    def previous_step(self) -> Optional[OnboardingStep]:
        """Get the previous step in the tour."""
        if self.current_step > 1:
            self.current_step -= 2  # Go back 2 because next_step will increment
            return self.next_step()
        elif self.current_step == 1:
            self.current_step = 0
            return self.steps[0]
        return None
    
    def skip_step(self) -> Optional[OnboardingStep]:
        """Skip the current step."""
        if self.current_step < len(self.steps):
            self.steps[self.current_step].completed = True
            self.current_step += 1
            return self.next_step()
        return None
    
    def complete_step(self) -> None:
        """Mark the current step as completed."""
        if self.current_step > 0:
            self.steps[self.current_step - 1].completed = True
    
    def is_complete(self) -> bool:
        """Check if the tour is complete."""
        return self.current_step >= len(self.steps)
    
    def reset(self) -> None:
        """Reset the tour to the beginning."""
        self.current_step = 0
        for step in self.steps:
            step.completed = False


class OnboardingManager:
    """Manages onboarding tours and user progress."""
    
    def __init__(self, progress_file: Path | None = None):
        """Initialize onboarding manager.
        
        Args:
            progress_file: Path to store user progress (default: ~/.anvil/onboarding.json)
        """
        self.progress_file = progress_file or (Path.home() / ".anvil" / "onboarding.json")
        self.tours: dict[str, OnboardingTour] = {}
        self.user_progress: dict[str, Any] = {}
        self._load_progress()
        self._create_default_tours()
    
    def _load_progress(self) -> None:
        """Load user progress from file."""
        if self.progress_file.exists():
            try:
                self.user_progress = json.loads(self.progress_file.read_text())
            except Exception:
                self.user_progress = {}
    
    def _save_progress(self) -> None:
        """Save user progress to file."""
        self.progress_file.parent.mkdir(parents=True, exist_ok=True)
        self.progress_file.write_text(json.dumps(self.user_progress, indent=2))
    
    def _create_default_tours(self) -> None:
        """Create default onboarding tours."""
        # Quick Start Tour
        quick_start = OnboardingTour(
            id="quick_start",
            name="Quick Start",
            description="Learn the basics of Anvil in 5 minutes",
        )
        
        quick_start.steps = [
            OnboardingStep(
                id="welcome",
                title="Welcome to Anvil!",
                description="Anvil is your AI-powered coding assistant. Let's take a quick tour!",
                action="watch",
                skippable=False,
            ),
            OnboardingStep(
                id="editor",
                title="Code Editor",
                description="This is the Monaco editor - the same editor used in VS Code. You can write and edit code here.",
                action="click",
                target=".monaco-editor",
            ),
            OnboardingStep(
                id="file_tree",
                title="File Explorer",
                description="Browse and select files from your project here.",
                action="click",
                target=".file-tree",
            ),
            OnboardingStep(
                id="chat",
                title="AI Assistant",
                description="Chat with Anvil to get help, explanations, and code suggestions.",
                action="click",
                target=".chat-panel",
            ),
            OnboardingStep(
                id="terminal",
                title="Terminal",
                description="View command output, verification results, and task progress here.",
                action="click",
                target=".terminal",
            ),
            OnboardingStep(
                id="menu",
                title="Menu Bar",
                description="Access all Anvil features from the menu bar. Try clicking 'Tools' > 'Run Task'.",
                action="click",
                target=".menu-bar",
            ),
            OnboardingStep(
                id="complete",
                title="You're All Set!",
                description="You're ready to start coding with Anvil. Remember: you can always ask Anvil for help!",
                action="complete",
                skippable=False,
            ),
        ]
        
        self.tours["quick_start"] = quick_start
        
        # Features Tour
        features = OnboardingTour(
            id="features",
            name="Features Tour",
            description="Discover all the powerful features of Anvil",
        )
        
        features.steps = [
            OnboardingStep(
                id="run_task",
                title="Run Tasks",
                description="Ask Anvil to complete coding tasks. Try: 'Create a function that calculates fibonacci numbers'",
                action="watch",
            ),
            OnboardingStep(
                id="verify",
                title="Verify Code",
                description="Anvil automatically verifies your code for syntax, lint, and type errors.",
                action="watch",
            ),
            OnboardingStep(
                id="explain",
                title="Explain Code",
                description="Select code and ask Anvil to explain what it does.",
                action="watch",
            ),
            OnboardingStep(
                id="refactor",
                title="Refactor Code",
                description="Ask Anvil to refactor your code with suggestions like 'Extract this into a function'.",
                action="watch",
            ),
            OnboardingStep(
                id="fix_errors",
                title="Fix Errors",
                description="Anvil can automatically fix errors in your code.",
                action="watch",
            ),
            OnboardingStep(
                id="generate_tests",
                title="Generate Tests",
                description="Ask Anvil to generate comprehensive tests for your code.",
                action="watch",
            ),
            OnboardingStep(
                id="settings",
                title="Settings",
                description="Customize Anvil in Settings. Choose your preferred model, theme, and more.",
                action="click",
                target="button[onclick='showSettings()']",
            ),
            OnboardingStep(
                id="features_complete",
                title="Explore More!",
                description="You've seen the main features. Explore the menu bar and try different commands!",
                action="complete",
            ),
        ]
        
        self.tours["features"] = features
        
        # Keyboard Shortcuts Tour
        shortcuts = OnboardingTour(
            id="shortcuts",
            name="Keyboard Shortcuts",
            description="Learn keyboard shortcuts to work faster",
        )
        
        shortcuts.steps = [
            OnboardingStep(
                id="shortcuts_intro",
                title="Keyboard Shortcuts",
                description="Anvil has many keyboard shortcuts to help you work faster. Let's learn the most important ones!",
                action="watch",
            ),
            OnboardingStep(
                id="save",
                title="Save File",
                description="Press Ctrl+S (Cmd+S on Mac) to save the current file.",
                action="watch",
                content="Ctrl+S",
            ),
            OnboardingStep(
                id="toggle_sidebar",
                title="Toggle Sidebar",
                description="Press Ctrl+B to show/hide the file explorer sidebar.",
                action="watch",
                content="Ctrl+B",
            ),
            OnboardingStep(
                id="toggle_terminal",
                title="Toggle Terminal",
                description="Press Ctrl+` to show/hide the terminal.",
                action="watch",
                content="Ctrl+`",
            ),
            OnboardingStep(
                id="settings_shortcut",
                title="Open Settings",
                description="Press Ctrl+, to open the settings panel.",
                action="watch",
                content="Ctrl+,",
            ),
            OnboardingStep(
                id="run_task_shortcut",
                title="Run Task",
                description="Press Ctrl+Enter to run the current task.",
                action="watch",
                content="Ctrl+Enter",
            ),
            OnboardingStep(
                id="shortcuts_complete",
                title="Shortcuts Mastered!",
                description="Great! You know the essential shortcuts. Check Help > Keyboard Shortcuts for the full list.",
                action="complete",
            ),
        ]
        
        self.tours["shortcuts"] = shortcuts
    
    def get_tour(self, tour_id: str) -> Optional[OnboardingTour]:
        """Get a tour by ID."""
        return self.tours.get(tour_id)
    
    def list_tours(self) -> list[OnboardingTour]:
        """List all available tours."""
        return list(self.tours.values())
    
    def start_tour(self, tour_id: str) -> Optional[OnboardingTour]:
        """Start a tour."""
        tour = self.tours.get(tour_id)
        if tour:
            tour.reset()
            return tour
        return None
    
    def complete_tour(self, tour_id: str) -> bool:
        """Mark a tour as completed."""
        if tour_id in self.tours:
            self.user_progress[tour_id] = {
                "completed": True,
                "completed_at": str(__import__('datetime').datetime.now()),
            }
            self._save_progress()
            return True
        return False
    
    def is_tour_completed(self, tour_id: str) -> bool:
        """Check if a tour is completed."""
        return self.user_progress.get(tour_id, {}).get("completed", False)
    
    def get_completed_tours(self) -> list[str]:
        """Get list of completed tour IDs."""
        return [tour_id for tour_id, progress in self.user_progress.items() if progress.get("completed")]
    
    def reset_all_progress(self) -> None:
        """Reset all onboarding progress."""
        self.user_progress = {}
        self._save_progress()
        for tour in self.tours.values():
            tour.reset()
    
    def should_show_onboarding(self) -> bool:
        """Check if onboarding should be shown to the user."""
        # Show onboarding if no tours are completed
        return len(self.get_completed_tours()) == 0
    
    def get_recommended_tour(self) -> Optional[OnboardingTour]:
        """Get the recommended tour for the user."""
        # Recommend Quick Start if no tours completed
        if not self.get_completed_tours():
            return self.tours.get("quick_start")
        
        # Recommend Features if Quick Start completed
        if self.is_tour_completed("quick_start") and not self.is_tour_completed("features"):
            return self.tours.get("features")
        
        # Recommend Shortcuts if Features completed
        if self.is_tour_completed("features") and not self.is_tour_completed("shortcuts"):
            return self.tours.get("shortcuts")
        
        return None


# Global instance
onboarding_manager = OnboardingManager()
