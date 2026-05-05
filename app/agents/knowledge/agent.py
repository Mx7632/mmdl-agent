from __future__ import annotations

from app.orchestration import AgentEnvelope
from app.rag.object_analysis import build_structured_object_analysis
from app.rag.service import build_anomaly_query_text, build_structured_analysis, get_rag_service
from app.schemas.detection import DetectionTask


class KnowledgeAgent:
    name = "knowledge"

    async def run(self, task: DetectionTask, *, anomalies: list[dict] | None = None) -> AgentEnvelope:
        service = get_rag_service()
        detector_params = (task.parameters or {}).get("detector_params") or {}
        category = (
            detector_params.get("category")
            or (task.parameters or {}).get("category")
            or (task.parameters or {}).get("patchcore_category")
        )

        query_text = task.question or ""
        if not query_text and anomalies:
            query_text = build_anomaly_query_text(anomalies)
        query_text = query_text or "industrial anomaly diagnosis"

        rows = service.query_rows(
            query_text=query_text,
            category=category,
            top_k=3,
        )
        analysis = build_structured_analysis(
            rows=rows,
            anomalies=anomalies,
            query_text=query_text,
        )
        object_analysis = build_structured_object_analysis(
            category=category,
            anomalies=anomalies,
        )
        prompt_context = analysis["prompt_context"]
        if object_analysis["prompt_context"]:
            prompt_context = f"{prompt_context}\n\n{object_analysis['prompt_context']}".strip()
        summary = analysis["analysis_summary"]
        if object_analysis["object_summary"]:
            summary = f"{summary}\n{object_analysis['object_summary']}".strip()

        return AgentEnvelope(
            agent_name=self.name,
            status="success",
            summary=summary,
            payload={
                "rows": rows,
                "prompt_context": prompt_context,
                "similar_cases": analysis["similar_cases"],
                "possible_causes": analysis["possible_causes"],
                "risk_notes": analysis["risk_notes"],
                "repair_actions": analysis["repair_actions"],
                "analysis_summary": analysis["analysis_summary"],
                "object_profile": object_analysis["object_profile"],
                "component_scope": object_analysis["component_scope"],
                "functional_impact": object_analysis["functional_impact"],
                "object_summary": object_analysis["object_summary"],
            },
            confidence=0.7 if rows else 0.3,
        )
