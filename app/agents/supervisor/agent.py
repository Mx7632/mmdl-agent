from __future__ import annotations

from app.memory.state import DetectionState


class SupervisorAgent:
    name = "supervisor"

    def plan(self, state: DetectionState) -> list[str]:
        """Return the next specialist agents to execute for the current turn."""
        requested: list[str] = []
        has_image = bool((state.task.parameters or {}).get("image_base64"))
        question = (state.task.question or "").lower()

        if state.report_requested:
            return ["report"]

        if has_image and not state.agent_outputs.get("vision"):
            requested.append("vision")

        knowledge_keywords = ("原因", "建议", "案例", "风险", "维修", "原因", "reason", "repair")
        if any(keyword in question for keyword in knowledge_keywords):
            requested.append("knowledge")

        if not requested and has_image:
            requested.append("vision")

        return requested
