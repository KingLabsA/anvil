# Anvil VS Code Extension

AI-powered coding assistant with verification and error recovery, integrated directly into VS Code.

## Features

### 🎯 Core Commands

- **Run Task** - Execute any coding task with Anvil's verify-loop
- **Verify Code** - Check syntax, tests, lint, and types
- **Explain Code** - Get AI-powered explanations of code
- **Refactor Code** - AI-assisted code refactoring
- **Fix Errors** - Automatically fix linting and type errors
- **Generate Tests** - Generate comprehensive test suites

### 🖥️ User Interface

- **Status Bar** - Quick access to Anvil commands
- **Sidebar** - Task list and history
- **Context Menu** - Right-click commands in editor
- **Output Channel** - Detailed logs and results

### ⚙️ Configuration

Customize Anvil in VS Code settings:

- **Server URL** - Connect to local or remote Anvil server
- **Model** - Choose between local, GPT-4o, or Claude
- **Auto Verify** - Automatically verify after changes
- **Max Iterations** - Control task execution depth
- **Theme** - Dark or light mode

## Installation

### From VS Code Marketplace

1. Open VS Code
2. Go to Extensions (Ctrl+Shift+X)
3. Search for "Anvil"
4. Click Install

### From VSIX

```bash
# Build the extension
cd integrations/vscode-extension
npm install
npm run compile
vsce package

# Install the VSIX
code --install-extension anvil-vscode-0.3.0.vsix
```

## Usage

### Running Tasks

1. Press `Ctrl+Shift+P` (or `Cmd+Shift+P` on Mac)
2. Type "Anvil: Run Task"
3. Enter your task description
4. Watch Anvil work in the output channel

### Verifying Code

1. Open a file
2. Right-click and select "Anvil: Verify Code"
3. Or use the verify icon in the editor title bar
4. See results in the output channel

### Explaining Code

1. Select code (or use entire file)
2. Right-click and select "Anvil: Explain Code"
3. View explanation in a new webview panel

### Refactoring Code

1. Open a file
2. Right-click and select "Anvil: Refactor Code"
3. Describe what you want to refactor
4. Anvil applies the changes automatically

### Fixing Errors

1. Open a file with errors
2. Right-click and select "Anvil: Fix Errors"
3. Anvil analyzes and fixes all errors
4. Changes are applied automatically

### Generating Tests

1. Open a source file
2. Right-click and select "Anvil: Generate Tests"
3. Anvil generates comprehensive tests
4. Test file opens in a new editor tab

## Keyboard Shortcuts

You can add custom keyboard shortcuts in VS Code:

```json
{
  "key": "ctrl+shift+a",
  "command": "anvil.runTask"
},
{
  "key": "ctrl+shift+v",
  "command": "anvil.verifyCode"
},
{
  "key": "ctrl+shift+e",
  "command": "anvil.explainCode"
}
```

## Configuration

### Settings

Open VS Code settings and search for "anvil":

```json
{
  "anvil.serverUrl": "http://localhost:8000",
  "anvil.model": "local",
  "anvil.autoVerify": true,
  "anvil.maxIterations": 20,
  "anvil.theme": "dark"
}
```

### Server Connection

Make sure the Anvil server is running:

```bash
anvil serve --port 8000
```

The extension will connect to `http://localhost:8000` by default.

## API Endpoints

The extension communicates with the Anvil server via these endpoints:

- `POST /run` - Execute a task
- `POST /verify` - Verify code
- `POST /explain` - Explain code
- `POST /refactor` - Refactor code
- `POST /fix` - Fix errors
- `POST /generate-tests` - Generate tests
- `GET /sessions` - List task history

## Development

### Building

```bash
cd integrations/vscode-extension
npm install
npm run compile
```

### Watching

```bash
npm run watch
```

### Packaging

```bash
npm install -g @vscode/vsce
vsce package
```

### Testing

```bash
npm test
```

## Troubleshooting

### Connection Issues

If the extension can't connect to the server:

1. Check that Anvil server is running: `anvil serve`
2. Verify the server URL in settings
3. Check the output channel for error messages
4. Try restarting VS Code

### Commands Not Working

If commands don't appear:

1. Reload VS Code window (Ctrl+Shift+P → "Developer: Reload Window")
2. Check that the extension is activated
3. Look for errors in the Extension Host output

### Slow Performance

If the extension is slow:

1. Reduce `maxIterations` in settings
2. Use a faster model (local vs API)
3. Check server logs for bottlenecks

## Contributing

Contributions are welcome! Please see the main [Anvil repository](https://github.com/KingLabsA/anvil) for contribution guidelines.

## License

MIT © [FableForge](https://github.com/KingLabsA)

## Support

- GitHub Issues: https://github.com/KingLabsA/anvil/issues
- Documentation: https://github.com/KingLabsA/anvil#readme
- Discord: [Coming soon]
