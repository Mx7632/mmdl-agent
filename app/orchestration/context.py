from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class VisionContext(BaseModel):
    anomalies: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    answer: str | None = None


class KnowledgeContext(BaseModel):
    rows: list[dict[str, Any]] = Field(default_factory=list)
    prompt_context: str | None = None


class ReportContext(BaseModel):
    summary: str | None = None
    anomalies: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ClarificationContext(BaseModel):
    pending_clarification: str | None = None
    pending_question: str | None = None
    unknown_anomaly_types: list[str] = Field(default_factory=list)
    requires_human: bool = False


class SharedContext(BaseModel):
    model_config = ConfigDict(validate_assignment=True)

    vision: VisionContext | None = None
    knowledge: KnowledgeContext | None = None
    report: ReportContext | None = None
    clarification: ClarificationContext | None = None

    def get(self, key: str, default: Any = None) -> Any:
        value = getattr(self, key, default)
        return default if value is None else value

    def __getitem__(self, key: str) -> Any:
        value = getattr(self, key)
        if value is None:
            raise KeyError(key)
        return value

    def __setitem__(self, key: str, value: Any) -> None:
        if key == "vision" and isinstance(value, dict):
            self.vision = VisionContext.model_validate(value)
        elif key == "knowledge" and isinstance(value, dict):
            self.knowledge = KnowledgeContext.model_validate(value)
        elif key == "report" and isinstance(value, dict):
            self.report = ReportContext.model_validate(value)
        elif key == "clarification" and isinstance(value, dict):
            self.clarification = ClarificationContext.model_validate(value)
        else:
            setattr(self, key, value)
