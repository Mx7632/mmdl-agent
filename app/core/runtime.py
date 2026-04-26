"""
Runtime helpers for LangGraph persistence and PostgreSQL-backed durable state.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from langgraph.checkpoint.memory import InMemorySaver

from app.config.settings import settings
from app.core.graph import build_graph
from app.storage.postgres import PostgresRuntimeStore

logger = logging.getLogger(__name__)

try:
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
except ImportError:  # pragma: no cover - optional dependency
    AsyncPostgresSaver = None


_MEMORY_SAVER = InMemorySaver()


def get_configured_checkpoint_backend() -> str:
    """Return the effective checkpoint backend for graph execution."""
    backend = (settings.checkpoint_backend or "memory").strip().lower()
    if backend != "postgres":
        return "memory"
    if not settings.database_url:
        logger.warning(
            "APP_CHECKPOINT_BACKEND=postgres but APP_DATABASE_URL is empty; fallback to memory"
        )
        return "memory"
    if AsyncPostgresSaver is None:
        logger.warning(
            "langgraph-checkpoint-postgres is not installed; fallback to memory checkpointer"
        )
        return "memory"
    return "postgres"


def build_thread_config(task_id: str) -> dict[str, Any]:
    """Build the LangGraph runnable config for a task thread."""
    return {"configurable": {"thread_id": task_id}}


@asynccontextmanager
async def graph_session(task_id: str) -> AsyncIterator[tuple[Any, dict[str, Any], str]]:
    """
    Yield a compiled graph plus runnable config bound to the task_id thread.

    PostgreSQL uses LangGraph's native async Postgres saver. Memory fallback uses
    a shared in-process saver so multi-turn conversations still work during one
    app lifetime.
    """
    config = build_thread_config(task_id)
    backend = get_configured_checkpoint_backend()

    if backend == "postgres":
        async with AsyncPostgresSaver.from_conn_string(settings.database_url) as saver:
            # Safe to call repeatedly; required on first use to create migrations.
            await saver.setup()
            yield build_graph(checkpointer=saver), config, backend
            return

    yield build_graph(checkpointer=_MEMORY_SAVER), config, "memory"


async def load_state_values(task_id: str) -> tuple[dict[str, Any] | None, str]:
    """Load the latest persisted graph state for a task."""
    async with graph_session(task_id) as (graph, config, backend):
        snapshot = await graph.aget_state(config)
        values = snapshot.values if snapshot.values else None
        return values, backend


def persist_runtime_state(task_id: str, state: dict[str, Any], *, backend: str) -> None:
    """
    Mirror the latest state into the durable runtime table when PostgreSQL is active.

    LangGraph's Postgres saver remains the source of truth for checkpoints. This
    write keeps the application-specific `agent_run_state` summary table current.
    """
    if backend != "postgres":
        return

    runtime_store = PostgresRuntimeStore(
        dsn=settings.database_url,
        schema=settings.database_schema,
    )
    runtime_store.save_checkpoint(task_id, state)
