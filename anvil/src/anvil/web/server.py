"""Anvil web server — FastAPI-based HTTP/WebSocket interface."""

from __future__ import annotations

import asyncio
import json
import uuid
import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import anvil
from anvil.core.config import AnvilConfig, ModelConfig
from anvil.core.engine import AnvilEngine
from anvil.core.session import Session


class RunRequest(BaseModel):
    task: str
    model: str = "gpt-4o-mini"
    max_iterations: int = 20
    verify: bool = True


class RunResponse(BaseModel):
    success: bool
    output: str
    error: str | None = None
    steps: int = 0
    session_id: str


class ChatRequest(BaseModel):
    message: str
    model: str = "gpt-4o-mini"
    workspace: str = "."


class ChatResponse(BaseModel):
    response: str
    success: bool
    error: str | None = None


class SettingsModel(BaseModel):
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    gemini_api_key: str | None = None
    deepseek_api_key: str | None = None
    groq_api_key: str | None = None
    mistral_api_key: str | None = None
    default_model: str = "gpt-4o-mini"
    workspace: str = "."


class SessionInfo(BaseModel):
    id: str
    task: str
    success: bool
    created_at: str


# Global state
_sessions: dict[str, Session] = {}
_settings = SettingsModel()
_engines: dict[str, AnvilEngine] = {}


def load_settings():
    """Load settings from ~/.anvil/settings.json"""
    global _settings
    settings_file = Path.home() / ".anvil" / "settings.json"
    if settings_file.exists():
        try:
            data = json.loads(settings_file.read_text())
            _settings = SettingsModel(**data)
        except:
            pass


def save_settings():
    """Save settings to ~/.anvil/settings.json"""
    settings_file = Path.home() / ".anvil" / "settings.json"
    settings_file.parent.mkdir(parents=True, exist_ok=True)
    settings_file.write_text(json.dumps(_settings.dict(), indent=2))


def get_engine(model: str) -> AnvilEngine:
    """Get or create a cached engine for the given model."""
    if model not in _engines:
        # Set API keys from settings
        if _settings.openai_api_key:
            os.environ["OPENAI_API_KEY"] = _settings.openai_api_key
        if _settings.anthropic_api_key:
            os.environ["ANTHROPIC_API_KEY"] = _settings.anthropic_api_key
        if _settings.gemini_api_key:
            os.environ["GEMINI_API_KEY"] = _settings.gemini_api_key
        if _settings.deepseek_api_key:
            os.environ["DEEPSEEK_API_KEY"] = _settings.deepseek_api_key
        if _settings.groq_api_key:
            os.environ["GROQ_API_KEY"] = _settings.groq_api_key
        if _settings.mistral_api_key:
            os.environ["MISTRAL_API_KEY"] = _settings.mistral_api_key

        cfg = AnvilConfig(model=ModelConfig(model=model))
        cfg.verify.enabled = True
        _engines[model] = AnvilEngine(cfg)
    
    return _engines[model]


def create_app(config: AnvilConfig | None = None) -> FastAPI:
    """Create the FastAPI application."""
    app = FastAPI(title="Anvil Web", version="0.3.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.on_event("startup")
    def startup():
        load_settings()

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
        """Execute a task synchronously."""
        try:
            # Set API keys from settings
            if _settings.openai_api_key:
                os.environ["OPENAI_API_KEY"] = _settings.openai_api_key
            if _settings.anthropic_api_key:
                os.environ["ANTHROPIC_API_KEY"] = _settings.anthropic_api_key
            if _settings.gemini_api_key:
                os.environ["GEMINI_API_KEY"] = _settings.gemini_api_key
            if _settings.deepseek_api_key:
                os.environ["DEEPSEEK_API_KEY"] = _settings.deepseek_api_key
            if _settings.groq_api_key:
                os.environ["GROQ_API_KEY"] = _settings.groq_api_key
            if _settings.mistral_api_key:
                os.environ["MISTRAL_API_KEY"] = _settings.mistral_api_key

            engine = get_engine(req.model)
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
        except Exception as e:
            return RunResponse(
                success=False,
                output="",
                error=str(e),
                steps=0,
                session_id="",
            )

    @app.post("/chat", response_model=ChatResponse)
    def chat(req: ChatRequest) -> ChatResponse:
        """Chat with Anvil — calls the model API directly."""
        try:
            # Set API keys from settings
            if _settings.openai_api_key:
                os.environ["OPENAI_API_KEY"] = _settings.openai_api_key
            if _settings.anthropic_api_key:
                os.environ["ANTHROPIC_API_KEY"] = _settings.anthropic_api_key
            if _settings.gemini_api_key:
                os.environ["GEMINI_API_KEY"] = _settings.gemini_api_key
            if _settings.deepseek_api_key:
                os.environ["DEEPSEEK_API_KEY"] = _settings.deepseek_api_key
            if _settings.groq_api_key:
                os.environ["GROQ_API_KEY"] = _settings.groq_api_key
            if _settings.mistral_api_key:
                os.environ["MISTRAL_API_KEY"] = _settings.mistral_api_key

            from anvil.models.registry import ModelRegistry, Message
            model = ModelRegistry.create(req.model)

            messages = [
                Message(role="system", content="You are Anvil, an expert AI coding assistant. Write clean, production-ready code. Explain your reasoning clearly."),
                Message(role="user", content=req.message),
            ]
            response = model.complete(messages, temperature=0.7)

            return ChatResponse(
                response=response.content,
                success=True,
                error=None,
            )
        except Exception as e:
            return ChatResponse(
                response="",
                success=False,
                error=str(e),
            )


    @app.get("/settings")
    def get_settings() -> dict:
        return _settings.dict()

    @app.post("/settings")
    def update_settings(settings: SettingsModel) -> dict:
        global _settings
        _settings = settings
        save_settings()
        _engines.clear()
        return {"status": "ok"}

    @app.get("/models")
    def list_models() -> list[dict]:
        from anvil.models.registry import ModelRegistry
        return ModelRegistry.list_providers()

    @app.get("/mcp/tools")
    def list_mcp_tools() -> list[dict]:
        from anvil.mcp.registry import MCPToolRegistry
        registry = MCPToolRegistry()
        return registry.get_available_tools()

    @app.get("/sessions")
    def list_sessions() -> list[SessionInfo]:
        return [
            SessionInfo(
                id=sid,
                task=sess.task,
                success=sess.stats.successful_steps > 0,
                created_at=str(sess.created_at) if hasattr(sess, "created_at") else "",
            )
            for sid, sess in list(_sessions.items())[-50:]
        ]

    return app


app = create_app()


def main(host: str = "127.0.0.1", port: int = 8000) -> None:
    import uvicorn
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
