# Anvil AI - VS Code Extension

AI coding agent with self-verification, multi-agent orchestration, and custom model training.

## Features

- **Inline Actions** - Right-click context menu for Explain, Refactor, Fix, Generate Tests, Verify
- **Chat Panel** - Sidebar WebView panel for interactive AI conversations
- **Self-Verification** - Automatic code verification after changes
- **Multi-Model Support** - Local, OpenAI, Anthropic, Gemini, DeepSeek
- **Theme Sync** - Matches VS Code light/dark theme automatically
- **Status Bar** - Real-time connection status and model indicator
- **Keyboard Shortcuts** - Quick access to common actions

## Requirements

- VS Code 1.85.0+
- Anvil server running locally or remotely

## Quick Start

1. Install the extension
2. Start the Anvil server: `Anvil: Start Server` (or run `anvil serve` manually)
3. Open the panel: `Anvil: Open Panel` or `Ctrl+Shift+A` / `Cmd+Shift+A`
4. Select code and use actions from the context menu or toolbar

## Commands

| Command | Shortcut | Description |
|---------|----------|-------------|
| `Anvil: Start Server` | - | Start the Anvil server |
| `Anvil: Open Panel` | `Ctrl+Shift+A` | Open the Anvil sidebar |
| `Anvil: Ask Question` | `Ctrl+Shift+I` | Ask a question |
| `Anvil: Explain Code` | - | Explain selected code |
| `Anvil: Refactor Code` | - | Refactor selected code |
| `Anvil: Fix Errors` | - | Fix errors in selected code |
| `Anvil: Generate Tests` | - | Generate tests for selected code |
| `Anvil: Verify Code` | `Ctrl+Shift+V` | Verify selected code |

## Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `anvil.serverUrl` | `http://localhost:8000` | Anvil server URL |
| `anvil.model` | `local` | Default model (local, openai, anthropic, gemini, deepseek) |
| `anvil.autoVerify` | `true` | Auto-verify code after changes |
| `anvil.theme` | `auto` | Panel theme (auto, light, dark) |
| `anvil.maxTokens` | `4096` | Maximum tokens per request |
| `anvil.temperature` | `0.7` | Model temperature |
| `anvil.autoStart` | `false` | Auto-start server on activation |

## Development

```bash
npm install
npm run compile
```

Press F5 in VS Code to launch the extension in a new window.

## Build

```bash
npm run package
```

This produces a `.vsix` file for distribution.
