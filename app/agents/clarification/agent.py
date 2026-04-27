from __future__ import annotations

from app.memory.state import DetectionState
from app.orchestration import AgentEnvelope


class ClarificationAgent:
    name = "clarification"

    async def run(self, state: DetectionState) -> AgentEnvelope:
        items = state.unknown_anomaly_types or ["异常细节"]
        pending_clarification = "请协助确认以下异常项：\n" + "\n".join(f"- {item}" for item in items)
        pending_question = (
            "以上异常仍需人工核实。请补充你观察到的具体现象、位置、严重程度或现场背景，"
            "以便我继续完成诊断。"
        )
        return AgentEnvelope(
            agent_name=self.name,
            status="success",
            summary="Clarification request prepared for the user.",
            payload={
                "pending_clarification": pending_clarification,
                "pending_question": pending_question,
                "unknown_anomaly_types": items,
                "requires_human": True,
            },
            confidence=max(0.0, min(1.0, state.confidence)),
            requires_human=True,
            next_recommendation="wait_user",
        )
