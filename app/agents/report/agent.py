from __future__ import annotations

from app.orchestration import AgentEnvelope
from app.memory.state import DetectionState
from app.core import _summarize_node


class ReportAgent:
    name = "report"

    async def run(self, state: DetectionState) -> AgentEnvelope:
        updated = await _summarize_node(state)
        result = updated.result
        return AgentEnvelope(
            agent_name=self.name,
            status="success",
            summary=result.summary if result else None,
            payload={
                "summary": result.summary if result else None,
                "anomalies": result.anomalies if result else [],
                "metadata": result.metadata if result else {},
            },
            confidence=float(updated.confidence or 0.0),
        )
