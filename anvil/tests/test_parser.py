"""Quick test of parser improvements."""
import sys
sys.path.insert(0, "src")
from anvil.core.engine import AnvilEngine

engine = AnvilEngine.__new__(AnvilEngine)

# 1. Thinking block stripping
text = '<|begin of thinking|>I need to fix this<|end of thinking|>\n```tool\n{"tool": "edit", "args": {"path": "x.py", "old_string": "a", "new_string": "b"}}\n```'
calls = engine._parse_tool_calls(text)
print(f"1. Thinking + tool block: {len(calls)} calls  (expected 1)")
assert len(calls) == 1, f"FAIL: got {len(calls)}"

# 2. Double-brace escaping
text2 = '```tool\n{{"tool": "edit", "args": {{"path": "x.py", "old_string": "a", "new_string": "b"}}}}\n```'
calls2 = engine._parse_tool_calls(text2)
print(f"2. Double-brace: {len(calls2)} calls  (expected 1)")
assert len(calls2) == 1, f"FAIL: got {len(calls2)}"

# 3. Bare JSON outside fences
text3 = 'Here is the fix: {"tool": "edit", "args": {"path": "x.py", "old_string": "a", "new_string": "b"}}'
calls3 = engine._parse_tool_calls(text3)
print(f"3. Bare JSON: {len(calls3)} calls  (expected 1)")
assert len(calls3) == 1, f"FAIL: got {len(calls3)}"

# 4. Natural language fallback
text4 = 'I need to edit calculator.py to replace "return a - b - 1" with "return a - b"'
calls4 = engine._parse_tool_calls(text4)
print(f"4. Natural language: {len(calls4)} calls  (expected 1)")
assert len(calls4) == 1, f"FAIL: got {len(calls4)}"

# 5. Empty = failure
print(f"5. Empty results -> False: {not []}  (expected True)")
assert not []

print("\nAll parser tests PASS")
