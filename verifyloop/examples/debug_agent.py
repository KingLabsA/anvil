"""Debug agent example: find and fix a bug using the recovery loop."""

import asyncio

from verifyloop import AgentPipeline, PipelineConfig
from verifyloop.models import RunStatus


async def main() -> None:
    config = PipelineConfig(
        model="gpt-4o",
        verify_model="reason-critic-7b",
        max_iterations=5,
        confidence_threshold=0.75,
        max_recovery_attempts=3,
    )

    pipeline = AgentPipeline(config)

    # The agent will plan, execute, verify, and if verification fails,
    # it will recover (fix the bug) and try again
    result = await pipeline.run(
        task="Fix the bug in main.py where the calculate_total function "
             "doesn't handle empty lists (it should return 0 instead of crashing)",
        context="The project is in the current directory. main.py has a calculate_total function.",
    )

    print(f"Status: {result.status.value}")
    print(f"Iterations used: {result.iteration}/{result.max_iterations}")

    if result.status == RunStatus.COMPLETED:
        print("Bug fixed successfully!")

        # Show recovery steps used
        recover_steps = [
            s for s in result.steps
            if s.step_type.value == "recover"
        ]
        if recover_steps:
            print(f"\nRecovery attempts: {len(recover_steps)}")
            for step in recover_steps:
                print(f"  - {step.content}")
    else:
        print("Could not fix the bug. Consider:")
        print("  1. Increasing max_iterations")
        print("  2. Providing more context")
        print("  3. Using a more capable model")


if __name__ == "__main__":
    asyncio.run(main())
