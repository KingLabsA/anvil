"""Coding agent example: full Plan → Execute → Verify → Recover cycle."""

import asyncio

from verifyloop import AgentPipeline, Executor, PipelineConfig, Verifier, VerifierConfig
from verifyloop.models import ExecuteStep


async def main() -> None:
    config = PipelineConfig(
        model="gpt-4o",
        verify_model="reason-critic-7b",
        max_iterations=5,
        confidence_threshold=0.85,
        max_recovery_attempts=3,
        working_dir=".",
    )

    pipeline = AgentPipeline(config)

    result = await pipeline.run(
        task="Create a Python module 'calculator.py' with add, subtract, multiply, "
             "and divide functions, then write unit tests for it",
        context="This is a new Python project. Use pytest for testing.",
    )

    if result.status.value == "completed":
        print("Task completed successfully!")

        # Verify file state using the standalone verifier
        executor = Executor(working_dir=".")
        verifier = Verifier(VerifierConfig(verify_model="reason-critic-7b"))

        # Check the calculator was created
        read_result = await executor.read("calculator.py")
        if read_result.success:
            print(f"\nCalculator module ({len(read_result.result)} chars):\n")
            print(read_result.result[:500])

        # Run the tests
        test_result: ExecuteStep = await executor.bash("python -m pytest test_calculator.py -v")
        print(f"\nTest results: {'PASSED' if test_result.success else 'FAILED'}")
    else:
        print(f"Task failed after {result.iteration} iterations")
        for step in result.steps:
            print(f"  [{step.step_type.value}] {step.content[:100]}")


if __name__ == "__main__":
    asyncio.run(main())
