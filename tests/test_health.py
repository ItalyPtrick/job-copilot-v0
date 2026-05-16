import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from fastapi.testclient import TestClient

from app.main import app


class _FakeConnection:
    def __init__(self, should_fail: bool = False):
        self.should_fail = should_fail
        self.executed_statements: list[str] = []

    def __enter__(self):
        if self.should_fail:
            raise RuntimeError("postgres down")
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, statement):
        self.executed_statements.append(str(statement))


class _FakeEngine:
    def __init__(self, should_fail: bool = False):
        self.connection = _FakeConnection(should_fail=should_fail)

    def connect(self):
        return self.connection


class _FakeRedis:
    def __init__(self, should_fail: bool = False):
        self.should_fail = should_fail
        self.ping_called = False

    def ping(self):
        self.ping_called = True
        if self.should_fail:
            raise RuntimeError("redis down")
        return True


def test_health_returns_200_when_postgres_and_redis_ok(monkeypatch):
    fake_engine = _FakeEngine()
    fake_redis = _FakeRedis()
    monkeypatch.setattr("app.main.engine", fake_engine)
    monkeypatch.setattr("app.main.redis_client", fake_redis)

    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "healthy",
        "postgres": "ok",
        "redis": "ok",
    }
    assert fake_engine.connection.executed_statements == ["SELECT 1"]
    assert fake_redis.ping_called is True


def test_health_returns_503_when_postgres_fails(monkeypatch):
    fake_redis = _FakeRedis()
    monkeypatch.setattr("app.main.engine", _FakeEngine(should_fail=True))
    monkeypatch.setattr("app.main.redis_client", fake_redis)

    response = TestClient(app).get("/health")

    assert response.status_code == 503
    data = response.json()
    assert data["status"] == "unhealthy"
    assert data["postgres"] == "error: RuntimeError"
    assert data["redis"] == "ok"
    assert fake_redis.ping_called is True


def test_health_returns_503_when_redis_fails(monkeypatch):
    fake_engine = _FakeEngine()
    monkeypatch.setattr("app.main.engine", fake_engine)
    monkeypatch.setattr("app.main.redis_client", _FakeRedis(should_fail=True))

    response = TestClient(app).get("/health")

    assert response.status_code == 503
    data = response.json()
    assert data["status"] == "unhealthy"
    assert data["postgres"] == "ok"
    assert data["redis"] == "error: RuntimeError"
    assert fake_engine.connection.executed_statements == ["SELECT 1"]
