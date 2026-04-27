"""Checkpoint storage backends for DetectionState persistence."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Union

from app.config.settings import settings
from app.memory.state import DetectionState
from app.storage.postgres import PostgresRuntimeStore

logger = logging.getLogger(__name__)


def _deep_to_dict(obj: Any) -> Any:
    """Recursively convert nested Pydantic values into plain JSON-compatible objects."""
    if obj is None:
        return None
    if isinstance(obj, dict):
        return {k: _deep_to_dict(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_deep_to_dict(item) for item in obj]
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if isinstance(obj, (str, int, float, bool)):
        return obj
    try:
        return dict(obj)
    except Exception:
        return obj


class CheckpointStore:
    """Abstract checkpoint storage."""

    def save(self, state: Union[DetectionState, dict]) -> None:
        raise NotImplementedError("save method must be implemented by subclass")

    def load(self, task_id: str) -> Optional[Union[DetectionState, dict]]:
        raise NotImplementedError("load method must be implemented by subclass")

    @property
    def backend_name(self) -> str:
        raise NotImplementedError("backend_name must be implemented by subclass")


class MemoryCheckpointStore(CheckpointStore):
    """In-memory checkpoint store used as a safe fallback."""

    def __init__(self):
        self._store: Dict[str, dict] = {}

    def save(self, state: Union[DetectionState, dict]) -> None:
        if isinstance(state, DetectionState):
            state = state.model_dump()
        else:
            state = _deep_to_dict(state)
        task = state.get("task", {})
        task_id = task.get("task_id") if isinstance(task, dict) else getattr(task, "task_id", "unknown")
        self._store[task_id] = state

    def load(self, task_id: str) -> Optional[dict]:
        return self._store.get(task_id)

    @property
    def backend_name(self) -> str:
        return "memory"


class PostgresCheckpointStore(CheckpointStore):
    """Persist checkpoints and durable run state into PostgreSQL."""

    def __init__(self, dsn: str, schema: str = "public"):
        self.runtime_store = PostgresRuntimeStore(dsn=dsn, schema=schema)

    def save(self, state: Union[DetectionState, dict]) -> None:
        if isinstance(state, DetectionState):
            state = state.model_dump()
        else:
            state = _deep_to_dict(state)

        task = state.get("task", {})
        task_id = task.get("task_id") if isinstance(task, dict) else getattr(task, "task_id", "unknown")
        self.runtime_store.save_checkpoint(task_id, state)

    def load(self, task_id: str) -> Optional[dict]:
        return self.runtime_store.load_checkpoint(task_id)

    @property
    def backend_name(self) -> str:
        return "postgres"


def get_checkpoint_store() -> CheckpointStore:
    """Create the configured checkpoint backend with safe fallback."""
    backend = (settings.checkpoint_backend or "memory").strip().lower()
    if backend == "postgres":
        if not settings.database_url:
            logger.warning(
                "APP_CHECKPOINT_BACKEND=postgres but APP_DATABASE_URL is empty; fallback to memory"
            )
            return MemoryCheckpointStore()
        try:
            return PostgresCheckpointStore(
                dsn=settings.database_url,
                schema=settings.database_schema,
            )
        except Exception as exc:
            logger.warning("PostgreSQL checkpoint backend unavailable, fallback to memory: %s", exc)
            return MemoryCheckpointStore()
    return MemoryCheckpointStore()
