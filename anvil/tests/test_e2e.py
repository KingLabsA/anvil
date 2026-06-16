"""E2E tests for Anvil Web UI using Playwright."""

import pytest
from playwright.sync_api import Page, expect
import time


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args):
    """Configure browser context."""
    return {
        **browser_context_args,
        "viewport": {"width": 1920, "height": 1080},
    }


class TestWebUILoading:
    """Test web UI loading and basic functionality."""
    
    def test_homepage_loads(self, page: Page):
        """Test that the homepage loads successfully."""
        page.goto("http://localhost:8000")
        
        # Check that the page title contains "Anvil"
        expect(page).to_have_title(/Anvil/)
        
        # Check that the logo is visible
        logo = page.locator(".logo")
        expect(logo).to_be_visible()
        expect(logo).to_contain_text("Anvil")
    
    def test_editor_loads(self, page: Page):
        """Test that the Monaco editor loads."""
        page.goto("http://localhost:8000")
        
        # Wait for Monaco editor to load
        page.wait_for_selector(".monaco-editor", timeout=10000)
        
        # Check that editor is visible
        editor = page.locator(".monaco-editor")
        expect(editor).to_be_visible()
    
    def test_menu_bar_visible(self, page: Page):
        """Test that the menu bar is visible."""
        page.goto("http://localhost:8000")
        
        # Check menu items
        menu_bar = page.locator(".menu-bar")
        expect(menu_bar).to_be_visible()
        
        # Check individual menu items
        for menu in ["File", "Edit", "View", "Tools", "Help"]:
            menu_item = page.locator(f".menu-item:has-text('{menu}')")
            expect(menu_item).to_be_visible()
    
    def test_sidebar_visible(self, page: Page):
        """Test that the sidebar is visible."""
        page.goto("http://localhost:8000")
        
        sidebar = page.locator(".sidebar")
        expect(sidebar).to_be_visible()
        
        # Check file tree
        file_tree = page.locator(".file-tree")
        expect(file_tree).to_be_visible()
    
    def test_chat_panel_visible(self, page: Page):
        """Test that the chat panel is visible."""
        page.goto("http://localhost:8000")
        
        chat_panel = page.locator(".chat-panel")
        expect(chat_panel).to_be_visible()
        
        # Check chat input
        chat_input = page.locator(".chat-input")
        expect(chat_input).to_be_visible()
    
    def test_terminal_visible(self, page: Page):
        """Test that the terminal is visible."""
        page.goto("http://localhost:8000")
        
        terminal = page.locator(".terminal")
        expect(terminal).to_be_visible()
    
    def test_status_bar_visible(self, page: Page):
        """Test that the status bar is visible."""
        page.goto("http://localhost:8000")
        
        status_bar = page.locator(".status-bar")
        expect(status_bar).to_be_visible()


