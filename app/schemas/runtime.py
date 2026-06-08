from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ApiComponentHealth(BaseModel):
    """Health state for the FastAPI component."""

    status: str


class RagComponentHealth(BaseModel):
    """Health state for the RAG vector store component."""

    status: str
    vector_dir: str


class CheckpointComponentHealth(BaseModel):
    """Health state for checkpoint persistence."""

    status: str
    backend: str


class PatchCoreComponentHealth(BaseModel):
    """Health state for the local PatchCore detector."""

    status: str
    model_root: str
    trained_categories: list[str] = Field(default_factory=list)


class SidecarComponentHealth(BaseModel):
    """Health state for optional detector sidecar services."""

    status: str
    url: str = ""


class SecurityComponentHealth(BaseModel):
    """Health state for browser/API access controls."""

    api_token_required: bool
    allowed_origins: list[str] = Field(default_factory=list)


class SystemHealthComponents(BaseModel):
    """Grouped product runtime component states."""

    api: ApiComponentHealth
    rag: RagComponentHealth
    postgres: CheckpointComponentHealth
    patchcore: PatchCoreComponentHealth
    anomalygpt_sidecar: SidecarComponentHealth
    grad_sidecar: SidecarComponentHealth
    security: SecurityComponentHealth


class RuntimeMetrics(BaseModel):
    """Product runtime counters exposed by the in-process runtime store."""

    model_config = ConfigDict(extra="allow")

    task_count: int = 0
    batch_count: int = 0
    feedback_count: int = 0
    session_count: int = 0
    status_counts: dict[str, int] = Field(default_factory=dict)
    review_counts: dict[str, int] = Field(default_factory=dict)
    backend_counts: dict[str, int] = Field(default_factory=dict)


class SystemHealthResponse(BaseModel):
    """Response contract for /v1/system/health."""

    status: str
    timestamp: float
    components: SystemHealthComponents
    metrics: RuntimeMetrics


class RuntimeMetricsResponse(BaseModel):
    """Response contract for /v1/metrics."""

    status: str
    metrics: RuntimeMetrics


class TaskListResponse(BaseModel):
    """Response contract for product task list endpoints."""

    status: str
    tasks: list[dict[str, Any]] = Field(default_factory=list)
