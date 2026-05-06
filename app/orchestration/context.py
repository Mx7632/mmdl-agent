from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class VisionContext(BaseModel):
    anomalies: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    answer: str | None = None


class DefectAnalysisContext(BaseModel):
    similar_cases: list[dict[str, Any]] = Field(default_factory=list)
    possible_causes: list[str] = Field(default_factory=list)
    risk_notes: list[str] = Field(default_factory=list)
    repair_actions: list[str] = Field(default_factory=list)
    analysis_summary: str | None = None


class ObjectAnalysisContext(BaseModel):
    object_profile: dict[str, Any] = Field(default_factory=dict)
    component_scope: list[str] = Field(default_factory=list)
    component_findings: list[dict[str, Any]] = Field(default_factory=list)
    functional_impact: list[str] = Field(default_factory=list)
    object_summary: str | None = None
    object_knowledge_notes: list[str] = Field(default_factory=list)
    object_knowledge_hits: list[dict[str, Any]] = Field(default_factory=list)
    object_knowledge_summary: str | None = None


class AnomalyDiscriminationContext(BaseModel):
    status: str = "unknown"
    is_anomaly: bool | None = None
    confidence: float = 0.0
    evidence: list[str] = Field(default_factory=list)
    reason: str | None = None


class DefectClassificationTaskContext(BaseModel):
    status: str = "unknown"
    defect_type: str | None = None
    candidates: list[str] = Field(default_factory=list)
    confidence: float = 0.0
    evidence: list[str] = Field(default_factory=list)


class DefectLocalizationTaskContext(BaseModel):
    status: str = "unknown"
    locations: list[str] = Field(default_factory=list)
    bboxes: list[list[int]] = Field(default_factory=list)
    heatmap_available: bool = False
    mask_available: bool = False
    description: str | None = None


class DefectDescriptionTaskContext(BaseModel):
    status: str = "unknown"
    descriptions: list[str] = Field(default_factory=list)
    appearances: list[dict[str, Any]] = Field(default_factory=list)
    severity_hints: list[str] = Field(default_factory=list)


class ObjectClassificationTaskContext(BaseModel):
    status: str = "unknown"
    category: str | None = None
    object_name: str | None = None
    confidence: float = 0.0
    evidence: list[str] = Field(default_factory=list)


class MMADAnalysisContext(BaseModel):
    anomaly_discrimination: AnomalyDiscriminationContext = Field(default_factory=AnomalyDiscriminationContext)
    defect_classification: DefectClassificationTaskContext = Field(default_factory=DefectClassificationTaskContext)
    defect_localization: DefectLocalizationTaskContext = Field(default_factory=DefectLocalizationTaskContext)
    defect_description: DefectDescriptionTaskContext = Field(default_factory=DefectDescriptionTaskContext)
    defect_analysis: DefectAnalysisContext = Field(default_factory=DefectAnalysisContext)
    object_classification: ObjectClassificationTaskContext = Field(default_factory=ObjectClassificationTaskContext)
    object_analysis: ObjectAnalysisContext = Field(default_factory=ObjectAnalysisContext)


class KnowledgeContext(BaseModel):
    rows: list[dict[str, Any]] = Field(default_factory=list)
    prompt_context: str | None = None
    defect_analysis: DefectAnalysisContext = Field(default_factory=DefectAnalysisContext)
    object_analysis: ObjectAnalysisContext = Field(default_factory=ObjectAnalysisContext)
    # Compatibility mirrors. New code should prefer defect_analysis/object_analysis.
    similar_cases: list[dict[str, Any]] = Field(default_factory=list)
    possible_causes: list[str] = Field(default_factory=list)
    risk_notes: list[str] = Field(default_factory=list)
    repair_actions: list[str] = Field(default_factory=list)
    analysis_summary: str | None = None
    object_profile: dict[str, Any] = Field(default_factory=dict)
    component_scope: list[str] = Field(default_factory=list)
    component_findings: list[dict[str, Any]] = Field(default_factory=list)
    functional_impact: list[str] = Field(default_factory=list)
    object_summary: str | None = None
    object_knowledge_notes: list[str] = Field(default_factory=list)
    object_knowledge_hits: list[dict[str, Any]] = Field(default_factory=list)
    object_knowledge_summary: str | None = None

    @model_validator(mode="after")
    def sync_analysis_views(self) -> "KnowledgeContext":
        if not self.defect_analysis.analysis_summary and self.analysis_summary:
            self.defect_analysis.analysis_summary = self.analysis_summary
        if not self.defect_analysis.similar_cases and self.similar_cases:
            self.defect_analysis.similar_cases = list(self.similar_cases)
        if not self.defect_analysis.possible_causes and self.possible_causes:
            self.defect_analysis.possible_causes = list(self.possible_causes)
        if not self.defect_analysis.risk_notes and self.risk_notes:
            self.defect_analysis.risk_notes = list(self.risk_notes)
        if not self.defect_analysis.repair_actions and self.repair_actions:
            self.defect_analysis.repair_actions = list(self.repair_actions)

        if not self.object_analysis.object_profile and self.object_profile:
            self.object_analysis.object_profile = dict(self.object_profile)
        if not self.object_analysis.component_scope and self.component_scope:
            self.object_analysis.component_scope = list(self.component_scope)
        if not self.object_analysis.component_findings and self.component_findings:
            self.object_analysis.component_findings = list(self.component_findings)
        if not self.object_analysis.functional_impact and self.functional_impact:
            self.object_analysis.functional_impact = list(self.functional_impact)
        if not self.object_analysis.object_summary and self.object_summary:
            self.object_analysis.object_summary = self.object_summary
        if not self.object_analysis.object_knowledge_notes and self.object_knowledge_notes:
            self.object_analysis.object_knowledge_notes = list(self.object_knowledge_notes)
        if not self.object_analysis.object_knowledge_hits and self.object_knowledge_hits:
            self.object_analysis.object_knowledge_hits = list(self.object_knowledge_hits)
        if not self.object_analysis.object_knowledge_summary and self.object_knowledge_summary:
            self.object_analysis.object_knowledge_summary = self.object_knowledge_summary

        self.similar_cases = list(self.defect_analysis.similar_cases)
        self.possible_causes = list(self.defect_analysis.possible_causes)
        self.risk_notes = list(self.defect_analysis.risk_notes)
        self.repair_actions = list(self.defect_analysis.repair_actions)
        self.analysis_summary = self.defect_analysis.analysis_summary

        self.object_profile = dict(self.object_analysis.object_profile)
        self.component_scope = list(self.object_analysis.component_scope)
        self.component_findings = list(self.object_analysis.component_findings)
        self.functional_impact = list(self.object_analysis.functional_impact)
        self.object_summary = self.object_analysis.object_summary
        self.object_knowledge_notes = list(self.object_analysis.object_knowledge_notes)
        self.object_knowledge_hits = list(self.object_analysis.object_knowledge_hits)
        self.object_knowledge_summary = self.object_analysis.object_knowledge_summary
        return self


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
    mmad_analysis: MMADAnalysisContext | None = None
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
        elif key == "mmad_analysis" and isinstance(value, dict):
            self.mmad_analysis = MMADAnalysisContext.model_validate(value)
        elif key == "report" and isinstance(value, dict):
            self.report = ReportContext.model_validate(value)
        elif key == "clarification" and isinstance(value, dict):
            self.clarification = ClarificationContext.model_validate(value)
        else:
            setattr(self, key, value)