class TestMenuInteractions:
    """Test menu bar interactions."""
    
    def test_file_menu_opens(self, page: Page):
        """Test that File menu opens."""
        page.goto("http://localhost:8000")
        
        # Click File menu
        file_menu = page.locator(".menu-item:has-text('File')")
        file_menu.click()
        
        # Check dropdown is visible
        dropdown = page.locator("#file-menu")
        expect(dropdown).to_be_visible()
        
        # Check menu items
        expect(dropdown).to_contain_text("New File")
        expect(dropdown).to_contain_text("Open File")
        expect(dropdown).to_contain_text("Save")
    
    def test_edit_menu_opens(self, page: Page):
        """Test that Edit menu opens."""
        page.goto("http://localhost:8000")
        
        # Click Edit menu
        edit_menu = page.locator(".menu-item:has-text('Edit')")
        edit_menu.click()
        
        # Check dropdown is visible
        dropdown = page.locator("#edit-menu")
        expect(dropdown).to_be_visible()
        
        # Check menu items
        expect(dropdown).to_contain_text("Undo")
        expect(dropdown).to_contain_text("Redo")
        expect(dropdown).to_contain_text("Find")
    
    def test_view_menu_opens(self, page: Page):
        """Test that View menu opens."""
        page.goto("http://localhost:8000")
        
        # Click View menu
        view_menu = page.locator(".menu-item:has-text('View')")
        view_menu.click()
        
        # Check dropdown is visible
        dropdown = page.locator("#view-menu")
        expect(dropdown).to_be_visible()
        
        # Check menu items
        expect(dropdown).to_contain_text("Toggle Sidebar")
        expect(dropdown).to_contain_text("Toggle Terminal")
    
    def test_tools_menu_opens(self, page: Page):
        """Test that Tools menu opens."""
        page.goto("http://localhost:8000")
        
        # Click Tools menu
        tools_menu = page.locator(".menu-item:has-text('Tools')")
        tools_menu.click()
        
        # Check dropdown is visible
        dropdown = page.locator("#tools-menu")
        expect(dropdown).to_be_visible()
        
        # Check menu items
        expect(dropdown).to_contain_text("Run Task")
        expect(dropdown).to_contain_text("Verify Code")
    
    def test_help_menu_opens(self, page: Page):
        """Test that Help menu opens."""
        page.goto("http://localhost:8000")
        
        # Click Help menu
        help_menu = page.locator(".menu-item:has-text('Help')")
        help_menu.click()
        
        # Check dropdown is visible
        dropdown = page.locator("#help-menu")
        expect(dropdown).to_be_visible()
        
        # Check menu items
        expect(dropdown).to_contain_text("Documentation")
        expect(dropdown).to_contain_text("About Anvil")


class TestSettingsPanel:
    """Test settings panel functionality."""
    
    def test_settings_opens(self, page: Page):
        """Test that settings panel opens."""
        page.goto("http://localhost:8000")
        
        # Click settings button
        settings_btn = page.locator("button[onclick='showSettings()']")
        settings_btn.click()
        
        # Check settings modal is visible
        settings_modal = page.locator("[style*='position: fixed']")
        expect(settings_modal).to_be_visible()
        
        # Check settings tabs
        expect(settings_modal).to_contain_text("General")
        expect(settings_modal).to_contain_text("Editor")
        expect(settings_modal).to_contain_text("Model")
    
    def test_settings_tabs_switch(self, page: Page):
        """Test that settings tabs switch correctly."""
        page.goto("http://localhost:8000")
        
        # Open settings
        settings_btn = page.locator("button[onclick='showSettings()']")
        settings_btn.click()
        
        # Click Editor tab
        editor_tab = page.locator("text=Editor")
        editor_tab.click()
        
        # Check Editor settings are visible
        expect(page.locator("#settings-content")).to_contain_text("Font Size")
        
        # Click Model tab
        model_tab = page.locator("text=Model")
        model_tab.click()
        
        # Check Model settings are visible
        expect(page.locator("#settings-content")).to_contain_text("Default Model")


class TestChatInteraction:
    """Test chat panel interactions."""
    
    def test_chat_input_works(self, page: Page):
        """Test that chat input works."""
        page.goto("http://localhost:8000")
        
        # Type in chat input
        chat_input = page.locator(".chat-input")
        chat_input.fill("Hello, Anvil!")
        
        # Check input has value
        expect(chat_input).to_have_value("Hello, Anvil!")
    
    def test_send_message_button(self, page: Page):
        """Test that send message button works."""
        page.goto("http://localhost:8000")
        
        # Type message
        chat_input = page.locator(".chat-input")
        chat_input.fill("Test message")
        
        # Click send button
        send_btn = page.locator("button:has-text('Send')")
        send_btn.click()
        
        # Check that message appears in chat
        messages = page.locator(".message")
        expect(messages).to_have_count(2)  # Initial greeting + user message


