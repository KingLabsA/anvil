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

            model_name = req.model

            # Ollama models: call directly via HTTP
            if model_name.startswith("ollama:") or model_name in ("ollama", "local", "llama"):
                import httpx as _httpx
                ollama_model = model_name.replace("ollama:", "") if ":" in model_name else "shellwhisperer"
                client = _httpx.Client(timeout=120.0)
                payload = {
                    "model": ollama_model,
                    "messages": [
                        {"role": "system", "content": "You are Anvil, an expert AI coding assistant. Write clean, production-ready code. Explain your reasoning clearly."},
                        {"role": "user", "content": req.message},
                    ],
                    "stream": False,
                }
                resp = client.post("http://localhost:11434/api/chat", json=payload)
                resp.raise_for_status()
                data = resp.json()
                content = data.get("message", {}).get("content", "")
                return ChatResponse(response=content, success=True)

            # Check if model looks like an Ollama model name (contains / or is a known name)
            if "/" in model_name and not model_name.startswith(("gpt-", "claude", "gemini", "deepseek", "groq/", "mistral")):
                import httpx as _httpx
                client = _httpx.Client(timeout=120.0)
                payload = {
                    "model": model_name,
                    "messages": [
                        {"role": "system", "content": "You are Anvil, an expert AI coding assistant. Write clean, production-ready code. Explain your reasoning clearly."},
                        {"role": "user", "content": req.message},
                    ],
                    "stream": False,
                }
                resp = client.post("http://localhost:11434/api/chat", json=payload)
                resp.raise_for_status()
                data = resp.json()
                content = data.get("message", {}).get("content", "")
                return ChatResponse(response=content, success=True)

            from anvil.models.registry import ModelRegistry, Message
            model = ModelRegistry.create(model_name)

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
        providers = ModelRegistry.list_providers()
        # Add local Ollama models
        try:
            import httpx
            resp = httpx.get("http://localhost:11434/api/tags", timeout=3.0)
            if resp.status_code == 200:
                data = resp.json()
                for m in data.get("models", []):
                    providers.append({
                        "provider": "ollama",
                        "model": m["name"],
                        "display_name": f"Ollama: {m['name']}",
                        "size_gb": round(m.get("size", 0) / 1e9, 1),
                    })
        except Exception:
            pass
        return providers

    @app.get("/ollama/models")
    def ollama_models() -> list[dict]:
        """List available Ollama models."""
        try:
            import httpx
            resp = httpx.get("http://localhost:11434/api/tags", timeout=3.0)
            if resp.status_code == 200:
                data = resp.json()
                return [
                    {"name": m["name"], "size_gb": round(m.get("size", 0) / 1e9, 1)}
                    for m in data.get("models", [])
                ]
        except Exception:
            pass
        return []

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

    # ─── Subagents ───
    from anvil.core.subagents import SubagentManager
    _subagent_mgr = SubagentManager()

    @app.post("/subagent/spawn")
    def spawn_subagent(task: str, agent: str = "general", model: str = "gpt-4o-mini", max_turns: int = 20) -> dict:
        task_id = _subagent_mgr.spawn(task, agent_name=agent, model=model, max_turns=max_turns)
        return {"task_id": task_id, "status": "spawned"}

    @app.post("/subagent/execute/{task_id}")
    def execute_subagent(task_id: str) -> dict:
        result = _subagent_mgr.execute(task_id)
        return {
            "id": result.id, "output": result.output, "status": result.status.value,
            "duration_ms": result.duration_ms, "error": result.error,
        }

    @app.get("/subagent/active")
    def list_active_subagents() -> list[dict]:
        return [{"id": t.id, "task": t.task, "agent": t.agent_name} for t in _subagent_mgr.get_active()]

    @app.get("/subagent/history")
    def subagent_history() -> list[dict]:
        return [
            {"id": r.id, "task": r.task, "status": r.status.value, "duration_ms": r.duration_ms}
            for r in _subagent_mgr.get_history()
        ]

    @app.post("/subagent/fan-out")
    def fan_out(tasks: list[str], agent: str = "general", model: str = "gpt-4o-mini") -> dict:
        ids = _subagent_mgr.fan_out(tasks, agent_name=agent, model=model)
        return {"task_ids": ids, "count": len(ids)}

    # ─── Checkpoints ───
    from anvil.core.checkpoint import CheckpointManager
    _checkpoint_mgr = CheckpointManager()

    @app.post("/checkpoint/create")
    def create_checkpoint(message: str) -> dict:
        cp = _checkpoint_mgr.create_checkpoint(message)
        return {"id": cp.id, "hash": cp.hash, "message": cp.message, "files": cp.files_changed}

    @app.post("/checkpoint/undo")
    def undo_checkpoint() -> dict:
        cp = _checkpoint_mgr.undo()
        if cp:
            return {"id": cp.id, "hash": cp.hash, "message": cp.message}
        return {"error": "Nothing to undo"}

    @app.post("/checkpoint/redo")
    def redo_checkpoint() -> dict:
        cp = _checkpoint_mgr.redo()
        if cp:
            return {"id": cp.id, "hash": cp.hash, "message": cp.message}
        return {"error": "Nothing to redo"}

    @app.get("/checkpoint/list")
    def list_checkpoints() -> list[dict]:
        return _checkpoint_mgr.get_checkpoints()

    @app.get("/checkpoint/diff/{checkpoint_id}")
    def checkpoint_diff(checkpoint_id: str) -> str:
        return _checkpoint_mgr.get_diff(checkpoint_id)

    # ─── Plan/Act ───
    from anvil.core.plan_act import PlanActController, AgentMode
    _plan_ctrl = PlanActController()

    @app.get("/plan/current")
    def get_plan() -> dict:
        return _plan_ctrl.get_plan_json()

    @app.post("/plan/create")
    def create_plan(task: str, steps: list[dict]) -> dict:
        plan = _plan_ctrl.create_plan(task, steps)
        return {"task": plan.task, "steps": len(plan.steps), "approved": plan.approved}

    @app.post("/plan/approve")
    def approve_plan() -> dict:
        msg = _plan_ctrl.approve_plan()
        return {"message": msg, "mode": _plan_ctrl.mode.value}

    @app.post("/plan/reject")
    def reject_plan() -> dict:
        msg = _plan_ctrl.reject_plan()
        return {"message": msg}

    @app.get("/plan/mode")
    def get_mode() -> dict:
        return {"mode": _plan_ctrl.mode.value}

    @app.post("/plan/mode/{mode}")
    def set_mode(mode: str) -> dict:
        _plan_ctrl.set_mode(AgentMode(mode))
        return {"mode": _plan_ctrl.mode.value}

    # ─── File Explorer ───
    @app.get("/files/list")
    def list_files(path: str = ".") -> list[dict]:
        """List files in directory."""
        target = Path(path).resolve()
        if not target.exists():
            return []
        items = []
        try:
            for item in sorted(target.iterdir()):
                if item.name.startswith(".") or item.name == "__pycache__":
                    continue
                items.append({
                    "name": item.name,
                    "path": str(item),
                    "type": "directory" if item.is_dir() else "file",
                    "size": item.stat().st_size if item.is_file() else 0,
                })
        except PermissionError:
            pass
        return items

    @app.get("/files/read")
    def read_file(path: str) -> dict:
        """Read file content."""
        target = Path(path).resolve()
        if not target.exists():
            return {"error": "File not found"}
        try:
            content = target.read_text(errors="replace")
            return {"path": str(target), "content": content, "lines": content.count("\n") + 1}
        except Exception as e:
            return {"error": str(e)}

    @app.get("/files/tree")
    def file_tree(path: str = ".", max_depth: int = 3) -> dict:
        """Get file tree."""
        def _build(p: Path, depth: int) -> dict:
            if depth > max_depth:
                return {"name": p.name, "type": "truncated"}
            if p.is_dir():
                children = []
                try:
                    for child in sorted(p.iterdir()):
                        if child.name.startswith(".") or child.name == "__pycache__" or child.name == "node_modules":
                            continue
                        children.append(_build(child, depth + 1))
                except PermissionError:
                    pass
                return {"name": p.name, "type": "directory", "children": children}
            return {"name": p.name, "type": "file", "size": p.stat().st_size}

        return _build(Path(path).resolve(), 0)

    # ─── Streaming Chat (WebSocket) ───
    @app.websocket("/ws/chat")
    async def websocket_chat(websocket: WebSocket):
        await websocket.accept()
        try:
            while True:
                data = await websocket.receive_json()
                model_name = data.get("model", "shellwhisperer")
                message = data.get("message", "")

                # Send thinking
                await websocket.send_json({"type": "thinking", "content": "Thinking..."})

                # Call model
                try:
                    if model_name.startswith(("fableforge", "mythos", "shellwhisperer")) or "/" in model_name:
                        import httpx
                        client = httpx.Client(timeout=120.0)
                        resp = client.post("http://localhost:11434/api/chat", json={
                            "model": model_name,
                            "messages": [
                                {"role": "system", "content": "You are Anvil, an expert AI coding assistant."},
                                {"role": "user", "content": message},
                            ],
                            "stream": False,
                        })
                        resp.raise_for_status()
                        result = resp.json()
                        content = result.get("message", {}).get("content", "")
                        await websocket.send_json({"type": "response", "content": content, "success": True})
                    else:
                        from anvil.models.registry import ModelRegistry, Message
                        model = ModelRegistry.create(model_name)
                        messages = [
                            Message(role="system", content="You are Anvil, an expert AI coding assistant."),
                            Message(role="user", content=message),
                        ]
                        response = model.complete(messages, temperature=0.7)
                        await websocket.send_json({"type": "response", "content": response.content, "success": True})
                except Exception as e:
                    await websocket.send_json({"type": "response", "content": "", "success": False, "error": str(e)})
        except WebSocketDisconnect:
            pass

    return app


app = create_app()


def main(host: str = "127.0.0.1", port: int = 8000) -> None:
    import uvicorn
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
