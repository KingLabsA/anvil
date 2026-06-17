"""Debug: see what models actually output for tool-call prompts."""

import sys
import json
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from anvil.models.registry import ModelRegistry, Message
from anvil.core.engine import SYSTEM_PROMPT, ALL_TOOL_NAMES

TOOL_PROMPT = """You are fixing calculator.py. The file has bugs:
- subtract(a,b) returns a-b-1 instead of a-b
- divide(a,b) uses a//b (integer division) instead of a/b

Fix the bugs by using the edit tool. Emit a tool call like:

```tool
{{"tool": "edit", "args": {{"path": "calculator.py", "old_string": "    return a - b - 1", "new_string": "    return a - b"}}}}
```

Then fix divide:
```tool
{{"tool": "edit", "args": {{"path": "calculator.py", "old_string": "    return a // b", "new_string": "    return a / b"}}}}
```

Then verify with tests:
```tool
{{"tool": "bash", "args": {{"command": "python -m pytest test_calculator.py -v"}}}}
```

Now emit the actual tool calls to fix calculator.py:"""


def test_model(model_name: str, api_base: str = "http://localhost:11434"):
    print(f"\n{'='*60}")
    print(f"Testing: {model_name}")
    print(f"{'='*60}")

    model = ModelRegistry.create(model_name, api_base=api_base)

    system = SYSTEM_PROMPT.format(agent_name="debug", tools=", ".join(ALL_TOOL_NAMES))
    messages = [
        Message(role="system", content=system),
        Message(role="user", content=TOOL_PROMPT),
    ]

    response = model.complete(messages, temperature=0.1, max_tokens=1024)

    print(f"Model: {response.model}")
    print(f"Tokens: in={response.input_tokens} out={response.output_tokens}")
    print(f"Duration: {response.duration_ms:.0f}ms")
    print(f"\n--- Raw output (first 1500 chars) ---")
    print(response.content[:1500])
    print(f"\n--- End output ---")

    # Try parsing
    from anvil.core.engine import AnvilEngine
    engine = AnvilEngine.__new__(AnvilEngine)
    tool_calls = engine._parse_tool_calls(response.content)

    print(f"\nParsed tool calls: {len(tool_calls)}")
    for i, tc in enumerate(tool_calls):
        print(f"  [{i}] tool={tc['tool']} args={json.dumps(tc['args'], ensure_ascii=False)[:200]}")

    return response.content, tool_calls


if __name__ == "__main__":
    models = [
        "shellwhisperer-1.5b:latest",
        "shellwhisperer:latest",
        "mythos-9b:latest",
        "mythos-9b-enhanced:latest",
        "mythos-9b-unhinged:latest",
        "fableforge-ai/shellwhisperer:latest",
        "fableforge-ai/mythos-9b:latest",
        "fableforge-ai/mythos-9b-unhinged:latest",
    ]

    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", nargs="*", default=None)
    parser.add_argument("--api-base", default="http://localhost:11434")
    args = parser.parse_args()

    test_models = args.models if args.models else models

    for m in test_models:
        try:
            content, calls = test_model(m, args.api_base)
        except Exception as e:
            print(f"\n  ERROR: {e}")
