from __future__ import annotations

import logging
from typing import Any

from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field, SecretStr

from app.config.settings import settings
from app.memory.state import DetectionState
from app.utils.json_parser import parse_json_safely

logger = logging.getLogger(__name__)

KNOWLEDGE_KEYWORDS = (
    "原因",
    "建议",
    "案例",
    "风险",
    "维修",
    "repair",
    "reason",
    "knowledge",
)

SUPERVISOR_PLAN_PROMPT = """You supervise an industrial anomaly multi-agent system.

Available agents:
- vision: detect/localize visual anomalies
- knowledge: retrieve similar cases and maintenance knowledge
- clarification: prepare a human clarification request
- report: generate a full report

Rules:
- If report_requested is true, return only ["report"].
- If needs_user_input is true and no clarification request has been prepared, return ["clarification"].
- If there is image input and vision has not run this turn, usually include "vision".
- Include "knowledge" when the user asks about cause, repair, suggestion, risk, or similar cases.
- Do not repeat an already completed specialist in the same turn unless explicitly needed.
- Return strict JSON only.

Format:
{
  "planned_agents": ["vision", "knowledge"],
  "reason": "short reason"
}
"""


class SupervisorPlan(BaseModel):
    planned_agents: list[str] = Field(default_factory=list)
    reason: str | None = None


class SupervisorAgent:
    name = "supervisor"

    def _fallback_plan(self, state: DetectionState) -> list[str]:
        requested: list[str] = []
        has_image = bool((state.task.parameters or {}).get("image_base64"))
        question = (state.task.question or "").lower()
        clarification_ctx = state.shared_context.clarification

        if state.report_requested:
            return ["report"]

        if state.needs_user_input and not (clarification_ctx and clarification_ctx.pending_question):
            return ["clarification"]

        if has_image and not state.agent_outputs.get("vision"):
            requested.append("vision")

        if any(keyword in question for keyword in KNOWLEDGE_KEYWORDS):
            requested.append("knowledge")

        if not requested and has_image and not state.agent_outputs.get("vision"):
            requested.append("vision")

        return requested

    def _build_plan_payload(self, state: DetectionState) -> dict[str, Any]:
        return {
            "task_id": state.task.task_id,
            "question": state.task.question or "",
            "has_image": bool((state.task.parameters or {}).get("image_base64")),
            "report_requested": state.report_requested,
            "needs_user_input": state.needs_user_input,
            "unknown_anomaly_types": list(state.unknown_anomaly_types),
            "existing_agent_outputs": list(state.agent_outputs.keys()),
            "agent_trace": list(state.agent_trace),
            "shared_context": state.shared_context.model_dump(exclude_none=True),
            "confidence": state.confidence,
        }

    def plan(self, state: DetectionState) -> list[str]:
        if not settings.openai_api_key:
            return self._fallback_plan(state)

        try:
            llm = ChatOpenAI(
                model=settings.llm_model,
                temperature=0.0,
                api_key=SecretStr(settings.openai_api_key),
                timeout=settings.llm_timeout,
                max_tokens=300,
                base_url=settings.llm_base_url,
                extra_body={"enable_thinking": False},
            )
            response = llm.invoke(
                [
                    {"role": "system", "content": SUPERVISOR_PLAN_PROMPT},
                    {"role": "user", "content": str(self._build_plan_payload(state))},
                ]
            )
            parsed = parse_json_safely(getattr(response, "content", "") or "")
            if not parsed:
                return self._fallback_plan(state)

            plan = SupervisorPlan.model_validate(parsed)
            planned_agents: list[str] = []
            for item in plan.planned_agents:
                if item in {"vision", "knowledge", "clarification", "report"} and item not in planned_agents:
                    planned_agents.append(item)

            if plan.reason:
                state.context["supervisor_reason"] = plan.reason
            return planned_agents
        except Exception as exc:
            logger.warning("[Supervisor] LLM planning failed, fallback to rules: %s", exc)
            return self._fallback_plan(state)
