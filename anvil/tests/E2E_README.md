# Anvil E2E Tests

End-to-end tests for the Anvil Web UI using Playwright.

## Overview

These tests verify the complete user journey through the Anvil web interface, including:
- Page loading and initialization
- Menu bar interactions
- Settings panel functionality
- Chat panel interactions
- Editor interactions
- Keyboard shortcuts
- Git diff viewer
- Responsive design

## Prerequisites

1. Install Playwright:
```bash
pip install playwright pytest-playwright
playwright install
```

2. Ensure the Anvil server can be started:
```bash
pip install fableforge-anvil-agent[web]
```

## Running Tests

### Quick Start

Run all E2E tests:
```bash
./scripts/run-e2e-tests.sh
```

### Manual Testing

1. Start the Anvil server:
```bash
cd anvil
python3 -m anvil.web.server
```

2. In another terminal, run the tests:
```bash
cd anvil
pytest tests/test_e2e.py -v
```

### Run Specific Test Suites

```bash
# Test homepage loading
pytest tests/test_e2e.py::TestWebUILoading -v

# Test menu interactions
pytest tests/test_e2e.py::TestMenuInteractions -v

# Test settings panel
pytest tests/test_e2e.py::TestSettingsPanel -v

# Test chat interactions
pytest tests/test_e2e.py::TestChatInteraction -v

# Test editor interactions
pytest tests/test_e2e.py::TestEditorInteraction -v

# Test keyboard shortcuts
pytest tests/test_e2e.py::TestKeyboardShortcuts -v

# Test Git diff viewer
pytest tests/test_e2e.py::TestGitDiffViewer -v

# Test responsive design
pytest tests/test_e2e.py::TestResponsiveDesign -v
```

### Run with Browser Visible

To see the browser during testing, modify `tests/conftest_playwright.py`:

```python
@pytest.fixture(scope="session")
def browser_type_launch_args():
    return {
        "headless": False,  # Change to False
        "slow_mo": 500,     # Increase for slower actions
    }
```

## Test Coverage

### TestWebUILoading
- ✅ Homepage loads successfully
- ✅ Monaco editor loads
- ✅ Menu bar is visible
- ✅ Sidebar is visible
- ✅ Chat panel is visible
- ✅ Terminal is visible
- ✅ Status bar is visible

### TestMenuInteractions
- ✅ File menu opens
- ✅ Edit menu opens
- ✅ View menu opens
- ✅ Tools menu opens
- ✅ Help menu opens

### TestSettingsPanel
- ✅ Settings panel opens
- ✅ Settings tabs switch correctly

### TestChatInteraction
- ✅ Chat input works
- ✅ Send message button works

### TestEditorInteraction
- ✅ File selection works
- ✅ Tab creation works

### TestKeyboardShortcuts
- ✅ Ctrl+S for save
- ✅ Ctrl+B for toggle sidebar
- ✅ Ctrl+, for settings

### TestGitDiffViewer
- ✅ Git panel opens
- ✅ Diff viewer can be closed

### TestResponsiveDesign
- ✅ Mobile viewport (375x667)
- ✅ Tablet viewport (768x1024)

## Configuration

### Browser Configuration

Edit `tests/conftest_playwright.py` to configure:
- Browser type (chromium, firefox, webkit)
- Viewport size
- Headless mode
- Slow motion

### Server Configuration

Edit `scripts/run-e2e-tests.sh` to configure:
- Server port
- Startup wait time
- Server command

## Debugging Failed Tests

### View Test Output

```bash
pytest tests/test_e2e.py -v --tb=short
```

### Take Screenshots on Failure

Add to test:
```python
def test_something(page: Page):
    page.goto("http://localhost:8000")
    # ... test code ...
    page.screenshot(path="screenshot.png")
```

### Record Video

Add to `conftest_playwright.py`:
```python
@pytest.fixture(scope="session")
def browser_context_args():
    return {
        "record_video_dir": "test-videos/",
        "record_video_size": {"width": 1920, "height": 1080},
    }
```

### Trace Recording

Add to test:
```python
def test_something(page: Page):
    page.context.tracing.start(screenshots=True, snapshots=True, sources=True)
    page.goto("http://localhost:8000")
    # ... test code ...
    page.context.tracing.stop(path="trace.zip")
```

View trace:
```bash
playwright show-trace trace.zip
```

## Common Issues

### Server Not Starting

**Problem**: Server fails to start
**Solution**: 
- Check if port 8000 is already in use
- Verify all dependencies are installed
- Check server logs for errors

### Tests Timeout

**Problem**: Tests timeout waiting for elements
**Solution**:
- Increase timeout in test: `expect(element).to_be_visible(timeout=10000)`
- Check if server is responding
- Verify element selectors are correct

### Element Not Found

**Problem**: Element selector doesn't match
**Solution**:
- Use Playwright Inspector: `page.pause()`
- Check element attributes in browser DevTools
- Update selector to match actual element

### Browser Not Installed

**Problem**: Playwright browsers not installed
**Solution**:
```bash
playwright install chromium
playwright install firefox
playwright install webkit
```

## CI/CD Integration

### GitHub Actions

Add to `.github/workflows/e2e.yml`:

```yaml
name: E2E Tests

on: [push, pull_request]

jobs:
  e2e:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install -e .[web]
          pip install playwright pytest-playwright
          playwright install --with-deps chromium
      
      - name: Run E2E tests
        run: |
          python3 -m anvil.web.server &
          sleep 5
          pytest tests/test_e2e.py -v
```

## Best Practices

1. **Use Data Test IDs**: Add `data-testid` attributes to elements for reliable selectors
2. **Wait for Network Idle**: Use `page.wait_for_load_state("networkidle")` for async operations
3. **Avoid Hard Waits**: Use `expect().to_be_visible()` instead of `time.sleep()`
4. **Test User Journeys**: Write tests that follow actual user workflows
5. **Keep Tests Independent**: Each test should be able to run in isolation
6. **Use Page Objects**: Create page object classes for complex pages
7. **Screenshot on Failure**: Automatically capture screenshots when tests fail

## Future Enhancements

- [ ] Add visual regression tests
- [ ] Add performance tests
- [ ] Add accessibility tests
- [ ] Add cross-browser testing (Firefox, WebKit)
- [ ] Add mobile device emulation
- [ ] Add network condition testing
- [ ] Add authentication flow tests
- [ ] Add real-time collaboration tests

## Resources

- [Playwright Documentation](https://playwright.dev/python/)
- [Playwright Python API](https://playwright.dev/python/docs/api/class-playwright)
- [Pytest Documentation](https://docs.pytest.org/)
- [Playwright Best Practices](https://playwright.dev/python/docs/best-practices)

## Support

For issues or questions:
- GitHub Issues: https://github.com/KingLabsA/anvil/issues
- Documentation: https://github.com/KingLabsA/anvil#readme
