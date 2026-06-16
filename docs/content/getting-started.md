# Getting Started with FableForge

> From zero to your first verified agent task in 10 minutes.

---

## Installation

### pip install (recommended)

```bash
pip install anvil
```

This installs the `anvil` CLI and Python library with all core dependencies.

### From source

```bash
git clone https://github.com/KingLabsA/anvil.git
cd anvil
pip install -e ".[dev]"
```

The `[dev]` extra installs test dependencies, linters, and debug tools.

### Optional dependencies

```bash
# OpenAI model backend
pip install anvil[openai]

# Anthropic model backend
pip install anvil[anthropic]

# All model backends
pip install anvil[all]

# Daemon server
pip install anvil[daemon]

# Everything
pip install anvil[all,daemon]
```

### Verify installation

```bash
anvil --version
# anvil 2.4.0

anvil tools list
# bash         Execute shell commands
# file_read    Read file contents
# file_write   Write or append to files
# file_search  Search files by name or content
# web_fetch    Fetch and extract text from URLs
# python       Execute Python code
# patch        Apply unified diffs
```

---

## Your First Task

### Using the CLI

The simplest way to use Anvil is through the `anvil run` command:

```bash
anvil run "Add a hello() function to greet.py that takes a name and returns a greeting string"
```

This will:
1. **Plan** — Analyze the task and create an execution plan.
2. **Execute** — Run the plan using built-in tools.
3. **Verify** — Check the result for correctness.
4. **Recover** — If verification fails, attempt to fix the issue.

### Using Python

For more control, use the Python API:

```python
from anvil.engine import AnvilEngine

engine = AnvilEngine(model_backend="local")
result = engine.run("Add a hello() function to greet.py")

print(result.summary)
# "Added hello() function to greet.py that takes a name parameter and returns
#  a greeting string. All verification checks passed."

print(result.success)        # True
print(result.duration_seconds)  # 3.2
print(result.verification.passed)  # True
print(result.verification.score)   # 0.95
```

### Dry Run (Plan Only)

To see what Anvil would do without executing anything:

```bash
anvil run "Refactor auth.py to use OAuth2" --dry-run
```

Or in Python:

```python
result = engine.run("Refactor auth.py to use OAuth2", dry_run=True)
```

---

## Configuring Model Backends

Anvil supports three built-in model backends. You can also add custom backends.

### Local (Ollama) — Free, Private

The default backend uses locally-hosted models through Ollama.

```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Pull the FableForge model
ollama pull fableforge-14b

# Start Ollama (runs in background)
ollama serve
```

```python
from anvil.engine import AnvilEngine

engine = AnvilEngine(
    model_backend="local",
    model_name="fableforge-14b",
)
```

**Using vLLM instead of Ollama:**

```python
from anvil.models import LocalModel

model = LocalModel(
    model_name="fableforge-14b",
    base_url="http://localhost:8000",  # vLLM default port
    api_type="vllm",
)
engine = AnvilEngine(config=AnvilConfig(model_backend="custom"))
engine.model = model
```

### OpenAI — Powerful, Paid

```python
from anvil.engine import AnvilEngine

engine = AnvilEngine(
    model_backend="openai",
    model_name="gpt-4o",
)
```

Set your API key:

```bash
export OPENAI_API_KEY="sk-..."
```

Or specify a custom environment variable:

```python
engine = AnvilEngine(
    model_backend="openai",
    api_key_env="MY_OPENAI_KEY",
)
```

### Anthropic — Thoughtful, Paid

```python
from anvil.engine import AnvilEngine

engine = AnvilEngine(
    model_backend="anthropic",
    model_name="claude-sonnet-4-20250514",
)
```

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

### Using a Config File

For persistent configuration, create `anvil.config.yaml`:

```yaml
model:
  backend: openai
  name: gpt-4o
  api_key_env: OPENAI_API_KEY
  temperature: 0.7

engine:
  max_iterations: 15
  verify: true

verify:
  strictness: balanced
```

Then reference it:

```bash
anvil run "Fix the tests" --config anvil.config.yaml
```

```python
from anvil.engine import AnvilEngine, AnvilConfig

config = AnvilConfig.from_file("anvil.config.yaml")
engine = AnvilEngine(config=config)
```

### Cost Optimization

Use the CostOptimizerBridge to automatically route to the cheapest adequate model:

```python
from anvil.engine import AnvilEngine, AnvilConfig
from anvil.integrations import CostOptimizerBridge

engine = AnvilEngine(config=AnvilConfig(model_backend="local"))
optimizer = CostOptimizerBridge(
    default_model="fableforge-14b",
    budget_usd=1.0,
    strategy="best_value",
)
engine = optimizer.attach(engine)
```

---

## Using Verification

Verification is Anvil's killer feature. It checks your code changes after execution.

### Default Verification

By default, Anvil runs verification after every task:

```python
result = engine.run("Add input validation to the login endpoint")
print(result.verification.passed)  # True or False
print(result.verification.score)   # 0.0 - 1.0
print(result.verification.summary) # Human-readable summary
```

### Strictness Levels

