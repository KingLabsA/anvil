# Anvil JetBrains Plugin

AI-powered coding assistant with verification and error recovery, integrated directly into your JetBrains IDE.

## Features

### 🎯 Core Commands

- **Run Task** - Execute any coding task with Anvil's verify-loop (Ctrl+Shift+A)
- **Verify Code** - Check syntax, tests, lint, and types (Ctrl+Shift+V)
- **Explain Code** - Get AI-powered explanations of code
- **Refactor Code** - AI-assisted code refactoring
- **Fix Errors** - Automatically fix linting and type errors
- **Generate Tests** - Generate comprehensive test suites
- **Debug with Anvil** - Integrated debugging support

### 🖥️ User Interface

- **Tool Window** - Dedicated Anvil panel in your IDE
- **Context Menu** - Right-click commands in editor
- **Settings** - Configure server URL, model, and preferences
- **Notifications** - Task progress and results

### ⚙️ Configuration

Customize Anvil in Settings > Tools > Anvil:

- **Server URL** - Connect to local or remote Anvil server
- **Default Model** - Choose between local, GPT-4o, or Claude
- **Max Iterations** - Control task execution depth
- **Auto Verify** - Automatically verify after changes
- **Theme** - Dark or light mode

## Installation

### From JetBrains Marketplace

1. Open your JetBrains IDE (IntelliJ IDEA, PyCharm, WebStorm, etc.)
2. Go to Settings > Plugins
3. Search for "Anvil"
4. Click Install
5. Restart your IDE

### Manual Installation

1. Download the plugin ZIP from [Releases](https://github.com/KingLabsA/anvil/releases)
2. Open your JetBrains IDE
3. Go to Settings > Plugins
4. Click the gear icon > Install Plugin from Disk
5. Select the downloaded ZIP file
6. Restart your IDE

## Building from Source

### Prerequisites

- JDK 17 or higher
- IntelliJ IDEA (for development)

### Build Steps

```bash
cd integrations/jetbrains-plugin

# Build the plugin
./gradlew buildPlugin

# The plugin ZIP will be in build/distributions/
```

### Run in Development Mode

```bash
# Run the plugin in a sandbox IDE
./gradlew runIde
```

## Usage

### Running Tasks

1. Press `Ctrl+Shift+A` (or `Cmd+Shift+A` on Mac)
2. Enter your task description
3. Watch Anvil work in the tool window

### Verifying Code

1. Open a file
2. Right-click and select "Anvil > Verify Code"
3. Or press `Ctrl+Shift+V`
4. See results in the tool window

### Explaining Code

1. Select code (or use entire file)
2. Right-click and select "Anvil > Explain Code"
3. View explanation in the tool window

### Refactoring Code

1. Select code to refactor
2. Right-click and select "Anvil > Refactor Code"
3. Enter your refactoring suggestion
4. Anvil applies the changes automatically

### Fixing Errors

1. Open a file with errors
2. Right-click and select "Anvil > Fix Errors"
3. Anvil analyzes and fixes all errors
4. Changes are applied automatically

### Generating Tests

1. Select code or open a source file
2. Right-click and select "Anvil > Generate Tests"
3. Anvil generates comprehensive tests
4. Test file is created automatically

### Debugging

1. Select code to debug
2. Right-click and select "Anvil > Debug with Anvil"
3. Anvil sets up debugging session
4. Use IDE's debug controls to step through code

## Configuration

### Server Connection

Make sure the Anvil server is running:

```bash
anvil serve --port 8000
```

The plugin will connect to `http://localhost:8000` by default.

### Changing Settings

1. Go to Settings > Tools > Anvil
2. Configure your preferences
3. Click Apply

## Keyboard Shortcuts

| Action | Windows/Linux | macOS |
|--------|---------------|-------|
| Run Task | Ctrl+Shift+A | Cmd+Shift+A |
| Verify Code | Ctrl+Shift+V | Cmd+Shift+V |
| Explain Code | - | - |
| Refactor Code | - | - |
| Fix Errors | - | - |
| Generate Tests | - | - |
| Debug | - | - |

You can customize these shortcuts in Settings > Keymap > Search for "Anvil"

## Troubleshooting

### Connection Issues

If the plugin can't connect to the server:

1. Check that Anvil server is running: `anvil serve`
2. Verify the server URL in Settings > Tools > Anvil
3. Check the IDE's Event Log for error messages
4. Try restarting your IDE

### Commands Not Working

If commands don't appear:

1. Reload the window (File > Invalidate Caches / Restart)
2. Check that the plugin is enabled in Settings > Plugins
3. Look for errors in the IDE's log file

### Slow Performance

If the plugin is slow:

1. Reduce `Max Iterations` in settings
2. Use a faster model (local vs API)
3. Check server logs for bottlenecks

## Development

### Project Structure

```
jetbrains-plugin/
├── src/main/
│   ├── kotlin/
│   │   └── com/fableforge/anvil/
│   │       ├── actions/          # Action implementations
│   │       ├── services/         # Service classes
│   │       ├── settings/         # Settings UI
│   │       └── toolwindow/       # Tool window UI
│   └── resources/
│       └── META-INF/
│           └── plugin.xml        # Plugin configuration
├── build.gradle.kts              # Build configuration
└── README.md                     # This file
```

### Building

```bash
# Build the plugin
./gradlew buildPlugin

# Run tests
./gradlew test

# Run in development IDE
./gradlew runIde

# Clean build
./gradlew clean
```

### Publishing

```bash
# Set your JetBrains Marketplace token
export PUBLISH_TOKEN=your_token_here

# Publish the plugin
./gradlew publishPlugin
```

## API Endpoints

The plugin communicates with the Anvil server via these endpoints:

- `POST /api/run` - Execute a task
- `POST /api/verify` - Verify code
- `POST /api/explain` - Explain code
- `POST /api/refactor` - Refactor code
- `POST /api/fix` - Fix errors
- `POST /api/generate-tests` - Generate tests

## Supported IDEs

- IntelliJ IDEA (Community & Ultimate)
- PyCharm (Community & Professional)
- WebStorm
- PhpStorm
- RubyMine
- GoLand
- CLion
- Rider
- Android Studio

## Contributing

Contributions are welcome! Please see the main [Anvil repository](https://github.com/KingLabsA/anvil) for contribution guidelines.

## License

MIT © [FableForge](https://github.com/KingLabsA)

## Support

- GitHub Issues: https://github.com/KingLabsA/anvil/issues
- Documentation: https://github.com/KingLabsA/anvil#readme
- Discord: [Coming soon]

## Credits

Built with:
- [IntelliJ Platform SDK](https://plugins.jetbrains.com/docs/intellij/)
- [Kotlin](https://kotlinlang.org/)
- [Anvil API](https://github.com/KingLabsA/anvil)
