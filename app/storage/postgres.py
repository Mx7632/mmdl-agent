"""PostgreSQL-backed durable runtime state and checkpoint storage."""

from __future__ import annotations

import json
import logging
import re
from contextlib import contextmanager
from typing import Any, Generator, Optional

logger = logging.getLogger(__name__)

try:
    import psycopg
except ImportError:  # pragma: no cover - handled by backend fallback
    psycopg = None


class PostgresRuntimeStore:
    """Persist runtime state and checkpoints into PostgreSQL."""

    def __init__(self, dsn: str, schema: str = "public"):
        if not dsn:
            raise ValueError("PostgreSQL DSN is required")
        if psycopg is None:
            raise RuntimeError("psycopg is not installed")
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", schema):
            raise ValueError(f"Invalid PostgreSQL schema name: {schema}")
        self.dsn = dsn
        self.schema = schema
        self._schema_ready = False

    @property
    def is_available(self) -> bool:
        return psycopg is not None

    @contextmanager
    def _connect(self) -> Generator[Any, None, None]:
        conn = psycopg.connect(self.dsn)
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def ensure_schema(self) -> None:
        if self._schema_ready:
            return

        schema_sql = f"""
        CREATE SCHEMA IF NOT EXISTS {self.schema};

        CREATE TABLE IF NOT EXISTS {self.schema}.agent_run_state (
            task_id TEXT PRIMARY KEY,
            asset_id TEXT,
            stage TEXT,
            status TEXT,
            needs_user_input BOOLEAN NOT NULL DEFAULT FALSE,
            loop_count INTEGER NOT NULL DEFAULT 0,
            current_step INTEGER NOT NULL DEFAULT 1,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            state_json JSONB NOT NULL
        );

        CREATE TABLE IF NOT EXISTS {self.schema}.agent_checkpoints (
            task_id TEXT PRIMARY KEY,
            checkpoint_json JSONB NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """

        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(schema_sql)
        self._schema_ready = True

    def save_checkpoint(self, task_id: str, state: dict[str, Any]) -> None:
        self.ensure_schema()

        task = state.get("task", {}) if isinstance(state, dict) else {}
        result = state.get("result") if isinstance(state, dict) else None
        if isinstance(result, dict):
            status = result.get("status")
        else:
            status = None

        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    INSERT INTO {self.schema}.agent_checkpoints (
                        task_id, checkpoint_json, created_at, updated_at
                    )
                    VALUES (%s, %s::jsonb, NOW(), NOW())
                    ON CONFLICT (task_id) DO UPDATE SET
                        checkpoint_json = EXCLUDED.checkpoint_json,
                        updated_at = NOW()
                    """,
                    (task_id, json.dumps(state, ensure_ascii=False, default=str)),
                )
                cur.execute(
                    f"""
                    INSERT INTO {self.schema}.agent_run_state (
                        task_id,
                        asset_id,
                        stage,
                        status,
                        needs_user_input,
                        loop_count,
                        current_step,
                        updated_at,
                        state_json
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, NOW(), %s::jsonb)
                    ON CONFLICT (task_id) DO UPDATE SET
                        asset_id = EXCLUDED.asset_id,
                        stage = EXCLUDED.stage,
                        status = EXCLUDED.status,
                        needs_user_input = EXCLUDED.needs_user_input,
                        loop_count = EXCLUDED.loop_count,
                        current_step = EXCLUDED.current_step,
                        updated_at = NOW(),
                        state_json = EXCLUDED.state_json
                    """,
                    (
                        task_id,
                        task.get("asset_id"),
                        state.get("stage"),
                        status,
                        bool(state.get("needs_user_input", False)),
                        int(state.get("loop_count", 0)),
                        int(state.get("current_step", 1)),
                        json.dumps(state, ensure_ascii=False, default=str),
                    ),
                )

    def load_checkpoint(self, task_id: str) -> Optional[dict[str, Any]]:
        self.ensure_schema()

        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT checkpoint_json FROM {self.schema}.agent_checkpoints WHERE task_id = %s",
                    (task_id,),
                )
                row = cur.fetchone()

        if not row:
            return None

        payload = row[0]
        if isinstance(payload, str):
            return json.loads(payload)
        return payload

    def load_run_state(self, task_id: str) -> Optional[dict[str, Any]]:
        self.ensure_schema()

        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT state_json FROM {self.schema}.agent_run_state WHERE task_id = %s",
                    (task_id,),
                )
                row = cur.fetchone()

        if not row:
            return None

        payload = row[0]
        if isinstance(payload, str):
            return json.loads(payload)
        return payload
