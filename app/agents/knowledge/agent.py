from __future__ import annotations

from app.orchestration import AgentEnvelope
from app.rag.service import get_rag_service
from app.schemas.detection import DetectionTask


class KnowledgeAgent:
    name = "knowledge"

    async def run(self, task: DetectionTask, *, anomalies: list[dict] | None = None) -> AgentEnvelope:
        service = get_rag_service()
        category = (task.parameters or {}).get("category")

        query_text = task.question or ""
        if not query_text and anomalies:
            query_text = "; ".join(
                f"{item.get('type', 'unknown')}: {item.get('details', '')}"
                for item in anomalies
            )
        query_text = query_text or "industrial anomaly diagnosis"

        rows = service.query_rows(
            query_text=query_text,
            category=category,
            top_k=3,
        )
        prompt_context = service.retriever.format_for_prompt(rows)
        summary = f"Retrieved {len(rows)} relevant knowledge item(s)."

        return AgentEnvelope(
            agent_name=self.name,
            status="success",
            summary=summary,
            payload={
                "rows": rows,
                "prompt_context": prompt_context,
            },
            confidence=0.7 if rows else 0.3,
        )
