# Anvil Mobile App

A mobile coding assistant with voice, camera, and terminal access.

## Features

- 🎤 **Voice Input** - Speak your coding tasks
- 📷 **Camera** - Capture screenshots for analysis
- 💬 **Chat Interface** - Natural language coding tasks
- 📱 **Native Performance** - React Native for iOS and Android
- 🔄 **Real-time Sync** - Connect to Anvil server

## Installation

```bash
cd mobile
npm install
```

## Development

### iOS
```bash
npm run ios
```

### Android
```bash
npm run android
```

## Architecture

- **React Native** for cross-platform mobile development
- **Anvil Server API** for task execution
- **Local storage** for offline caching
- **Voice/Camera** for multimodal input

## API Integration

The mobile app connects to the Anvil server via:
- `GET /health` - Health check
- `POST /api/run` - Execute tasks
- WebSocket for real-time updates

## Testing

```bash
npm test
```

## License

MIT © FableForge
