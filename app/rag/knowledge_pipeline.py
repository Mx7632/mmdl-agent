from __future__ import annotations

from typing import Any

from app.orchestration.context import DefectAnalysisContext, KnowledgeContext, ObjectAnalysisContext
from app.rag.defect_analysis import build_anomaly_query_text, build_structured_analysis
from app.rag.object_analysis import build_structured_object_analysis
from app.schemas.detection import DetectionTask


def resolve_knowledge_request(
    task: DetectionTask,
    *,
    anomalies: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    detector_params = (task.parameters or {}).get("detector_params") or {}
    object_context = (
        (task.parameters or {}).get("object_context")
        or detector_params.get("object_context")
        or {}
    )
    category = (
        detector_params.get("category")
        or (task.parameters or {}).get("category")
        or (task.parameters or {}).get("patchcore_category")
    )

    query_text = task.question or ""
    if not query_text and anomalies:
        query_text = build_anomaly_query_text(anomalies)
    query_text = query_text or "industrial anomaly diagnosis"

    return {
        "category": category,
        "query_text": query_text,
        "object_context": object_context if isinstance(object_context, dict) else None,
    }


def build_defect_analysis_contract(
    *,
    rows: list[dict[str, Any]],
    anomalies: list[dict[str, Any]] | None = None,
    query_text: str = "",
) -> tuple[DefectAnalysisContext, str]:
    analysis = build_structured_analysis(
        rows=rows,
        anomalies=anomalies,
        query_text=query_text,
    )
    return (
        DefectAnalysisContext(
            similar_cases=analysis["similar_cases"],
            possible_causes=analysis["possible_causes"],
            risk_notes=analysis["risk_notes"],
            repair_actions=analysis["repair_actions"],
            analysis_summary=analysis["analysis_summary"],
        ),
        analysis["prompt_context"],
    )


def build_object_analysis_contract(
    *,
    category: str | None,
    anomalies: list[dict[str, Any]] | None = None,
    asset_id: str | None = None,
    object_context: dict[str, Any] | None = None,
    query_text: str = "",
) -> tuple[ObjectAnalysisContext, str]:
    object_analysis = build_structured_object_analysis(
        category=category,
        anomalies=anomalies,
        asset_id=asset_id,
        object_context=object_context,
        query_text=query_text,
    )
    return (
        ObjectAnalysisContext(
            object_profile=object_analysis["object_profile"],
            component_scope=object_analysis["component_scope"],
            component_findings=object_analysis["component_findings"],
            functional_impact=object_analysis["functional_impact"],
            object_summary=object_analysis["object_summary"],
            object_knowledge_notes=object_analysis["object_knowledge_notes"],
            object_knowledge_hits=object_analysis["object_knowledge_hits"],
            object_knowledge_summary=object_analysis["object_knowledge_summary"],
        ),
        object_analysis["prompt_context"],
    )


def build_knowledge_context(
    *,
    rows: list[dict[str, Any]],
    defect_analysis: DefectAnalysisContext,
    defect_prompt_context: str,
    object_analysis: ObjectAnalysisContext,
    object_prompt_context: str,
    few_shot_context: str | None = None,
    few_shot_examples: dict[str, list[dict[str, Any]]] | None = None,
) -> KnowledgeContext:
    prompt_context = defect_prompt_context
    if few_shot_context:
        prompt_context = f"{prompt_context}\n\n{few_shot_context}".strip()
    if object_prompt_context:
        prompt_context = f"{prompt_context}\n\n{object_prompt_context}".strip()

    return KnowledgeContext(
        rows=rows,
        prompt_context=prompt_context,
        defect_analysis=defect_analysis,
        object_analysis=object_analysis,
        few_shot_examples=few_shot_examples or {},
        few_shot_context=few_shot_context,
    )


def dump_knowledge_payload(context: KnowledgeContext) -> dict[str, Any]:
    return {
        "rows": list(context.rows),
        "prompt_context": context.prompt_context,
        "few_shot_examples": context.few_shot_examples,
        "few_shot_context": context.few_shot_context,
        "defect_analysis": context.defect_analysis.model_dump(),
        "object_analysis": context.object_analysis.model_dump(),
    }


def dump_analysis_contracts(context: KnowledgeContext) -> dict[str, Any]:
    return {
        "defect_analysis": context.defect_analysis.model_dump(),
        "object_analysis": context.object_analysis.model_dump(),
    }


def format_analysis_contracts(context: KnowledgeContext, *, empty_text: str = "(no structured defect analysis)") -> str:
    sections: list[str] = []
    defect = context.defect_analysis
    obj = context.object_analysis

    if defect.analysis_summary:
        sections.append(f"[Analysis summary]\n{defect.analysis_summary}")
    if obj.object_summary:
        sections.append(f"[Object summary]\n{obj.object_summary}")
    if obj.object_knowledge_summary:
        sections.append(f"[Object knowledge summary]\n{obj.object_knowledge_summary}")
    if context.few_shot_context:
        sections.append(context.few_shot_context)
    if obj.object_knowledge_hits:
        sections.append(
            "[Object knowledge hits]\n"
            + "\n".join(
                f"- {item.get('title')}: {item.get('note')}"
                for item in obj.object_knowledge_hits
            )
        )
    if obj.component_scope:
        sections.append("[Component scope]\n" + "\n".join(f"- {item}" for item in obj.component_scope))
    if obj.component_findings:
        sections.append(
            "[Component findings]\n"
            + "\n".join(
                f"- {item.get('location')} -> {item.get('component')} ({item.get('anomaly_type')})"
                for item in obj.component_findings
            )
        )
    if obj.functional_impact:
        sections.append("[Functional impact]\n" + "\n".join(f"- {item}" for item in obj.functional_impact))
    if obj.object_knowledge_notes:
        sections.append("[Object knowledge]\n" + "\n".join(f"- {item}" for item in obj.object_knowledge_notes))
    if defect.similar_cases:
        sections.append(
            "[Similar cases]\n"
            + "\n".join(f"- {item.get('summary') or item.get('id')}" for item in defect.similar_cases)
        )
    if defect.possible_causes:
        sections.append("[Possible causes]\n" + "\n".join(f"- {item}" for item in defect.possible_causes))
    if defect.risk_notes:
        sections.append("[Risk notes]\n" + "\n".join(f"- {item}" for item in defect.risk_notes))
    if defect.repair_actions:
        sections.append("[Repair actions]\n" + "\n".join(f"- {item}" for item in defect.repair_actions))

    return "\n\n".join(sections) if sections else empty_text


def summarize_knowledge_context(context: KnowledgeContext) -> str:
    parts = [context.defect_analysis.analysis_summary or ""]
    if context.object_analysis.object_summary:
        parts.append(context.object_analysis.object_summary)
    if context.object_analysis.object_knowledge_summary:
        parts.append(context.object_analysis.object_knowledge_summary)
    return "\n".join(part for part in parts if part).strip()
