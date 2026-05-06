from __future__ import annotations

from typing import Any

from app.orchestration.context import (
    AnomalyDiscriminationContext,
    DefectAnalysisContext,
    DefectClassificationTaskContext,
    DefectDescriptionTaskContext,
    DefectLocalizationTaskContext,
    KnowledgeContext,
    MMADAnalysisContext,
    ObjectAnalysisContext,
    ObjectClassificationTaskContext,
    VisionContext,
)
from app.schemas.detection import DetectionResult, DetectionTask


def _task_category(task: DetectionTask) -> str | None:
    params = task.parameters or {}
    detector_params = params.get("detector_params") or {}
    category = (
        detector_params.get("category")
        or params.get("category")
        or params.get("patchcore_category")
    )
    return str(category).strip().lower() if category else None


def _metadata_category(metadata: dict[str, Any]) -> str | None:
    category = metadata.get("category") or metadata.get("object_category")
    return str(category).strip().lower() if category else None


def _unique_strings(values: list[Any]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        if value in (None, ""):
            continue
        text = str(value)
        if text in seen:
            continue
        seen.add(text)
        output.append(text)
    return output


def _confidence_from_anomalies(anomalies: list[dict[str, Any]], metadata: dict[str, Any]) -> float:
    scores = [
        float(item.get("score"))
        for item in anomalies
        if isinstance(item, dict) and item.get("score") is not None
    ]
    if scores:
        return round(max(scores), 4)
    for key in ("confidence", "anomaly_score"):
        if metadata.get(key) is not None:
            return round(float(metadata[key]), 4)
    return 0.0


def _build_anomaly_discrimination(
    *,
    result: DetectionResult | None,
    anomalies: list[dict[str, Any]],
    metadata: dict[str, Any],
) -> AnomalyDiscriminationContext:
    if result and result.status == "failed":
        return AnomalyDiscriminationContext(
            status="failed",
            is_anomaly=None,
            confidence=0.0,
            evidence=["视觉分析失败，不能据此判断设备正常。"],
            reason=result.summary or result.answer or "检测工具未返回可靠结果。",
        )

    confidence = _confidence_from_anomalies(anomalies, metadata)
    if anomalies:
        return AnomalyDiscriminationContext(
            status="success",
            is_anomaly=True,
            confidence=confidence,
            evidence=[
                f"检测到 {len(anomalies)} 个异常候选区域。",
                *[
                    str(item.get("description") or item.get("details") or item.get("type"))
                    for item in anomalies[:3]
                    if isinstance(item, dict)
                ],
            ],
            reason="视觉检测结果包含异常候选。",
        )

    return AnomalyDiscriminationContext(
        status="success",
        is_anomaly=False,
        confidence=confidence,
        evidence=["未检测到超过阈值的异常候选区域。"],
        reason="当前视觉结果未返回异常区域。",
    )


def _build_defect_classification(
    anomalies: list[dict[str, Any]],
    *,
    confidence: float,
) -> DefectClassificationTaskContext:
    candidates = _unique_strings(
        [
            item.get("type") or item.get("anomaly_type")
            for item in anomalies
            if isinstance(item, dict)
        ]
    )
    defect_type = candidates[0] if candidates else None
    return DefectClassificationTaskContext(
        status="success" if defect_type else "unknown",
        defect_type=defect_type,
        candidates=candidates,
        confidence=confidence if defect_type else 0.0,
        evidence=[
            str(item.get("description") or item.get("details") or item.get("type"))
            for item in anomalies[:3]
            if isinstance(item, dict)
        ],
    )


def _build_defect_localization(
    anomalies: list[dict[str, Any]],
    metadata: dict[str, Any],
) -> DefectLocalizationTaskContext:
    locations = _unique_strings(
        [
            item.get("location")
            for item in anomalies
            if isinstance(item, dict)
        ]
    )
    bboxes = [
        [int(value) for value in item.get("bbox")]
        for item in anomalies
        if isinstance(item, dict)
        and isinstance(item.get("bbox"), list)
        and len(item.get("bbox")) == 4
    ]
    heatmap_available = bool(metadata.get("heatmap_path") or metadata.get("overlay_path"))
    mask_available = bool(metadata.get("mask_path"))
    if locations or bboxes or heatmap_available or mask_available:
        description = "；".join(
            [
                f"位置：{', '.join(locations)}" if locations else "",
                f"边界框数量：{len(bboxes)}" if bboxes else "",
                "已生成热力图" if heatmap_available else "",
                "已生成掩码" if mask_available else "",
            ]
        ).strip("；")
        return DefectLocalizationTaskContext(
            status="success",
            locations=locations,
            bboxes=bboxes,
            heatmap_available=heatmap_available,
            mask_available=mask_available,
            description=description,
        )
    return DefectLocalizationTaskContext(status="unknown")


def _build_defect_description(anomalies: list[dict[str, Any]]) -> DefectDescriptionTaskContext:
    descriptions = _unique_strings(
        [
            item.get("description") or item.get("details")
            for item in anomalies
            if isinstance(item, dict)
        ]
    )
    appearances = [
        dict(item.get("appearance"))
        for item in anomalies
        if isinstance(item, dict) and isinstance(item.get("appearance"), dict)
    ]
    severity_hints = _unique_strings(
        [
            item.get("severity_hint") or item.get("severity")
            for item in anomalies
            if isinstance(item, dict)
        ]
    )
    return DefectDescriptionTaskContext(
        status="success" if descriptions or appearances or severity_hints else "unknown",
        descriptions=descriptions,
        appearances=appearances,
        severity_hints=severity_hints,
    )


def _build_object_classification(
    *,
    task: DetectionTask,
    vision: VisionContext | None,
    knowledge: KnowledgeContext | None,
    confidence: float,
) -> ObjectClassificationTaskContext:
    metadata = vision.metadata if vision else {}
    object_profile = knowledge.object_analysis.object_profile if knowledge else {}
    category = _metadata_category(metadata) or _task_category(task)
    object_name = object_profile.get("display_name") or object_profile.get("category") or category
    evidence = _unique_strings(
        [
            f"视觉后端类别：{category}" if category else None,
            f"对象知识：{object_name}" if object_name else None,
        ]
    )
    return ObjectClassificationTaskContext(
        status="success" if category or object_name else "unknown",
        category=category,
        object_name=str(object_name) if object_name else None,
        confidence=confidence if category or object_name else 0.0,
        evidence=evidence,
    )


def build_mmad_analysis_context(
    *,
    task: DetectionTask,
    vision: VisionContext | None,
    knowledge: KnowledgeContext | None,
    result: DetectionResult | None = None,
) -> MMADAnalysisContext:
    anomalies = list(vision.anomalies) if vision else list(result.anomalies or []) if result else []
    metadata = dict(result.metadata or {}) if result else {}
    if vision and vision.metadata:
        metadata.update(vision.metadata)

    confidence = _confidence_from_anomalies(anomalies, metadata)
    defect_analysis = knowledge.defect_analysis if knowledge else DefectAnalysisContext()
    object_analysis = knowledge.object_analysis if knowledge else ObjectAnalysisContext()
    return MMADAnalysisContext(
        anomaly_discrimination=_build_anomaly_discrimination(
            result=result,
            anomalies=anomalies,
            metadata=metadata,
        ),
        defect_classification=_build_defect_classification(anomalies, confidence=confidence),
        defect_localization=_build_defect_localization(anomalies, metadata),
        defect_description=_build_defect_description(anomalies),
        defect_analysis=defect_analysis,
        object_classification=_build_object_classification(
            task=task,
            vision=vision,
            knowledge=knowledge,
            confidence=confidence,
        ),
        object_analysis=object_analysis,
    )


def dump_mmad_analysis(context: MMADAnalysisContext | None) -> dict[str, Any]:
    return context.model_dump() if context else {}


def format_mmad_analysis(context: MMADAnalysisContext | None, *, empty_text: str = "(no MMAD task analysis)") -> str:
    if not context:
        return empty_text

    sections = [
        (
            "异常判别",
            [
                f"状态：{context.anomaly_discrimination.status}",
                f"是否异常：{context.anomaly_discrimination.is_anomaly}",
                f"置信度：{context.anomaly_discrimination.confidence}",
                *(context.anomaly_discrimination.evidence or []),
            ],
        ),
        (
            "缺陷分类",
            [
                f"类型：{context.defect_classification.defect_type or 'unknown'}",
                f"候选：{', '.join(context.defect_classification.candidates) or 'unknown'}",
            ],
        ),
        (
            "缺陷定位",
            [
                context.defect_localization.description or "暂无明确定位",
            ],
        ),
        (
            "缺陷描述",
            context.defect_description.descriptions
            or [f"外观线索：{item}" for item in context.defect_description.appearances]
            or ["暂无结构化描述"],
        ),
        (
            "缺陷分析",
            [
                context.defect_analysis.analysis_summary or "",
                *context.defect_analysis.possible_causes,
                *context.defect_analysis.risk_notes,
            ],
        ),
        (
            "产品分类",
            [
                f"类别：{context.object_classification.category or 'unknown'}",
                f"对象：{context.object_classification.object_name or 'unknown'}",
            ],
        ),
        (
            "产品分析",
            [
                context.object_analysis.object_summary or "",
                *context.object_analysis.functional_impact,
            ],
        ),
    ]

    rendered: list[str] = []
    for title, items in sections:
        values = [str(item) for item in items if item not in (None, "")]
        if values:
            rendered.append(f"[{title}]\n" + "\n".join(f"- {item}" for item in values))
    return "\n\n".join(rendered) if rendered else empty_text
