from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from app.core import runtime as runtime_module


def test_get_configured_checkpoint_backend_falls_back_to_memory_without_database_url(monkeypatch):
    monkeypatch.setattr(runtime_module.settings, "checkpoint_backend", "postgres")
    monkeypatch.setattr(runtime_module.settings, "database_url", "")

    backend = runtime_module.get_configured_checkpoint_backend()

    assert backend == "memory"


def test_get_configured_checkpoint_backend_uses_postgres_when_available(monkeypatch):
    monkeypatch.setattr(runtime_module.settings, "checkpoint_backend", "postgres")
    monkeypatch.setattr(runtime_module.settings, "database_url", "postgresql://example")
    monkeypatch.setattr(runtime_module, "AsyncPostgresSaver", object())

    backend = runtime_module.get_configured_checkpoint_backend()

    assert backend == "postgres"


def test_graph_session_uses_memory_saver_when_postgres_not_configured(monkeypatch):
    sentinel_graph = object()

    def fake_build_graph(*, checkpointer=None, store=None):
        assert checkpointer is runtime_module._MEMORY_SAVER
        assert store is None
        return sentinel_graph

    monkeypatch.setattr(runtime_module.settings, "checkpoint_backend", "memory")
    monkeypatch.setattr(runtime_module, "build_graph", fake_build_graph)

    async def runner():
        async with runtime_module.graph_session("task-001") as (graph, config, backend):
            assert graph is sentinel_graph
            assert backend == "memory"
            assert config == {"configurable": {"thread_id": "task-001"}}

    asyncio.run(runner())


def test_graph_session_uses_async_postgres_saver(monkeypatch):
    sentinel_graph = object()
    setup_called = False

    def fake_build_graph(*, checkpointer=None, store=None):
        assert getattr(checkpointer, "_marker", None) == "fake-postgres-saver"
        assert store is None
        return sentinel_graph

    monkeypatch.setattr(runtime_module.settings, "checkpoint_backend", "postgres")
    monkeypatch.setattr(runtime_module.settings, "database_url", "postgresql://example")
    monkeypatch.setattr(runtime_module, "build_graph", fake_build_graph)

    @asynccontextmanager
    async def wrapped_from_conn_string(conn_string: str):
        assert conn_string == "postgresql://example"

        class FakeSaver:
            _marker = "fake-postgres-saver"

            async def setup(self):
                nonlocal setup_called
                setup_called = True

        yield FakeSaver()

    class WrappedAsyncPostgresSaver:
        from_conn_string = staticmethod(wrapped_from_conn_string)

    monkeypatch.setattr(runtime_module, "AsyncPostgresSaver", WrappedAsyncPostgresSaver)

    async def runner():
        async with runtime_module.graph_session("task-002") as (graph, config, backend):
            assert graph is sentinel_graph
            assert backend == "postgres"
            assert config == {"configurable": {"thread_id": "task-002"}}

    asyncio.run(runner())

    assert setup_called is True


def test_persist_runtime_state_only_writes_for_postgres(monkeypatch):
    calls: list[tuple[str, str, str, dict]] = []

    class FakeRuntimeStore:
        def __init__(self, dsn: str, schema: str):
            self.dsn = dsn
            self.schema = schema

        def save_checkpoint(self, task_id: str, state: dict):
            calls.append((self.dsn, self.schema, task_id, state))

    monkeypatch.setattr(runtime_module.settings, "database_url", "postgresql://example")
    monkeypatch.setattr(runtime_module.settings, "database_schema", "agent")
    monkeypatch.setattr(runtime_module, "PostgresRuntimeStore", FakeRuntimeStore)

    runtime_module.persist_runtime_state("task-003", {"stage": "chat"}, backend="memory")
    runtime_module.persist_runtime_state("task-003", {"stage": "chat"}, backend="postgres")

    assert calls == [("postgresql://example", "agent", "task-003", {"stage": "chat"})]
