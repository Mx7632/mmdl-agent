from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.orchestration.context import SharedContext
from app.schemas.detection import DetectionResult, DetectionTask


class DetectionState(BaseModel):
    task: DetectionTask

    context: dict[str, Any] = Field(default_factory=dict)
    logs: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)

    result: DetectionResult | None = None

    intermediate_steps: list[Any] = Field(default_factory=list)
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    tool_outputs: list[dict[str, Any]] = Field(default_factory=list)
    agent_outputs: dict[str, Any] = Field(default_factory=dict)
    agent_trace: list[dict[str, Any]] = Field(default_factory=list)
    active_agent: str | None = None
    shared_context: SharedContext = Field(default_factory=SharedContext)
    execution_plan: dict[str, Any] | None = None
    step_status: dict[str, str] = Field(default_factory=dict)
    step_attempts: dict[str, int] = Field(default_factory=dict)
    step_outputs: dict[str, Any] = Field(default_factory=dict)
    execution_events: list[dict[str, Any]] = Field(default_factory=list)
    last_failed_step: str | None = None

    conversation_history: list[dict[str, str]] = Field(default_factory=list)

    loop_count: int = 0
    needs_user_input: bool = False
    user_reply: str | None = None
    reflection_decision: str | None = None
    retry_target: str | None = None
    retry_reason: str | None = None
    retry_strategy: str | None = None
    confidence: float = 0.0
    unknown_anomaly_types: list[str] = Field(default_factory=list)
    current_step: int = 1

    report_requested: bool = False
    stage: str = "chat"
