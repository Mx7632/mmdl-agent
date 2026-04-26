from __future__ import annotations

from app.memory.checkpoint import (
    MemoryCheckpointStore,
    PostgresCheckpointStore,
    get_checkpoint_store,
)
from app.schemas.detection import DetectionTask
from app.memory.state import DetectionState


def test_get_checkpoint_store_falls_back_to_memory_without_database_url(monkeypatch):
    monkeypatch.setattr("app.memory.checkpoint.settings.checkpoint_backend", "postgres")
    monkeypatch.setattr("app.memory.checkpoint.settings.database_url", "")

    store = get_checkpoint_store()

    assert isinstance(store, MemoryCheckpointStore)
    assert store.backend_name == "memory"


def test_get_checkpoint_store_uses_postgres_when_configured(monkeypatch):
    class FakePostgresCheckpointStore:
        def __init__(self, dsn: str, schema: str):
            self.dsn = dsn
            self.schema = schema
            self.backend_name = "postgres"

    monkeypatch.setattr("app.memory.checkpoint.settings.checkpoint_backend", "postgres")
    monkeypatch.setattr("app.memory.checkpoint.settings.database_url", "postgresql://example")
    monkeypatch.setattr("app.memory.checkpoint.settings.database_schema", "agent")
    monkeypatch.setattr("app.memory.checkpoint.PostgresCheckpointStore", FakePostgresCheckpointStore)

    store = get_checkpoint_store()

    assert isinstance(store, FakePostgresCheckpointStore)
    assert store.dsn == "postgresql://example"
    assert store.schema == "agent"


def test_postgres_checkpoint_store_save_and_load(monkeypatch):
    class FakeRuntimeStore:
        def __init__(self, dsn: str, schema: str):
            self.saved = {}

        def save_checkpoint(self, task_id: str, state: dict):
            self.saved[task_id] = state

        def load_checkpoint(self, task_id: str):
            return self.saved.get(task_id)

    monkeypatch.setattr("app.memory.checkpoint.PostgresRuntimeStore", FakeRuntimeStore)

    task = DetectionTask(
        task_id="pg-checkpoint-test",
        asset_id="asset-001",
        start_time="2025-01-01T00:00:00Z",
        end_time="2025-01-01T01:00:00Z",
    )
    state = DetectionState(task=task, stage="chat")

    store = PostgresCheckpointStore("postgresql://example")
    store.save(state)
    loaded = store.load("pg-checkpoint-test")

    assert loaded is not None
    assert loaded["task"]["task_id"] == "pg-checkpoint-test"
    assert loaded["task"]["asset_id"] == "asset-001"
    assert store.backend_name == "postgres"
