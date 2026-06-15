"""Basic usage example for VerifyLoop."""

import asyncio

from verifyloop import AgentPipeline, PipelineConfig


async def main() -> None:
    config = PipelineConfig(
        model="gpt-4o",
        verify_model="reason-critic-7b",
        max_iterations=3,
        confidence_threshold=0.8,
        working_dir=".",
    )

    pipeline = AgentPipeline(config)

    async def on_event(event: str, data: dict) -> None:
        print(f"[{event}] {data}")

    pipeline.on_event(on_event)

    result = await pipeline.run(
        task="Add a hello() function to app.py that returns 'Hello, World!'",
        context="This is a Python project with a Flask app.",
    )

    print(f"\nStatus: {result.status}")
    print(f"Iterations: {result.iteration}")
    print(f"Duration: {result.duration_seconds:.2f}s")
    print(f"Steps: {len(result.steps)}")
    print(f"Tokens: {result.token_usage.total_tokens}")


if __name__ == "__main__":
    asyncio.run(main())
