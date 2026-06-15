"""ReasonCritic: A self-verification model that critiques agent output."""

__version__ = "0.1.0"

__all__ = [
    "ReasonCritic",
    "VerificationResult",
    "StepVerification",
    "RunVerification",
    "GenerateVerifyPipeline",
    "VerifiedResult",
]


def __getattr__(name: str):
    if name == "ReasonCritic":
        from reason_critic.critic import ReasonCritic
        return ReasonCritic
    elif name == "VerificationResult":
        from reason_critic.critic import VerificationResult
        return VerificationResult
    elif name == "StepVerification":
        from reason_critic.critic import StepVerification
        return StepVerification
    elif name == "RunVerification":
        from reason_critic.critic import RunVerification
        return RunVerification
    elif name == "GenerateVerifyPipeline":
        from reason_critic.pipeline import GenerateVerifyPipeline
        return GenerateVerifyPipeline
    elif name == "VerifiedResult":
        from reason_critic.pipeline import VerifiedResult
        return VerifiedResult
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
