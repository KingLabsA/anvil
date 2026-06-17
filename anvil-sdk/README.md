# Anvil SDK

SDK for embedding Anvil AI agent in your applications.

## Installation

```bash
pip install anvil-sdk
```

## Quick Start

```python
from anvil_sdk import AnvilClient

with AnvilClient("http://localhost:8000") as client:
    result = client.tasks.run("Create a fibonacci function")
    print(result)
```

## Features

- **Agent Management** — Create, list, invoke, and delete agents
- **Task Execution** — Run tasks synchronously or stream results via WebSocket
- **Event System** — Subscribe to server events with typed handlers
- **Code Helpers** — Verify, explain, and refactor code through the API

## Examples

See the [`examples/`](examples/) directory for complete usage samples.

## License

MIT
