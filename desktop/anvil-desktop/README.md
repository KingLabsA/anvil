# Anvil Desktop

Native desktop application for Anvil, the self-verified coding agent.

## Features

- 🖥️ Native desktop experience with Anvil web UI
- 🚀 Fast, lightweight Tauri-based application
- 🔒 Secure sandboxed environment
- 🎨 Beautiful gradient loading screen
- 🔄 Automatic server connection detection

## Prerequisites

1. **Anvil CLI** must be installed:
   ```bash
   pip install fableforge-anvil-agent[web]
   ```

2. **Rust** (for development):
   ```bash
   curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
   ```

## Development

### Start the Anvil server

In one terminal:
```bash
anvil serve --port 8000
```

### Start the desktop app in dev mode

In another terminal:
```bash
cd desktop/anvil-desktop
npm run tauri dev
```

## Building

### Build for your platform

```bash
cd desktop/anvil-desktop
npm run tauri build
```

The built application will be in `src-tauri/target/release/bundle/`:
- **macOS**: `macos/Anvil Desktop.app`
- **Windows**: `msi/Anvil Desktop_0.3.0_x64_en-US.msi`
- **Linux**: `deb/anvil-desktop_0.3.0_amd64.deb` or `appimage/anvil-desktop_0.3.0_amd64.AppImage`

## Usage

1. Launch Anvil Desktop
2. The app will automatically start the Anvil web server
3. Wait for the connection (usually takes 2-5 seconds)
4. Start coding with Anvil!

## Architecture

- **Frontend**: HTML/CSS/JavaScript loading screen
- **Backend**: Tauri (Rust) for native window management
- **Integration**: Connects to Anvil web server at `http://localhost:8000`

## Configuration

Edit `src-tauri/tauri.conf.json` to customize:
- Window size and title
- App identifier
- Bundle settings
- Security policies

## Troubleshooting

### "Failed to connect to Anvil server"

Make sure the Anvil server is running:
```bash
anvil serve --port 8000
```

### Port already in use

Change the port in both commands:
```bash
anvil serve --port 8001
# Update src/index.html to use port 8001
```

## License

MIT

## Links

- [Anvil GitHub](https://github.com/KingLabsA/anvil)
- [Anvil Documentation](https://github.com/KingLabsA/anvil#readme)
- [Tauri Documentation](https://tauri.app/)