class TestEditorInteraction:
    """Test editor interactions."""
    
    def test_file_selection(self, page: Page):
        """Test that file selection works."""
        page.goto("http://localhost:8000")
        
        # Click on a file in the file tree
        file_item = page.locator(".file-item:has-text('utils.py')")
        file_item.click()
        
        # Check that file is selected
        expect(file_item).to_have_class(/active/)
    
    def test_tab_creation(self, page: Page):
        """Test that tabs are created when selecting files."""
        page.goto("http://localhost:8000")
        
        # Click on a file
        file_item = page.locator(".file-item:has-text('utils.py')")
        file_item.click()
        
        # Check that tab is created
        tabs = page.locator(".tab")
        expect(tabs).to_have_count(1)


class TestKeyboardShortcuts:
    """Test keyboard shortcuts."""
    
    def test_ctrl_s_save(self, page: Page):
        """Test Ctrl+S shortcut for save."""
        page.goto("http://localhost:8000")
        
        # Press Ctrl+S
        page.keyboard.press("Control+s")
        
        # Check terminal for save message
        terminal = page.locator(".terminal-content")
        expect(terminal).to_contain_text("saved", timeout=5000)
    
    def test_ctrl_b_toggle_sidebar(self, page: Page):
        """Test Ctrl+B shortcut for toggle sidebar."""
        page.goto("http://localhost:8000")
        
        # Check sidebar is visible
        sidebar = page.locator(".sidebar")
        expect(sidebar).to_be_visible()
        
        # Press Ctrl+B
        page.keyboard.press("Control+b")
        
        # Check sidebar is hidden
        expect(sidebar).to_be_hidden()
        
        # Press Ctrl+B again
        page.keyboard.press("Control+b")
        
        # Check sidebar is visible again
        expect(sidebar).to_be_visible()
    
    def test_ctrl_comma_settings(self, page: Page):
        """Test Ctrl+, shortcut for settings."""
        page.goto("http://localhost:8000")
        
        # Press Ctrl+,
        page.keyboard.press("Control+,")
        
        # Check settings modal is visible
        settings_modal = page.locator("[style*='position: fixed']")
        expect(settings_modal).to_be_visible()


class TestGitDiffViewer:
    """Test Git diff viewer."""
    
    def test_git_panel_opens(self, page: Page):
        """Test that Git panel opens."""
        page.goto("http://localhost:8000")
        
        # Click Git Panel from Tools menu
        tools_menu = page.locator(".menu-item:has-text('Tools')")
        tools_menu.click()
        
        git_panel_item = page.locator("text=Git Panel")
        git_panel_item.click()
        
        # Check diff viewer is visible
        diff_viewer = page.locator(".diff-viewer")
        expect(diff_viewer).to_be_visible()
    
    def test_diff_viewer_close(self, page: Page):
        """Test that diff viewer can be closed."""
        page.goto("http://localhost:8000")
        
        # Open Git panel
        tools_menu = page.locator(".menu-item:has-text('Tools')")
        tools_menu.click()
        git_panel_item = page.locator("text=Git Panel")
        git_panel_item.click()
        
        # Close diff viewer
        close_btn = page.locator(".diff-viewer button:has-text('Close')")
        close_btn.click()
        
        # Check diff viewer is hidden
        diff_viewer = page.locator(".diff-viewer")
        expect(diff_viewer).to_be_hidden()


class TestResponsiveDesign:
    """Test responsive design."""
    
    def test_mobile_viewport(self, page: Page):
        """Test that UI adapts to mobile viewport."""
        page.set_viewport_size({"width": 375, "height": 667})
        page.goto("http://localhost:8000")
        
        # Check that page loads
        expect(page).to_have_title(/Anvil/)
        
        # Check that main elements are still visible
        logo = page.locator(".logo")
        expect(logo).to_be_visible()
    
    def test_tablet_viewport(self, page: Page):
        """Test that UI adapts to tablet viewport."""
        page.set_viewport_size({"width": 768, "height": 1024})
        page.goto("http://localhost:8000")
        
        # Check that page loads
        expect(page).to_have_title(/Anvil/)
        
        # Check that main elements are visible
        editor = page.locator(".monaco-editor")
        expect(editor).to_be_visible()
