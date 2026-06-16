# Anvil Browser Extension

Browser extension for Chrome and Firefox that integrates Anvil AI coding assistant directly into your browser.

## Features

- 🎯 **Quick Access** - Click the extension icon to ask Anvil anything
- 💡 **Code Analysis** - Right-click on code to explain, optimize, or review
- 🔍 **Codebase Understanding** - Anvil understands your code context
- ⚡ **Quick Actions** - One-click actions for common tasks
- 🌐 **Works Everywhere** - Injects buttons into code blocks on any website

## Installation

### Chrome

1. Download or clone this repository
2. Open Chrome and go to `chrome://extensions/`
3. Enable "Developer mode" (top right)
4. Click "Load unpacked"
5. Select the `extension` folder

### Firefox

1. Download or clone this repository
2. Open Firefox and go to `about:debugging#/runtime/this-firefox`
3. Click "Load Temporary Add-on"
4. Select the `manifest.json` file in the `extension` folder

## Usage

### Popup

1. Click the Anvil icon in your browser toolbar
2. Type your question or task
3. Press Enter or click "Ask Anvil"
4. View the response

### Context Menu

1. Select code on any webpage
2. Right-click
3. Choose an action:
   - **Explain Code** - Get a simple explanation
   - **Optimize Code** - Get optimization suggestions
   - **Review Code** - Get a code review
   - **Fix Issues** - Get fixes for issues

### Code Block Buttons

On websites with code blocks (GitHub, Stack Overflow, etc.), Anvil automatically injects "Ask Anvil" buttons. Click to analyze the code.

## Requirements

- Anvil server running on `http://localhost:8000`
- Run `anvil serve` to start the server

## Development

### Project Structure

```
extension/
├── manifest.json       # Extension manifest
├── popup.html         # Popup HTML
├── popup.css          # Popup styles
├── popup.js           # Popup logic
├── background.js      # Background service worker
├── content.js         # Content script
├── content.css        # Content script styles
└── icons/             # Extension icons
```

### Local Development

1. Make changes to the extension files
2. Go to `chrome://extensions/` or `about:debugging`
3. Click "Reload" to apply changes

### Building for Production

```bash
# Create a zip file for distribution
zip -r anvil-extension.zip extension/
```

## API Endpoints

The extension communicates with the Anvil server:

- `GET /health` - Health check
- `POST /api/run` - Execute a task

## Permissions

- `storage` - Store settings and preferences
- `activeTab` - Access current tab
- `scripting` - Inject scripts into pages
- `contextMenus` - Add right-click menu items

## Privacy

- All communication happens locally with your Anvil server
- No data is sent to external servers
- Your code and queries stay on your machine

## License

MIT © FableForge
