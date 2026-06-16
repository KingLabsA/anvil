# API Reference

This document provides a complete reference for the Anvil API.

## Base URL

```
http://localhost:8000
```

## Authentication

Currently, the API does not require authentication. In production, you should configure authentication.

## Endpoints

### Health Check

Check if the server is running.

```http
GET /health
```

**Response:**

```json
{
  "status": "ok",
  "version": "0.3.0"
}
```

### Run Task

Execute a coding task.

```http
POST /api/run
```

**Request Body:**

```json
{
  "task": "Add error handling to all API endpoints",
  "model": "local",
  "max_iterations": 20
}
```

**Parameters:**

- `task` (string, required): The task description
- `model` (string, optional): Model to use (`local` or `api`)
- `max_iterations` (integer, optional): Maximum iterations (default: 20)

**Response:**

```json
{
  "success": true,
  "output": "Task completed successfully",
  "error": null,
  "duration_ms": 1234
}
```

### Analyze Code

Analyze code for issues.

```http
POST /api/analyze
```

**Request Body:**

```json
{
  "code": "def add(a, b):\n    return a + b",
  "language": "python"
}
```

**Parameters:**

- `code` (string, required): The code to analyze
- `language` (string, optional): Programming language (default: `python`)

**Response:**

```json
{
  "issues": [],
  "suggestions": ["Consider adding type hints"],
  "score": 0.95
}
```

### Explain Code

Get an explanation of code.

```http
POST /api/explain
```

**Request Body:**

```json
{
  "code": "def add(a, b):\n    return a + b",
  "language": "python"
}
```

**Parameters:**

- `code` (string, required): The code to explain
- `language` (string, optional): Programming language (default: `python`)

**Response:**

```json
{
  "explanation": "This function takes two parameters and returns their sum."
}
```

### Optimize Code

Get optimization suggestions.

```http
POST /api/optimize
```

**Request Body:**

```json
{
  "code": "def add(a, b):\n    return a + b",
  "language": "python"
}
```

**Parameters:**

- `code` (string, required): The code to optimize
- `language` (string, optional): Programming language (default: `python`)

**Response:**

```json
{
  "optimized_code": "def add(a: int, b: int) -> int:\n    return a + b",
  "improvements": ["Added type hints for better type safety"]
}
```

### Review Code

Get a code review.

```http
POST /api/review
```

**Request Body:**

```json
{
  "code": "def add(a, b):\n    return a + b",
  "language": "python"
}
```

**Parameters:**

- `code` (string, required): The code to review
- `language` (string, optional): Programming language (default: `python`)

**Response:**

```json
{
  "review": "The code is simple and correct. Consider adding error handling.",
  "score": 0.85,
  "issues": []
}
```

### Fix Issues

Fix issues in code.

```http
POST /api/fix
```

**Request Body:**

```json
{
  "code": "def add(a, b)\n    return a + b",
  "language": "python"
}
```

**Parameters:**

- `code` (string, required): The code to fix
- `language` (string, optional): Programming language (default: `python`)

**Response:**

```json
{
  "fixed_code": "def add(a, b):\n    return a + b",
  "fixes": ["Added missing colon after function definition"]
}
```

## Error Responses

All endpoints return errors in the following format:

```json
{
  "error": "Error message",
  "details": "Additional details (optional)"
}
```

## Rate Limiting

Currently, there is no rate limiting. In production, you should configure rate limiting.

## WebSocket API

Anvil also provides a WebSocket API for real-time communication.

### Connect

```javascript
const ws = new WebSocket('ws://localhost:8000/ws');
```

### Messages

**Send a task:**

```json
{
  "type": "task",
  "task": "Add error handling",
  "model": "local"
}
```

**Receive updates:**

```json
{
  "type": "update",
  "status": "running",
  "message": "Analyzing code..."
}
```

**Receive result:**

```json
{
  "type": "result",
  "success": true,
  "output": "Task completed"
}
```

## SDK Usage

### Python

```python
from anvil.client import AnvilClient

client = AnvilClient(base_url="http://localhost:8000")

# Run a task
result = client.run("Add error handling")
print(result.output)

# Analyze code
analysis = client.analyze("def add(a, b): return a + b")
print(analysis.suggestions)
```

### JavaScript

```javascript
const anvil = require('anvil-sdk');

const client = new anvil.Client({
  baseUrl: 'http://localhost:8000'
});

// Run a task
const result = await client.run('Add error handling');
console.log(result.output);

// Analyze code
const analysis = await client.analyze('def add(a, b): return a + b');
console.log(analysis.suggestions);
```

## Next Steps

- Explore the [CLI Reference](./cli-reference.md)
- Learn about [Extensions](./extensions.md)
- Check out [Examples](./examples.md)
