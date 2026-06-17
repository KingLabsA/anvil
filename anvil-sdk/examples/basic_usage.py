"""Basic usage example for Anvil SDK."""

from anvil_sdk import AnvilClient

with AnvilClient(api_url="http://localhost:8000") as client:
    print(client.health_check())

    result = client.tasks.run("Create a fibonacci function")
    print(result)

    agents = client.agents.list()
    print(agents)

    result = client.agents.invoke("assistant", "Explain this code: def foo(): pass")
    print(result)
