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

SUPERVISOR_PLAN_PROMPT = """You are the supervisor of an industrial anomaly diagnosis multi-agent system.

Choose which specialist agents should run next for the current user turn.

Available agents:
- vision: image anomaly detection and localization
- knowledge: retrieve similar cases / maintenance knowledge
- report: generate the full technical report

Rules:
- If report_requested is true, return only ["report"].
- If there is image input and vision has not been executed for this turn, usually include "vision".
- Include "knowledge" when the user asks about cause, repair, suggestions, risk, similar cases, or when richer context would help explain anomalies.
- Do not schedule the same specialist twice in one turn.
- If no specialist is needed, return an empty list.

Return strict JSON only:
{{
  "planned_agents": ["vision", "knowledge"],
  "reason": "short reason"
}}
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

        if state.report_requested:
            return ["report"]

        if has_image and not state.agent_outputs.get("vision"):
            requested.append("vision")

        if any(keyword in question for keyword in KNOWLEDGE_KEYWORDS):
            requested.append("knowledge")

        if not requested and has_image:
            requested.append("vision")

        return requested

    def _build_plan_payload(self, state: DetectionState) -> dict[str, Any]:
        question = state.task.question or ""
        parameters = state.task.parameters or {}
        has_image = bool(parameters.get("image_base64"))
        vision_done = bool(state.agent_outputs.get("vision"))
        knowledge_done = bool(state.agent_outputs.get("knowledge"))

        return {
            "task_id": state.task.task_id,
            "question": question,
            "has_image": has_image,
            "report_requested": state.report_requested,
            "current_stage": state.stage,
            "existing_agent_outputs": list(state.agent_outputs.keys()),
            "vision_done": vision_done,
            "knowledge_done": knowledge_done,
            "vision_summary": (state.agent_outputs.get("vision") or {}).get("summary"),
            "knowledge_summary": (state.agent_outputs.get("knowledge") or {}).get("summary"),
        }

    def plan(self, state: DetectionState) -> list[str]:
        if state.report_requested:
            return ["report"]

        if not settings.openai_api_key:
            return self._fallback_plan(state)

        payload = self._build_plan_payload(state)

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
                    {"role": "user", "content": str(payload)},
                ]
            )
            parsed = parse_json_safely(getattr(response, "content", "") or "")
            if not parsed:
                return self._fallback_plan(state)

            plan = SupervisorPlan.model_validate(parsed)
            planned_agents: list[str] = []
            for item in plan.planned_agents:
                if item in {"vision", "knowledge", "report"} and item not in planned_agents:
                    planned_agents.append(item)

            if plan.reason:
                state.context["supervisor_reason"] = plan.reason
            return planned_agents
        except Exception as exc:
            logger.warning("[Supervisor] LLM planning failed, fallback to rules: %s", exc)
            return self._fallback_plan(state)