```python
from anvil.engine import AnvilConfig

# Relaxed — syntax + tests only
config = AnvilConfig(verify_strictness="relaxed")

# Balanced — syntax + tests + lint + diff review (default)
config = AnvilConfig(verify_strictness="balanced")

# Strict — all 7 checkers
config = AnvilConfig(verify_strictness="strict")
```

### Custom Checkers

Add your own verification logic:

```python
from anvil.verify import VerifyPipeline, BaseChecker

class NoPrintChecker(BaseChecker):
    name = "no_print_statements"
    
    def check(self, result, workspace):
        issues = []
        for change in result.iterations[-1].file_changes:
            if "print(" in change.content:
                issues.append(CheckResult(
                    checker=self.name,
                    passed=False,
                    message=f"Print statement found in {change.path}",
                    severity="warning",
                ))
        return issues

pipeline = VerifyPipeline()
pipeline.add_checker(NoPrintChecker())
report = pipeline.verify(result, workspace=".")
```

### Disabling Verification

For quick prototyping, you can disable verification:

```python
engine = AnvilEngine(verify=False)
# Or via CLI:
# anvil run "Quick fix" --no-verify
```

---

## Using Error Recovery

When tasks fail, Anvil's recovery system kicks in automatically.

### Automatic Recovery

Recovery is enabled by default with `max_retries=3`:

```python
result = engine.run("Add rate limiting to the API")
if not result.success:
    print(f"Failed after {result.cost.total_retries} recovery attempts")
    print(f"Last error: {result.error}")
```

### Recovery Strategies

```python
from anvil.integrations import ErrorRecoveryBridge

# Default: cascade (retry → rewrite → escalate)
bridge = ErrorRecoveryBridge(strategy="cascade")

# Simple retry with backoff
bridge = ErrorRecoveryBridge(strategy="retry", max_attempts=5)

# Rewriting on each failure
bridge = ErrorRecoveryBridge(strategy="rewrite")

result = await bridge.heal(error=exc, context=result, engine=engine)
```

### Integrating with the Engine

```python
from anvil.engine import AnvilEngine, AnvilConfig
from anvil.integrations import ErrorRecoveryBridge

engine = AnvilEngine(config=AnvilConfig(max_retries=3))
bridge = ErrorRecoveryBridge(strategy="cascade", max_attempts=3)

# The engine's built-in recovery handles simple cases.
# For advanced recovery, use the bridge:
try:
    result = engine.run("Complex refactoring task")
except Exception as e:
    result = await bridge.heal(error=e, context=result, engine=engine)
```

---

## Using the Daemon

Run Anvil as a persistent HTTP service for integration with web apps and CI/CD.

### Starting the Daemon

```bash
# Start with defaults
anvil daemon

# Custom port and authentication
anvil daemon --port 8420 --api-key "my-secret-key"

# With a config file
anvil daemon --config anvil.config.yaml
```

### Submitting Tasks

```bash
# Submit a task
curl -X POST http://localhost:8420/v1/tasks \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer my-secret-key" \
  -d '{"task": "Add rate limiting to /api/users"}'

# Response:
# {"task_id": "task_abc123", "status": "running", "created_at": "2026-06-15T10:30:00Z"}

# Check status
curl http://localhost:8420/v1/tasks/task_abc123 \
  -H "Authorization: Bearer my-secret-key"

# Stream events (SSE)
curl -N http://localhost:8420/v1/tasks/task_abc123/stream \
  -H "Authorization: Bearer my-secret-key"
```

### Python Client

```python
import requests

BASE = "http://localhost:8420/v1"
HEADERS = {"Authorization": "Bearer my-secret-key"}

# Submit task
resp = requests.post(f"{BASE}/tasks", json={"task": "Fix the login bug"}, headers=HEADERS)
task_id = resp.json()["task_id"]

# Poll for completion
import time
while True:
    status = requests.get(f"{BASE}/tasks/{task_id}", headers=HEADERS).json()
    if status["status"] in ("completed", "failed"):
        break
    time.sleep(2)

print(status["result"]["summary"])
```

### Daemon in Docker

```dockerfile
FROM python:3.12-slim
RUN pip install anvil[daemon]
EXPOSE 8420
CMD ["anvil", "daemon", "--host", "0.0.0.0", "--port", "8420"]
```

```bash
docker build -t anvil-daemon .
docker run -p 8420:8420 -e OPENAI_API_KEY=$OPENAI_API_KEY anvil-daemon
```

---

## Integrating with Other FableForge Projects

Anvil is the execution engine of the FableForge ecosystem. Here's how it connects to other projects.

### verify-loop — Iterative Verification

```python
from anvil.integrations import VerifyLoopBridge

bridge = VerifyLoopBridge(max_rounds=5, convergence_threshold=0.95)
result = await bridge.run(task="Add input validation", engine=engine)
# Runs plan→execute→verify loops until score ≥ 0.95
```

### error-recovery — Intelligent Error Healing

```python
from anvil.integrations import ErrorRecoveryBridge

bridge = ErrorRecoveryBridge(strategy="cascade", max_attempts=3)
result = await bridge.heal(error=exc, context=result, engine=engine)
```

