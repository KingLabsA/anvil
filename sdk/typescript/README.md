# Anvil TypeScript SDK

TypeScript SDK for [Anvil](https://github.com/KingLabsA/anvil) - the self-verified coding agent.

## Installation

```bash
npm install @anvil-ai/sdk
```

## Prerequisites

Make sure you have the Anvil server running:

```bash
# Install Anvil
pip install fableforge-anvil-agent[web]

# Start the server
anvil serve --port 8765
```

## Usage

### Basic Example

```typescript
import { AnvilClient } from '@anvil-ai/sdk';

const anvil = new AnvilClient({
  baseUrl: 'http://localhost:8765',
  model: 'local',
  maxIterations: 20
});

// Execute a task
const result = await anvil.run('Fix the bug in main.py');
console.log(result.success); // true
console.log(result.output); // "Task completed and verified"
```

### Streaming Execution

```typescript
// Stream execution progress
for await (const message of anvil.stream('Create a new feature')) {
  if (message.type === 'step') {
    console.log('Step:', message.step?.content);
  } else if (message.type === 'result') {
    console.log('Result:', message.result?.output);
  }
}
```

### Session Management

```typescript
// List recent sessions
const sessions = await anvil.listSessions(10);
console.log(sessions);

// Get a specific session
const session = await anvil.getSession('session-id-123');
console.log(session.task);
console.log(session.stats.success_rate);
```

### Health Check

```typescript
const health = await anvil.health();
console.log(health.status); // "ok"
console.log(health.version); // "0.3.0"
```

## API Reference

### `AnvilClient`

#### Constructor

```typescript
new AnvilClient(config?: AnvilConfig)
```

**Config options:**
- `baseUrl` - Server URL (default: `http://localhost:8765`)
- `timeout` - Request timeout in ms (default: `30000`)
- `model` - Model to use (default: `local`)
- `maxIterations` - Max iterations (default: `20`)
- `verify` - Enable verification (default: `true`)

#### Methods

##### `run(task, options?)`

Execute a task synchronously.

```typescript
const result = await anvil.run('Fix the bug', {
  model: 'gpt-4',
  maxIterations: 10,
  verify: true
});
```

**Returns:** `Promise<RunResponse>`

##### `stream(task, options?)`

Execute a task with streaming via WebSocket.

```typescript
for await (const message of anvil.stream('Create feature')) {
  console.log(message.type, message);
}
```

**Returns:** `AsyncGenerator<StreamMessage>`

##### `getSession(sessionId)`

Retrieve a session by ID.

```typescript
const session = await anvil.getSession('session-123');
```

**Returns:** `Promise<Session>`

##### `listSessions(limit?)`

List recent sessions.

```typescript
const sessions = await anvil.listSessions(50);
```

**Returns:** `Promise<SessionInfo[]>`

##### `health()`

Check server health.

```typescript
const health = await anvil.health();
```

**Returns:** `Promise<HealthResponse>`

##### `configure(config)`

Update client configuration.

```typescript
anvil.configure({
  baseUrl: 'http://new-server:9000',
  model: 'gpt-4'
});
```

## Types

### `RunResponse`

```typescript
interface RunResponse {
  success: boolean;
  output: string;
  error?: string;
  steps: number;
  session_id: string;
}
```

### `Session`

```typescript
interface Session {
  id: string;
  task: string;
  steps: Step[];
  stats: SessionStats;
  created_at: string;
  updated_at: string;
}
```

### `Step`

```typescript
interface Step {
  id: string;
  kind: 'plan' | 'execute' | 'verify' | 'recover';
  content: string;
  status: 'pending' | 'running' | 'success' | 'failed' | 'recovered';
  tool_calls?: ToolCall[];
  verify_result?: VerifyResult;
  error?: string;
  timestamp: string;
}
```

### `StreamMessage`

```typescript
interface StreamMessage {
  type: 'status' | 'step' | 'result' | 'error';
  message?: string;
  step?: Step;
  result?: RunResponse;
  error?: string;
}
```

## Error Handling

The SDK throws descriptive errors:

```typescript
try {
  await anvil.run('Bad task');
} catch (error) {
  if (error.message.includes('not reachable')) {
    console.error('Server is not running');
  } else if (error.message.includes('Anvil error')) {
    console.error('Task failed:', error.message);
  }
}
```

## License

MIT

## Links

- [Anvil GitHub](https://github.com/KingLabsA/anvil)
- [Anvil PyPI](https://pypi.org/project/fableforge-anvil-agent/)
- [Documentation](https://github.com/KingLabsA/anvil#readme)
