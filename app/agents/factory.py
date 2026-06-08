from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.agents.supervisor import SupervisorAgent


def get_supervisor_agent() -> SupervisorAgent:
    from app.agents.supervisor import SupervisorAgent

    return SupervisorAgent()


def get_specialist_agents() -> dict[str, object]:
    from app.agents.clarification import ClarificationAgent
    from app.agents.knowledge import KnowledgeAgent
    from app.agents.report import ReportAgent
    from app.agents.vision import VisionAgent

    return {
        "vision": VisionAgent(),
        "knowledge": KnowledgeAgent(),
        "clarification": ClarificationAgent(),
        "report": ReportAgent(),
    }
