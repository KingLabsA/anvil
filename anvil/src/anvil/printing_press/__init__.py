"""Printing Press — turn any API into a runnable Anvil CLI wrapper + loadable skill.

Inspired by Matt Van Horn's Printing Press concept: given a service's API
(an OpenAPI/Swagger spec or just a base URL), generate a self-contained CLI
that an agent can call, plus a SKILL.md so the agent knows how to use it.
"""

from anvil.printing_press.generator import (
    Endpoint,
    PressResult,
    generate_cli_source,
    generate_skill_md,
    parse_openapi,
    press,
)

__all__ = [
    "Endpoint",
    "PressResult",
    "parse_openapi",
    "generate_cli_source",
    "generate_skill_md",
    "press",
]
