"""FastAPI inference server for ShellWhisperer.

Endpoints:
  POST /predict          — Natural language → shell command
  POST /predict/batch    — Batch prediction
  GET  /health           — Health check
  GET  /info             — Model info
  WebSocket /ws/stream   — Streaming prediction
"""

from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from shell_whisperer.inference import ShellWhisperer

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Global model holder
# ---------------------------------------------------------------------------

_model: ShellWhisperer | None = None
_model_config: dict[str, Any] = {}


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------


class PredictRequest(BaseModel):
    """Single prediction request."""

    prompt: str = Field(..., min_length=1, description="Natural language description")
    working_directory: str | None = Field(None, description="Current working directory")
    os_type: str = Field("linux", description="Target OS: linux, macos, windows")
    recent_history: list[str] = Field(default_factory=list, description="Recent commands")


class PredictResponse(BaseModel):
    """Single prediction response."""

    command: str
    raw_output: str
    latency_ms: float
    backend: str
    os_type: str
    safety_warnings: list[str] = []


class BatchPredictRequest(BaseModel):
    """Batch prediction request."""

    prompts: list[str] = Field(..., min_length=1, description="List of natural language prompts")
    working_directory: str | None = Field(None)
    os_type: str = Field("linux")
    recent_history: list[str] = Field(default_factory=list)


class BatchPredictResponse(BaseModel):
    """Batch prediction response."""

    predictions: list[PredictResponse]
    total_latency_ms: float


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    model_loaded: bool
    backend: str | None = None
    uptime_seconds: float = 0.0


class InfoResponse(BaseModel):
    """Model info response."""

    model_path: str | None = None
    backend: str | None = None
    os_type: str = "linux"
    max_new_tokens: int = 256
    temperature: float = 0.1
    supported_os_types: list[str] = ["linux", "macos", "windows"]


# ---------------------------------------------------------------------------
# App lifecycle
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load model on startup, free on shutdown."""
    global _model, _model_config
    if _model_config:
        from shell_whisperer.inference import ShellWhisperer

        _model = ShellWhisperer(**_model_config)
        _model.load_model()
        logger.info("Model loaded: %s", _model_config)
    yield
    if _model is not None:
        _model.unload()
        _model = None
        logger.info("Model unloaded")


app = FastAPI(
    title="ShellWhisperer",
    description="Natural language to shell command API — 1.5B edge-native model",
    version="0.1.0",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.post("/predict", response_model=PredictResponse)
async def predict(request: PredictRequest) -> PredictResponse:
    """Convert natural language to a shell command."""
    if _model is None:
        return PredictResponse(
            command="",
            raw_output="Error: model not loaded",
            latency_ms=0,
            backend="none",
            os_type=request.os_type,
            safety_warnings=["Model not loaded"],
        )

    result = _model.predict(
        prompt=request.prompt,
        working_directory=request.working_directory,
        recent_history=request.recent_history or None,
        os_type=request.os_type,
    )

    return PredictResponse(**result.to_dict())


@app.post("/predict/batch", response_model=BatchPredictResponse)
async def predict_batch(request: BatchPredictRequest) -> BatchPredictResponse:
    """Convert multiple natural language prompts to shell commands."""
    if _model is None:
        return BatchPredictResponse(
            predictions=[],
            total_latency_ms=0,
        )

    start = time.monotonic()
    results = _model.predict_batch(
        prompts=request.prompts,
        working_directory=request.working_directory,
        recent_history=request.recent_history or None,
        os_type=request.os_type,
    )
    total_ms = (time.monotonic() - start) * 1000

    predictions = [PredictResponse(**r.to_dict()) for r in results]
    return BatchPredictResponse(predictions=predictions, total_latency_ms=total_ms)


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Health check endpoint."""
    return HealthResponse(
        status="ok" if _model is not None else "no_model",
        model_loaded=_model is not None,
        backend=_model.backend.value if _model else None,
    )


@app.get("/info", response_model=InfoResponse)
async def info() -> InfoResponse:
    """Get model information."""
    if _model is None:
        return InfoResponse()
    return InfoResponse(
        model_path=_model.model_path,
        backend=_model.backend.value,
        os_type=_model.os_type,
        max_new_tokens=_model.max_new_tokens,
        temperature=_model.temperature,
    )


@app.websocket("/ws/stream")
async def stream_predict(websocket: WebSocket) -> None:
    """Stream prediction tokens via WebSocket.

    Client sends JSON: {"prompt": "...", "os_type": "linux", "working_directory": "/home/user"}
    Server streams back tokens one at a time as JSON: {"token": "..."}
    Server sends final message: {"done": true, "command": "..."}
    """
    await websocket.accept()

    try:
        while True:
            data = await websocket.receive_json()
            prompt = data.get("prompt", "")
            os_type = data.get("os_type", "linux")
            working_directory = data.get("working_directory")
            recent_history = data.get("recent_history", [])

            if not prompt:
                await websocket.send_json({"error": "prompt is required"})
                continue

            if _model is None:
                await websocket.send_json({"error": "model not loaded"})
                continue

            full_command = ""
            try:
                for token in _model.predict_stream(
                    prompt=prompt,
                    working_directory=working_directory,
                    recent_history=recent_history or None,
                    os_type=os_type,
                ):
                    full_command += token
                    await websocket.send_json({"token": token})
            except Exception as e:
                logger.error("Streaming error: %s", e)
                await websocket.send_json({"error": str(e)})

            # Send completion
            from shell_whisperer.inference import _check_safety, _clean_output

            command = _clean_output(full_command)
            safety_warnings = _check_safety(command)

            await websocket.send_json({
                "done": True,
                "command": command,
                "safety_warnings": safety_warnings,
            })

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.error("WebSocket error: %s", e)
        try:
            await websocket.close()
        except Exception:
            pass


def create_app(
    model_path: str | None = None,
    backend: str = "transformers",
    os_type: str = "linux",
    max_new_tokens: int = 256,
    temperature: float = 0.1,
) -> FastAPI:
    """Create a configured FastAPI application.

    Args:
        model_path: Path to the model.
        backend: Inference backend ('transformers', 'onnx', 'llama_cpp').
        os_type: Default OS type.
        max_new_tokens: Maximum tokens to generate.
        temperature: Sampling temperature.

    Returns:
        Configured FastAPI app.
    """
    global _model_config

    _model_config = {
        "model_path": model_path,
        "backend": backend,
        "os_type": os_type,
        "max_new_tokens": max_new_tokens,
        "temperature": temperature,
    }

    return app
