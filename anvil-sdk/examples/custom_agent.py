"""Custom agent creation example."""

from anvil_sdk import AnvilClient, AgentConfig

with AnvilClient(api_url="http://localhost:8000") as client:
    config = AgentConfig(
        name="code-reviewer",
        description="Reviews code for bugs, style issues, and performance problems.",
        model="local",
        system_prompt="You are a senior code reviewer. Be thorough but constructive.",
        tools=["file_read", "lint"],
    )

    agent = client.agents.create(config)
    print(f"Created agent: {agent}")

    result = client.agents.invoke(
        agent["id"],
        "Review this function for potential issues.",
        context={"code": "def process(data):\n    return [x for x in data if x]"},
    )
    print(result)

    client.agents.delete(agent["id"])
