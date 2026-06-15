"""Memory system: short-term (in-process) and long-term (persistent file) stores."""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import aiofiles


class MemoryStore(ABC):
    @abstractmethod
    async def store(self, key: str, value: Any, namespace: str = "default") -> None:
        ...

    @abstractmethod
    async def retrieve(self, key: str, namespace: str = "default") -> Any | None:
        ...

    @abstractmethod
    async def search(self, query: str, namespace: str = "default", limit: int = 10) -> list[dict[str, Any]]:
        ...

    @abstractmethod
    async def delete(self, key: str, namespace: str = "default") -> bool:
        ...

    @abstractmethod
    async def list_keys(self, namespace: str = "default") -> list[str]:
        ...


class InMemoryStore(MemoryStore):
    def __init__(self) -> None:
        self._store: dict[str, dict[str, dict[str, Any]]] = {}

    def _ns(self, namespace: str) -> dict[str, dict[str, Any]]:
        if namespace not in self._store:
            self._store[namespace] = {}
        return self._store[namespace]

    async def store(self, key: str, value: Any, namespace: str = "default") -> None:
        ns = self._ns(namespace)
        ns[key] = {
            "value": value,
            "stored_at": datetime.now(UTC).isoformat(),
            "access_count": ns.get(key, {}).get("access_count", 0),
        }

    async def retrieve(self, key: str, namespace: str = "default") -> Any | None:
        ns = self._ns(namespace)
        entry = ns.get(key)
        if entry is None:
            return None
        entry["access_count"] = entry.get("access_count", 0) + 1
        return entry["value"]

    async def search(self, query: str, namespace: str = "default", limit: int = 10) -> list[dict[str, Any]]:
        ns = self._ns(namespace)
        query_lower = query.lower()
        results = []
        for key, entry in ns.items():
            value_str = str(entry.get("value", "")).lower()
            if query_lower in value_str or query_lower in key.lower():
                results.append({"key": key, **entry})
        results.sort(key=lambda r: r.get("access_count", 0), reverse=True)
        return results[:limit]

    async def delete(self, key: str, namespace: str = "default") -> bool:
        ns = self._ns(namespace)
        if key in ns:
            del ns[key]
            return True
        return False

    async def list_keys(self, namespace: str = "default") -> list[str]:
        return list(self._ns(namespace).keys())


class FileStore(MemoryStore):
    def __init__(self, base_dir: str = ".verifyloop_memory") -> None:
        self.base_dir = Path(base_dir)
        self._cache: dict[str, dict[str, dict[str, Any]]] = {}

    def _ns_path(self, namespace: str) -> Path:
        return self.base_dir / f"{namespace}.json"

    async def _load_ns(self, namespace: str) -> dict[str, dict[str, Any]]:
        if namespace in self._cache:
            return self._cache[namespace]
        path = self._ns_path(namespace)
        if path.exists():
            async with aiofiles.open(path) as f:
                data = json.loads(await f.read())
            self._cache[namespace] = data
            return data
        self._cache[namespace] = {}
        return {}

    async def _save_ns(self, namespace: str, data: dict[str, dict[str, Any]]) -> None:
        self._cache[namespace] = data
        path = self._ns_path(namespace)
        path.parent.mkdir(parents=True, exist_ok=True)
        async with aiofiles.open(path, "w") as f:
            await f.write(json.dumps(data, indent=2, default=str))

    async def store(self, key: str, value: Any, namespace: str = "default") -> None:
        data = await self._load_ns(namespace)
        data[key] = {
            "value": value,
            "stored_at": datetime.now(UTC).isoformat(),
            "access_count": data.get(key, {}).get("access_count", 0),
        }
        await self._save_ns(namespace, data)

    async def retrieve(self, key: str, namespace: str = "default") -> Any | None:
        data = await self._load_ns(namespace)
        entry = data.get(key)
        if entry is None:
            return None
        entry["access_count"] = entry.get("access_count", 0) + 1
        await self._save_ns(namespace, data)
        return entry["value"]

    async def search(self, query: str, namespace: str = "default", limit: int = 10) -> list[dict[str, Any]]:
        data = await self._load_ns(namespace)
        query_lower = query.lower()
        results = []
        for key, entry in data.items():
            value_str = str(entry.get("value", "")).lower()
            if query_lower in value_str or query_lower in key.lower():
                results.append({"key": key, **entry})
        results.sort(key=lambda r: r.get("access_count", 0), reverse=True)
        return results[:limit]

    async def delete(self, key: str, namespace: str = "default") -> bool:
        data = await self._load_ns(namespace)
        if key in data:
            del data[key]
            await self._save_ns(namespace, data)
            return True
        return False

    async def list_keys(self, namespace: str = "default") -> list[str]:
        data = await self._load_ns(namespace)
        return list(data.keys())


class ConversationContext:
    def __init__(self, memory: MemoryStore | None = None) -> None:
        self.memory = memory or InMemoryStore()
        self._messages: list[dict[str, str]] = []
        self._file_context: dict[str, str] = {}

    def add_message(self, role: str, content: str) -> None:
        self._messages.append({"role": role, "content": content})

    def get_messages(self) -> list[dict[str, str]]:
        return list(self._messages)

    def add_file_context(self, file_path: str, content: str) -> None:
        self._file_context[file_path] = content
        if self.memory:
            import asyncio as _asyncio
            try:
                loop = _asyncio.get_event_loop()
                if loop.is_running():
                    _asyncio.ensure_future(
                        self.memory.store(f"file:{file_path}", content, namespace="files")
                    )
                else:
                    loop.run_until_complete(
                        self.memory.store(f"file:{file_path}", content, namespace="files")
                    )
            except RuntimeError:
                pass

    def get_file_context(self, file_path: str) -> str | None:
        return self._file_context.get(file_path)

    def get_all_file_paths(self) -> list[str]:
        return list(self._file_context.keys())

    def build_context_string(self, max_files: int = 5) -> str:
        parts = []
        if self._messages:
            last_msg = self._messages[-1] if self._messages else {}
            parts.append(f"Last message: {last_msg.get('content', '')[:500]}")
        if self._file_context:
            for path, content in list(self._file_context.items())[:max_files]:
                preview = content[:300] + "..." if len(content) > 300 else content
                parts.append(f"File {path}:\n{preview}")
        return "\n\n".join(parts)
