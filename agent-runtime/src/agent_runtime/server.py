"""FastAPI server — HTTP API for agent runtime."""

from __future__ import annotations


from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .daemon import AgentDaemon
from .models import (
    CheckpointInfo,
    HealthResponse,
    MemoryRetrieveResponse,
    MemoryStoreRequest,
    SessionCreate,
    SessionResume,
    SessionState,
)


def create_app(daemon: AgentDaemon) -> FastAPI:
    app = FastAPI(title="AgentRuntime", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    sm = daemon.session_manager

    @app.get("/health", response_model=HealthResponse)
    async def health():
        return daemon.health()

    @app.post("/sessions", response_model=SessionState, status_code=201)
    async def create_session(body: SessionCreate):
        state = sm.create_session(
            name=body.name,
            model=body.model,
            config={
                "system_prompt": body.system_prompt,
                "tools": body.tools,
            },
        )
        return state

    @app.get("/sessions", response_model=list[SessionState])
    async def list_sessions():
        return sm.list_sessions()

    @app.get("/sessions/{session_id}", response_model=SessionState)
    async def get_session(session_id: str):
        try:
            return sm.get_session_status(session_id)
        except Exception:
            raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    @app.post("/sessions/{session_id}/start", response_model=SessionState)
    async def start_session(session_id: str):
        try:
            return await sm.start_session(session_id)
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    @app.post("/sessions/{session_id}/pause", response_model=SessionState)
    async def pause_session(session_id: str):
        try:
            return await sm.pause_session(session_id)
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    @app.post("/sessions/{session_id}/resume", response_model=SessionState)
    async def resume_session(session_id: str, body: SessionResume | None = None):
        checkpoint_id = body.checkpoint_id if body else None
        try:
            return await sm.resume_session(session_id, checkpoint_id=checkpoint_id)
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    @app.post("/sessions/{session_id}/stop", response_model=SessionState)
    async def stop_session(session_id: str):
        try:
            return await sm.stop_session(session_id)
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    @app.get("/sessions/{session_id}/memory")
    async def get_memory(session_id: str, key: str | None = None):
        mem = sm.get_memory_store()
        if key:
            entry = mem.retrieve(key)
            if entry is None:
                raise HTTPException(status_code=404, detail=f"Memory key {key} not found")
            return MemoryRetrieveResponse(key=entry.key, value=entry.value, timestamp=entry.timestamp)
        return {"keys": mem.list_keys()}

    @app.post("/sessions/{session_id}/memory", status_code=201)
    async def store_memory(session_id: str, body: MemoryStoreRequest):
        mem = sm.get_memory_store()
        mem.store(key=body.key, value=body.value)
        return {"status": "stored", "key": body.key}

    @app.get("/sessions/{session_id}/checkpoints", response_model=list[CheckpointInfo])
    async def list_checkpoints(session_id: str):
        serializer = sm.get_state_serializer()
        return serializer.list_checkpoints(session_id)

    @app.post("/sessions/{session_id}/checkpoints", response_model=CheckpointInfo, status_code=201)
    async def create_checkpoint(session_id: str, label: str | None = None):
        serializer = sm.get_state_serializer()
        try:
            return serializer.create_checkpoint(session_id, label=label)
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))

    return app
