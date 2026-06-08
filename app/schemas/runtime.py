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


class TaskRecord(BaseModel):
    """Public product task record exposed by runtime history endpoints."""

    model_config = ConfigDict(extra="allow")

    task_id: str
    batch_id: str | None = None
    asset_id: str = ""
    category: str = "unknown"
    status: str = "unknown"
    is_anomaly: bool = False
    score: float = 0.0
    defect_type: str = "unknown"
    review_status: str = "auto_pass"
    requires_review: bool = False
    model_backend: str = "unknown"
    model_version: str = "unknown"
    sample_version: str = "unversioned"
    created_at: str | None = None
    updated_at: str | None = None
    review: dict[str, Any] | None = None
    result: dict[str, Any] = Field(default_factory=dict)


class TaskListResponse(BaseModel):
    """Response contract for product task list endpoints."""

    status: str
    tasks: list[TaskRecord] = Field(default_factory=list)


class TaskDetailResponse(TaskRecord):
    """Response contract for a single product task detail."""

    status: str = "success"


class TaskReviewResponse(BaseModel):
    """Response contract for task human-review actions."""

    status: str
    task: TaskRecord


class DeleteTaskResponse(BaseModel):
    """Response contract for deleting a single task."""

    status: str
    deleted: str


class DeleteAllTasksResponse(BaseModel):
    """Response contract for clearing task history."""

    status: str
    deleted_count: int


class BatchInfo(BaseModel):
    """Runtime batch metadata."""

    model_config = ConfigDict(extra="allow")

    batch_id: str
    asset_id: str = ""
    question: str | None = None
    item_count: int = 0
    task_ids: list[str] = Field(default_factory=list)
    status: str = "unknown"
    created_at: str | None = None
    updated_at: str | None = None


class BatchReport(BaseModel):
    """Response body fields produced by the batch report generator."""

    batch_id: str
    status: str | None = None
    task_count: int = 0
    anomaly_count: int = 0
    normal_count: int = 0
    defect_distribution: dict[str, int] = Field(default_factory=dict)
    review_distribution: dict[str, int] = Field(default_factory=dict)
    sample_tasks: list[TaskRecord] = Field(default_factory=list)
    summary: str = ""


class BatchReportResponse(BatchReport):
    """Response contract for /v1/batches/{batch_id}/report."""

    status: str = "success"


class BatchDetectResponse(BaseModel):
    """Response contract for batch image detection."""

    status: str
    batch: BatchInfo
    results: list[dict[str, Any]] = Field(default_factory=list)
    report: BatchReport


class RagFeedbackReviewResponse(BaseModel):
    """Response contract for RAG feedback review actions."""

    status: str
    feedback: dict[str, Any]


class ProductAnalysisResponse(BaseModel):
    """Shared product response shape for analysis and report-facing endpoints."""

    model_config = ConfigDict(extra="allow")

    task_id: str | None = None
    status: str
    answer: str | None = None
    anomalies: list[dict[str, Any]] = Field(default_factory=list)
    summary: str | None = None
    has_report: bool = False
    conversation_history: list[dict[str, Any]] = Field(default_factory=list)
    pending_clarification: str | None = None
    pending_question: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    is_anomaly: bool | None = None
    score: float | None = None
    defect_type: str | None = None
    review_status: str | None = None
    requires_review: bool | None = None


class ReportGenerationResponse(ProductAnalysisResponse):
    """Response contract for /v1/generate_report."""

    has_report: bool = True
