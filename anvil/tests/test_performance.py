"""Performance tests for Anvil."""

import time
import pytest
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from fastapi.testclient import TestClient
from anvil.api.server import app


@pytest.fixture
def client():
    return TestClient(app)


class TestPerformance:
    def test_api_response_time(self, client):
        start = time.time()
        resp = client.get("/api/health")
        assert resp.status_code == 200
        assert time.time() - start < 0.1

    def test_auth_response_time(self, client):
        start = time.time()
        resp = client.post("/api/auth/login", json={"email": "x@x.com", "password": "x"})
        assert resp.status_code in [200, 401]
        assert time.time() - start < 0.5

    def test_concurrent_api_requests(self, client):
        with ThreadPoolExecutor(max_workers=5) as ex:
            results = [f.result() for f in [ex.submit(lambda: client.get("/api/health")) for _ in range(10)]]
        assert all(r.status_code == 200 for r in results)

    def test_search_performance(self):
        from anvil.codebase.indexer import CodebaseIndex
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            for i in range(100):
                (p / f"f{i}.py").write_text(f"def func{i}(): pass")
            idx = CodebaseIndex(p)
            t = time.time(); idx.index(); t1 = time.time() - t
            t = time.time(); r = idx.search("func", limit=10); t2 = time.time() - t
            assert t1 < 5.0 and t2 < 0.5 and len(r) > 0

    def test_memory_performance(self):
        from anvil.memory.manager import MemoryManager, MemoryCategory
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            m = MemoryManager(memory_dir=Path(tmp))
            t = time.time()
            for i in range(100):
                m.add(category=MemoryCategory.FACT, content=f"Fact {i}", importance=0.5)
            t1 = time.time() - t
            t = time.time(); m.recall("fact", limit=10); t2 = time.time() - t
            assert t1 < 1.0 and t2 < 0.1

    def test_extension_load_performance(self):
        from anvil.extensions.manager import ExtensionManager
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            for i in range(10):
                d = p / f"ext{i}"; d.mkdir()
                (d / "extension.json").write_text(f'{{"name":"e{i}","version":"1.0","description":"t"}}')
                (d / "main.py").write_text(f"def tool{i}(): pass")
            mgr = ExtensionManager(extensions_dir=p)
            t = time.time(); e = mgr.list_extensions(); t1 = time.time() - t
            assert t1 < 0.5 and len(e) == 10

    def test_db_operations_performance(self):
        from anvil.api.database import DatabaseManager, DBUser
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            db = DatabaseManager(Path(tmp)/"test.db")
            t = time.time()
            for i in range(100):
                db.create_user(DBUser(id=f"u{i}", email=f"u{i}@t.com", username=f"u{i}", hashed_password="h", created_at="2026-01-01T00:00:00"))
            t1 = time.time() - t
            t = time.time(); u = db.get_user_by_email("u50@t.com"); t2 = time.time() - t
            assert t1 < 1.0 and t2 < 0.1 and u is not None
