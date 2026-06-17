"""Anvil web server — FastAPI-based HTTP/WebSocket interface for non-terminal users."""

from __future__ import annotations

import asyncio
import json
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import anvil
from anvil.core.config import AnvilConfig, ModelConfig
from anvil.core.engine import AnvilEngine
from anvil.core.session import Session
from anvil.onboarding import onboarding_manager


class RunRequest(BaseModel):
    task: str
    model: str = "local"
    max_iterations: int = 20
    verify: bool = True


class RunResponse(BaseModel):
    success: bool
    output: str
    error: str | None = None
    steps: int = 0
    session_id: str


class SessionInfo(BaseModel):
    id: str
    task: str
    success: bool
    created_at: str


# In-memory session store (replace with persistent storage in production)
_sessions: dict[str, Session] = {}


def create_app(config: AnvilConfig | None = None) -> FastAPI:
    """Create the FastAPI application."""
    app = FastAPI(title="Anvil Web", version="0.3.0")

    # CORS for local dev
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Serve static files
    static_dir = Path(__file__).parent / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "version": anvil.__version__}

    @app.get("/")
    def index() -> HTMLResponse:
        index_path = static_dir / "index.html"
        if index_path.exists():
            return HTMLResponse(index_path.read_text())
        return HTMLResponse("<h1>Anvil Web</h1><p>index.html not found</p>")

    @app.post("/run", response_model=RunResponse)
    def run_task(req: RunRequest) -> RunResponse:
        """Execute a task synchronously and return the result."""
        cfg = config or AnvilConfig(model=ModelConfig(model=req.model))
        cfg.verify.enabled = req.verify

        engine = AnvilEngine(cfg)
        result = engine.run(req.task, max_iterations=req.max_iterations)

        session_id = str(uuid.uuid4())
        if result.session:
            _sessions[session_id] = result.session

        return RunResponse(
            success=result.success,
            output=result.output or "",
            error=result.error,
            steps=len(result.session.steps) if result.session else 0,
            session_id=session_id,
        )

    @app.get("/sessions")
    def list_sessions() -> list[SessionInfo]:
        """List recent sessions."""
        return [
            SessionInfo(
                id=sid,
                task=sess.task,
                success=sess.stats.successful_steps > 0,
                created_at=str(sess.created_at) if hasattr(sess, "created_at") else "",
            )
            for sid, sess in list(_sessions.items())[-50:]
        ]

    @app.websocket("/stream")
    async def stream_task(websocket: WebSocket) -> None:
        """WebSocket endpoint for streaming task execution."""
        await websocket.accept()
        try:
            # Receive task request
            data = await websocket.receive_json()
            task = data.get("task", "")
            model = data.get("model", "local")
            max_iterations = data.get("max_iterations", 20)

            await websocket.send_json({"type": "status", "message": "Starting..."})

            cfg = config or AnvilConfig(model=ModelConfig(model=model))
            engine = AnvilEngine(cfg)

            # Run in a thread to avoid blocking the event loop
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, lambda: engine.run(task, max_iterations=max_iterations)
            )

            # Stream final result
            await websocket.send_json({
                "type": "result",
                "success": result.success,
                "output": result.output or "",
                "error": result.error,
                "steps": len(result.session.steps) if result.session else 0,
            })

        except WebSocketDisconnect:
            pass
        except Exception as e:
            await websocket.send_json({"type": "error", "message": str(e)})
        finally:
            await websocket.close()

    @app.get("/api/onboarding/status")
    def get_onboarding_status() -> dict[str, Any]:
        """Get onboarding status for the current user."""
        return {
            "should_show_onboarding": onboarding_manager.should_show_onboarding(),
            "completed_tours": onboarding_manager.get_completed_tours(),
            "recommended_tour": onboarding_manager.get_recommended_tour().id if onboarding_manager.get_recommended_tour() else None,
        }

    @app.get("/api/onboarding/tours")
    def list_onboarding_tours() -> list[dict[str, Any]]:
        """List all available onboarding tours."""
        tours = onboarding_manager.list_tours()
        return [
            {
                "id": tour.id,
                "name": tour.name,
                "description": tour.description,
                "steps": len(tour.steps),
                "completed": onboarding_manager.is_tour_completed(tour.id),
            }
            for tour in tours
        ]

    @app.post("/api/onboarding/tours/{tour_id}/start")
    def start_onboarding_tour(tour_id: str) -> dict[str, Any]:
        """Start an onboarding tour."""
        tour = onboarding_manager.start_tour(tour_id)
        if not tour:
            return {"error": "Tour not found"}
        return {
            "id": tour.id,
            "name": tour.name,
            "current_step": 0,
            "steps": tour.steps,
        }

    return app


# Default app instance
app = create_app()


def main(host: str = "127.0.0.1", port: int = 8000) -> None:
    """Run the web server."""
    import uvicorn

    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