### agent-swarm — Multi-Agent Delegation

```python
from anvil.integrations import AgentSwarmBridge

bridge = AgentSwarmBridge(agents=["coder", "reviewer", "tester"])
result = await bridge.delegate(task="Implement auth with tests", engine=engine)
```

### cost-optimizer — Smart Model Routing

```python
from anvil.integrations import CostOptimizerBridge

bridge = CostOptimizerBridge(budget_usd=1.0, strategy="best_value")
engine = bridge.attach(engine)
# Now all engine.run() calls are routed to the optimal model
```

### Using Multiple Bridges Together

```python
from anvil.engine import AnvilEngine, AnvilConfig
from anvil.integrations import (
    VerifyLoopBridge,
    ErrorRecoveryBridge,
    CostOptimizerBridge,
)

# Set up engine with all integrations
engine = AnvilEngine(config=AnvilConfig(model_backend="local"))

# Attach cost optimization
cost_bridge = CostOptimizerBridge(budget_usd=2.0, strategy="best_value")
engine = cost_bridge.attach(engine)

# Run task with verification loop
verify_bridge = VerifyLoopBridge(max_rounds=5, convergence_threshold=0.95)

try:
    result = await verify_bridge.run(
        task="Implement user registration with validation and tests",
        engine=engine,
    )
except Exception as e:
    # Fall back to error recovery
    recovery_bridge = ErrorRecoveryBridge(strategy="cascade")
    result = await recovery_bridge.heal(error=e, context=result, engine=engine)

print(result.summary)
print(f"Verification score: {result.verification.score:.2f}")
print(f"Total cost: ${result.cost.total_usd:.4f}")
```

---

## Common Patterns and Recipes

### Pattern: Multi-File Refactoring

```python
result = engine.run(
    "Refactor the authentication module: "
    "1) Move auth logic from app.py to auth/ module "
    "2) Add OAuth2 support "
    "3) Update all imports "
    "4) Ensure existing tests still pass",
    context="The project uses Flask with Blueprints",
    max_iterations=20,
)
```

### Pattern: Bug Fix with Verification

```python
result = engine.run(
    "Fix the off-by-one error in the pagination logic",
    context="Bug reported in issue #42: last page returns empty results",
)
if result.verification.passed:
    print("Bug fixed and verified!")
else:
    print(f"Verification score: {result.verification.score}")
    for check in result.verification.checkers:
        if not check.passed:
            print(f"  ✗ {check.checker}: {check.message}")
```

### Pattern: Test Generation

```python
result = engine.run(
    "Write unit tests for src/calculator.py with at least 90% coverage",
    verify=True,
)
```

### Pattern: Code Review

```python
result = engine.run(
    "Review the changes in the last git commit and identify potential issues",
    verify=False,  # No code changes expected
)
print(result.summary)
```

### Pattern: Streaming Progress

```python
async for event in engine.run_stream("Implement the new API endpoint"):
    match event.phase:
        case "plan":
            print(f"[PLAN] {event.content}")
        case "execute":
            print(f"[{event.tool}] {event.content[:80]}")
        case "verify":
            status = "✓" if event.result else "✗"
            print(f"  {status} {event.check_name}")
        case "recover":
            print(f"[RECOVER] {event.content}")
```

### Pattern: Session Continuity

```python
# Start a session
session_id = result.session_id

# Continue in the same session
result2 = engine.run(
    "Now add input validation to the same endpoint",
    session_id=session_id,
)

# Resume after interruption
result3 = engine.resume(session_id)
```

### Pattern: Custom Tool Integration

```python
from anvil.tools import BaseTool

class DatabaseTool(BaseTool):
    name = "database"
    description = "Query and modify the application database"
    
    def run(self, query: str, dry_run: bool = False) -> str:
        # Your database logic here
        if dry_run:
            return f"Would execute: {query}"
        return execute_sql(query)

engine = AnvilEngine(tools=[
    BashTool(), FileReadTool(), FileWriteTool(),
    FileSearchTool(), WebFetchTool(), PythonTool(),
    DatabaseTool(),  # Custom tool added
])
```

---

## Troubleshooting

### "Model not found" errors

```bash
# For local models, ensure Ollama is running and the model is pulled
ollama list
ollama pull fableforge-14b
```

### "Sandbox violation" errors

```python
# Add additional directories to the sandbox
engine = AnvilEngine(
    workspace="/projects/myapp",
    config=AnvilConfig(sandbox_dirs=["/projects/myapp", "/tmp/tests"]),
)
```

### "Cost limit exceeded" errors

```python
# Increase or remove cost limit
config = AnvilConfig(cost_limit_usd=5.0)  # Increase to $5
# Or remove limit entirely
config = AnvilConfig(cost_limit_usd=None)  # No limit
```

### Slow local model responses

```python
# Reduce context length for faster responses
model = LocalModel(
    model_name="fableforge-14b",
    context_length=4096,  # Reduce from default 8192
)
```

### Getting debug output

```bash
# Enable verbose logging
anvil run "Fix the bug" --verbose

# Or in Python
import logging
logging.getLogger("anvil").setLevel(logging.DEBUG)
```
