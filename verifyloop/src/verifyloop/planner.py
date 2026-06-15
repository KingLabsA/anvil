"""Plan phase: decompose tasks into executable substeps."""

from __future__ import annotations

import json
import re
from typing import Any

import litellm

from verifyloop.models import PlanStep, Substep, TokenUsage

PLAN_SYSTEM_PROMPT = """You are a planning agent. Given a task and optional context, produce a JSON plan.

Your plan must be a JSON object with these fields:
{
  "description": "One-line summary of the overall task",
  "substeps": ["Step 1 description", "Step 2 description", ...],
  "estimated_tools": ["bash", "edit", "read", "write", "web_search", "web_fetch"],
  "complexity": "low" | "medium" | "high",
  "substep_details": [
    {
      "description": "What this step does",
      "tool": "Tool name to use",
      "arguments": {"arg_name": "value"},
      "order": 0
    }
  ]
}

Rules:
- Each substep should be atomic and independently verifiable
- Prefer small, targeted edits over large rewrites
- Estimate which tools will be needed
- Be specific about file paths, commands, and expected outcomes
- Order substeps so earlier steps produce artifacts later steps need

Respond ONLY with valid JSON, no markdown fences."""


class PlanGenerator:
    def __init__(
        self,
        model: str = "gpt-4o",
        api_key: str | None = None,
        api_base: str | None = None,
        temperature: float = 0.1,
    ) -> None:
        self.model = model
        self.api_key = api_key
        self.api_base = api_base
        self.temperature = temperature
        self._token_usage = TokenUsage()

    @property
    def token_usage(self) -> TokenUsage:
        return self._token_usage

    async def generate_plan(
        self,
        task: str,
        context: str = "",
    ) -> PlanStep:
        messages = []
        messages.append({"role": "system", "content": PLAN_SYSTEM_PROMPT})

        user_content = f"Task: {task}"
        if context:
            user_content += f"\n\nContext:\n{context}"
        messages.append({"role": "user", "content": user_content})

        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
        }
        if self.api_key:
            kwargs["api_key"] = self.api_key
        if self.api_base:
            kwargs["api_base"] = self.api_base

        response = await litellm.acompletion(**kwargs)

        self._token_usage = self._token_usage.merge(
            TokenUsage(
                prompt_tokens=response.usage.prompt_tokens if response.usage else 0,
                completion_tokens=response.usage.completion_tokens if response.usage else 0,
                total_tokens=response.usage.total_tokens if response.usage else 0,
            )
        )

        content = response.choices[0].message.content or "{}"
        content = re.sub(r"^```(?:json)?\s*", "", content.strip())
        content = re.sub(r"\s*```$", "", content.strip())

        try:
            plan_data = json.loads(content)
        except json.JSONDecodeError:
            return self._fallback_plan(task)

        details = []
        for sd in plan_data.get("substep_details", []):
            details.append(
                Substep(
                    description=sd.get("description", ""),
                    tool=sd.get("tool", "bash"),
                    arguments=sd.get("arguments", {}),
                    order=sd.get("order", len(details)),
                )
            )

        return PlanStep(
            description=plan_data.get("description", task),
            substeps=plan_data.get("substeps", []),
            estimated_tools=plan_data.get("estimated_tools", ["bash"]),
            substep_details=details,
            complexity=plan_data.get("complexity", "medium"),
            context_tokens=self._token_usage.prompt_tokens,
        )

    def decompose_task(self, task: str) -> list[Substep]:
        patterns = [
            (r"add\s+(\w+)\s+to\s+(\w+\.\w+)", "edit", lambda m: {
                "file_path": m.group(2),
                "description": f"Add {m.group(1)} to {m.group(2)}",
            }),
            (r"fix\s+(?:the\s+)?(\w+)\s+in\s+(\w+\.\w+)", "edit", lambda m: {
                "file_path": m.group(2),
                "description": f"Fix {m.group(1)} in {m.group(2)}",
            }),
            (r"(?:create|write|make)\s+(?:a\s+)?(\w+\.\w+)", "write", lambda m: {
                "file_path": m.group(1),
                "description": f"Create {m.group(1)}",
            }),
            (r"(?:read|show|cat|view)\s+(\w+\.\w+)", "read", lambda m: {
                "file_path": m.group(1),
                "description": f"Read {m.group(1)}",
            }),
            (r"run\s+(.+)", "bash", lambda m: {
                "command": m.group(1),
                "description": f"Run: {m.group(1)}",
            }),
            (r"(?:search|look up|find)\s+(?:for\s+)?(.+?)(?:\s+on(?:line| the web))?\.?$", "web_search", lambda m: {
                "query": m.group(1),
                "description": f"Search for: {m.group(1)}",
            }),
        ]

        for pattern, tool, arg_fn in patterns:
            match = re.match(pattern, task, re.IGNORECASE)
            if match:
                args = arg_fn(match)
                return [
                    Substep(
                        description=args.pop("description", task),
                        tool=tool,
                        arguments=args,
                        order=0,
                    )
                ]

        return [Substep(description=task, tool="bash", arguments={"command": task}, order=0)]

    def estimate_tools(self, task: str) -> list[str]:
        tools: set[str] = set()

        if re.search(r"(?:run|execute|install|pip|npm|cargo|make|build)", task, re.I):
            tools.add("bash")
        if re.search(r"(?:add|fix|edit|modify|update|change|refactor)", task, re.I):
            tools.add("edit")
        if re.search(r"(?:create|write|new|make)\s+(?:a\s+)?(?:file|module|class)", task, re.I):
            tools.add("write")
        if re.search(r"(?:read|show|view|check|inspect|display)", task, re.I):
            tools.add("read")
        if re.search(r"(?:search|look up|find|google)", task, re.I):
            tools.add("web_search")
        if re.search(r"(?:fetch|download|curl|url|http)", task, re.I):
            tools.add("web_fetch")

        return list(tools) or ["bash"]

    def _fallback_plan(self, task: str) -> PlanStep:
        substeps = self.decompose_task(task)
        return PlanStep(
            description=task,
            substeps=[s.description for s in substeps],
            estimated_tools=[s.tool for s in substeps],
            substep_details=substeps,
            complexity="low" if len(substeps) <= 2 else "medium",
        )
