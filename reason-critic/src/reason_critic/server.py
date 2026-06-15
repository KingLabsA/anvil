"""FastAPI server for the ReasonCritic verification API.

Endpoints:
    POST /verify        — Verify code
    POST /verify/step   — Verify a single step
    POST /verify/run    — Verify a full agent run
    POST /pipeline      — Generate-then-verify pipeline
    GET  /health        — Health check
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)


# --- Global state ---

_critic = None
_pipeline = None


# --- Request/Response models ---

class VerifyRequest(BaseModel):
    code: str
    context: str = ""
    language: str = "python"


class VerifyStepRequest(BaseModel):
    step: dict
    context: str = ""


class VerifyRunRequest(BaseModel):
    run: dict
    context: str = ""


class PipelineRequest(BaseModel):
    task: str
    max_attempts: int = 3
    language: str = "python"
    context: str = ""


class VerifyResponse(BaseModel):
    pass_fail: str
    confidence: float
    issues: list[str]
    suggestions: list[str]
    explanation: str
    language: str


class StepVerifyResponse(BaseModel):
    step_index: int
    step_type: str
    step_name: str
    result: VerifyResponse


class RunVerifyResponse(BaseModel):
    run_id: str
    overall_verdict: str
    overall_confidence: float
    num_passed: int
    num_failed: int
    summary: str
    step_verifications: list[StepVerifyResponse]


class PipelineResponse(BaseModel):
    task: str
    passed: bool
    total_attempts: int
    final_code: str
    final_verification: VerifyResponse
    attempts: list[dict]


class HealthResponse(BaseModel):
    status: str
    model: str
    backend: str


class SetupRequest(BaseModel):
    backend: str = "local"
    model_name: str = "Qwen/Qwen3-7B"
    device: str = "auto"
    api_endpoint: str = ""
    api_key: str = ""
    generator_model: str = "Qwen/Qwen3-7B"
    max_attempts: int = 3


# --- App ---

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting ReasonCritic server")
    yield
    logger.info("Shutting down ReasonCritic server")


app = FastAPI(
    title="ReasonCritic",
    description="A self-verification model that critiques agent output",
    version="0.1.0",
    lifespan=lifespan,
)


def get_critic():
    global _critic
    if _critic is None:
        raise HTTPException(status_code=503, detail="Critic model not initialized. Call /setup first.")
    return _critic


def get_pipeline():
    global _pipeline
    if _pipeline is None:
        raise HTTPException(status_code=503, detail="Pipeline not initialized. Call /setup first.")
    return _pipeline


@app.post("/setup")
async def setup(request: SetupRequest):
    """Initialize the critic and pipeline models."""
    global _critic, _pipeline

    from reason_critic.critic import ReasonCritic

    _critic = ReasonCritic(
        backend=request.backend,
        model_name=request.model_name,
        device=request.device,
        api_endpoint=request.api_endpoint,
        api_key=request.api_key,
    )

    if request.backend != "api":
        from reason_critic.pipeline import GenerateVerifyPipeline, GeneratorWrapper

        generator = GeneratorWrapper(model_name=request.generator_model, device=request.device)
        _pipeline = GenerateVerifyPipeline(
            generator=generator,
            critic=_critic,
            max_attempts=request.max_attempts,
        )

    return {"status": "initialized", "backend": request.backend, "model": request.model_name}


@app.post("/verify", response_model=VerifyResponse)
async def verify(request: VerifyRequest):
    """Verify a piece of code."""
    critic = get_critic()
    result = critic.verify(code=request.code, context=request.context, language=request.language)
    return VerifyResponse(**result.to_dict())


@app.post("/verify/step", response_model=StepVerifyResponse)
async def verify_step(request: VerifyStepRequest):
    """Verify a single agent step."""
    critic = get_critic()
    result = critic.verify_step(step=request.step, context=request.context)
    return StepVerifyResponse(
        step_index=result.step_index,
        step_type=result.step_type,
        step_name=result.step_name,
        result=VerifyResponse(**result.result.to_dict()),
    )


@app.post("/verify/run", response_model=RunVerifyResponse)
async def verify_run(request: VerifyRunRequest):
    """Verify a full agent run."""
    critic = get_critic()
    result = critic.verify_run(run=request.run, context=request.context)

    step_responses = [
        StepVerifyResponse(
            step_index=sv.step_index,
            step_type=sv.step_type,
            step_name=sv.step_name,
            result=VerifyResponse(**sv.result.to_dict()),
        )
        for sv in result.step_verifications
    ]

    return RunVerifyResponse(
        run_id=result.run_id,
        overall_verdict=result.overall_verdict,
        overall_confidence=result.overall_confidence,
        num_passed=result.num_passed,
        num_failed=result.num_failed,
        summary=result.summary,
        step_verifications=step_responses,
    )


@app.post("/pipeline", response_model=PipelineResponse)
async def pipeline(request: PipelineRequest):
    """Generate-then-verify pipeline."""
    pipeline_instance = get_pipeline()

    result = pipeline_instance.generate_and_verify(
        task=request.task,
        max_attempts=request.max_attempts,
        language=request.language,
        context=request.context,
    )

    return PipelineResponse(
        task=result.task,
        passed=result.passed,
        total_attempts=result.total_attempts,
        final_code=result.final_code,
        final_verification=VerifyResponse(**result.final_verification.to_dict()),
        attempts=[
            {
                "attempt": a.attempt_number,
                "code": a.code,
                "verification": a.verification.to_dict(),
                "timestamp": a.timestamp,
            }
            for a in result.attempts
        ],
    )


@app.get("/health", response_model=HealthResponse)
async def health():
    """Health check."""
    global _critic
    if _critic is None:
        return HealthResponse(status="not_initialized", model="", backend="")

    return HealthResponse(
        status="healthy",
        model=_critic.model_name,
        backend=_critic.backend_name,
    )
