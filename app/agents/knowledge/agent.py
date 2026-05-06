from __future__ import annotations

from app.orchestration import AgentEnvelope
from app.rag.fewshot import build_fewshot_context
from app.rag.knowledge_pipeline import (
    build_defect_analysis_contract,
    build_knowledge_context,
    build_object_analysis_contract,
    dump_knowledge_payload,
    resolve_knowledge_request,
    summarize_knowledge_context,
)
from app.rag.service import get_rag_service
from app.schemas.detection import DetectionTask


class KnowledgeAgent:
    name = "knowledge"

    async def run(self, task: DetectionTask, *, anomalies: list[dict] | None = None) -> AgentEnvelope:
        service = get_rag_service()
        request = resolve_knowledge_request(task, anomalies=anomalies)
        category = request["category"]
        query_text = request["query_text"]

        rows = service.query_rows(
            query_text=query_text,
            category=category,
            top_k=3,
        )
        if hasattr(service, "query_fewshot_rows"):
            fewshot_rows = service.query_fewshot_rows(
                query_text=query_text,
                category=category,
                top_k=4,
            )
        else:
            fewshot_rows = rows
        few_shot_examples, few_shot_context = build_fewshot_context(fewshot_rows)

        defect_context, defect_prompt_context = build_defect_analysis_contract(
            rows=rows,
            anomalies=anomalies,
            query_text=query_text,
        )
        object_context_payload, object_prompt_context = build_object_analysis_contract(
            category=category,
            anomalies=anomalies,
            asset_id=task.asset_id,
            object_context=request["object_context"],
            query_text=query_text,
        )
        knowledge_context = build_knowledge_context(
            rows=rows,
            defect_analysis=defect_context,
            defect_prompt_context=defect_prompt_context,
            object_analysis=object_context_payload,
            object_prompt_context=object_prompt_context,
            few_shot_context=few_shot_context,
            few_shot_examples=few_shot_examples,
        )
        summary = summarize_knowledge_context(knowledge_context)

        return AgentEnvelope(
            agent_name=self.name,
            status="success",
            summary=summary,
            payload=dump_knowledge_payload(knowledge_context),
            confidence=0.7 if rows else 0.3,
        )
