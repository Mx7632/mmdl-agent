from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.orchestration.context import SharedContext
from app.schemas.detection import DetectionResult, DetectionTask


class TaskRuntimeState(BaseModel):
    task: DetectionTask
    conversation_history: list[dict[str, str]] = Field(default_factory=list)
    user_reply: str | None = None
    current_step: int = 1
    report_requested: bool = False
    stage: str = "chat"


class OrchestrationRuntimeState(BaseModel):
    active_agent: str | None = None
    execution_plan: dict[str, Any] | None = None
    step_status: dict[str, str] = Field(default_factory=dict)
    step_attempts: dict[str, int] = Field(default_factory=dict)
    step_outputs: dict[str, Any] = Field(default_factory=dict)
    execution_events: list[dict[str, Any]] = Field(default_factory=list)
    last_failed_step: str | None = None
    loop_count: int = 0
    needs_user_input: bool = False
    reflection_decision: str | None = None
    retry_target: str | None = None
    retry_reason: str | None = None
    retry_strategy: str | None = None
    confidence: float = 0.0
    unknown_anomaly_types: list[str] = Field(default_factory=list)


class DomainRuntimeState(BaseModel):
    result: DetectionResult | None = None
    shared_context: SharedContext = Field(default_factory=SharedContext)
    intermediate_steps: list[Any] = Field(default_factory=list)
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    tool_outputs: list[dict[str, Any]] = Field(default_factory=list)
    agent_outputs: dict[str, Any] = Field(default_factory=dict)
    agent_trace: list[dict[str, Any]] = Field(default_factory=list)


class DetectionState(BaseModel):
    """Durable top-level workflow state.

    Notes:
    - The persisted/checkpointed shape remains flat for compatibility.
    - New code should prefer grouped runtime access via:
      `task_runtime()`, `orchestration_runtime()`, and `domain_runtime()`.
    - Direct top-level field access is kept as a compatibility layer while the
      codebase is migrated incrementally.
    """

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

    def task_runtime(self) -> TaskRuntimeState:
        return TaskRuntimeState(
            task=self.task,
            conversation_history=list(self.conversation_history),
            user_reply=self.user_reply,
            current_step=self.current_step,
            report_requested=self.report_requested,
            stage=self.stage,
        )

    def apply_task_runtime(self, runtime: TaskRuntimeState) -> None:
        self.task = runtime.task
        self.conversation_history = list(runtime.conversation_history)
        self.user_reply = runtime.user_reply
        self.current_step = runtime.current_step
        self.report_requested = runtime.report_requested
        self.stage = runtime.stage

    def orchestration_runtime(self) -> OrchestrationRuntimeState:
        return OrchestrationRuntimeState(
            active_agent=self.active_agent,
            execution_plan=self.execution_plan,
            step_status=dict(self.step_status),
            step_attempts=dict(self.step_attempts),
            step_outputs=dict(self.step_outputs),
            execution_events=list(self.execution_events),
            last_failed_step=self.last_failed_step,
            loop_count=self.loop_count,
            needs_user_input=self.needs_user_input,
            reflection_decision=self.reflection_decision,
            retry_target=self.retry_target,
            retry_reason=self.retry_reason,
            retry_strategy=self.retry_strategy,
            confidence=self.confidence,
            unknown_anomaly_types=list(self.unknown_anomaly_types),
        )

    def apply_orchestration_runtime(self, runtime: OrchestrationRuntimeState) -> None:
        self.active_agent = runtime.active_agent
        self.execution_plan = runtime.execution_plan
        self.step_status = dict(runtime.step_status)
        self.step_attempts = dict(runtime.step_attempts)
        self.step_outputs = dict(runtime.step_outputs)
        self.execution_events = list(runtime.execution_events)
        self.last_failed_step = runtime.last_failed_step
        self.loop_count = runtime.loop_count
        self.needs_user_input = runtime.needs_user_input
        self.reflection_decision = runtime.reflection_decision
        self.retry_target = runtime.retry_target
        self.retry_reason = runtime.retry_reason
        self.retry_strategy = runtime.retry_strategy
        self.confidence = runtime.confidence
        self.unknown_anomaly_types = list(runtime.unknown_anomaly_types)

    def domain_runtime(self) -> DomainRuntimeState:
        return DomainRuntimeState(
            result=self.result,
            shared_context=self.shared_context.model_copy(deep=True),
            intermediate_steps=list(self.intermediate_steps),
            tool_calls=list(self.tool_calls),
            tool_outputs=list(self.tool_outputs),
            agent_outputs=dict(self.agent_outputs),
            agent_trace=list(self.agent_trace),
        )

    def apply_domain_runtime(self, runtime: DomainRuntimeState) -> None:
        self.result = runtime.result
        self.shared_context = runtime.shared_context.model_copy(deep=True)
        self.intermediate_steps = list(runtime.intermediate_steps)
        self.tool_calls = list(runtime.tool_calls)
        self.tool_outputs = list(runtime.tool_outputs)
        self.agent_outputs = dict(runtime.agent_outputs)
        self.agent_trace = list(runtime.agent_trace)
