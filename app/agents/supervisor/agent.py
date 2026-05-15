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
    "rag",
    "RAG",
    "检索",
    "知识库",
    "相似",
    "严重",
    "影响",
    "为什么",
    "怎么处理",
    "如何处理",
    "是否使用",
    "有没有使用",
    "追问",
    "repair",
    "reason",
    "knowledge",
    "retrieve",
    "similar",
    "risk",
    "suggestion",
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
- For follow-up questions, regenerate the answer for the current question; include "knowledge" when the follow-up asks about RAG, retrieval, cause, risk, suggestion, or similar cases.
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


class SupervisorStep(BaseModel):
    id: str
    agent: str
    goal: str
    depends_on: list[str] = Field(default_factory=list)
    retryable: bool = True


class SupervisorExecutionPlan(BaseModel):
    steps: list[SupervisorStep] = Field(default_factory=list)
    reason: str | None = None
    stop_when_confident: bool = True


class SupervisorAgent:
    name = "supervisor"

    def _followup_needs_knowledge(self, state: DetectionState, question: str) -> bool:
        if not state.context.get("is_followup"):
            return False
        has_new_image = bool(state.context.get("has_new_image"))
        if has_new_image:
            return False
        return any(keyword.lower() in question for keyword in KNOWLEDGE_KEYWORDS)

    def _goal_for_agent(self, agent_name: str, state: DetectionState) -> str:
        orchestration = state.orchestration_runtime()
        if agent_name == "vision":
            if orchestration.retry_target == "vision":
                return f"重新执行视觉异常分析（策略：{orchestration.retry_strategy or 'rerun'}）"
            return "检测并定位图像中的异常区域"
        if agent_name == "knowledge":
            return "检索相似案例、知识库与维修建议"
        if agent_name == "clarification":
            return "生成结构化澄清问题，等待用户补充信息"
        if agent_name == "report":
            return "生成完整技术报告"
        return f"执行 {agent_name}"

    def _build_execution_plan(
        self,
        state: DetectionState,
        planned_agents: list[str],
        *,
        reason: str | None = None,
    ) -> SupervisorExecutionPlan:
        steps: list[SupervisorStep] = []
        prior_step_id: str | None = None
        orchestration = state.orchestration_runtime()

        for index, agent_name in enumerate(planned_agents, start=1):
            attempt = orchestration.step_attempts.get(agent_name, 0) + 1
            step_id = f"{agent_name}-{attempt}"
            depends_on = [prior_step_id] if prior_step_id and agent_name == "knowledge" else []
            if orchestration.retry_target and orchestration.retry_target == agent_name:
                depends_on = []

            steps.append(
                SupervisorStep(
                    id=step_id,
                    agent=agent_name,
                    goal=self._goal_for_agent(agent_name, state),
                    depends_on=depends_on,
                    retryable=agent_name != "report",
                )
            )
            prior_step_id = step_id

        return SupervisorExecutionPlan(steps=steps, reason=reason, stop_when_confident=True)

    def _fallback_plan(self, state: DetectionState) -> SupervisorExecutionPlan:
        requested: list[str] = []
        task_runtime = state.task_runtime()
        orchestration = state.orchestration_runtime()
        domain = state.domain_runtime()
        has_image = bool((task_runtime.task.parameters or {}).get("image_base64"))
        question = (task_runtime.task.question or "").lower()
        clarification_ctx = domain.shared_context.clarification

        if task_runtime.report_requested:
            return self._build_execution_plan(state, ["report"], reason="用户请求生成报告")

        if orchestration.reflection_decision == "retry" and orchestration.retry_target:
            return self._build_execution_plan(
                state,
                [orchestration.retry_target],
                reason=orchestration.retry_reason or "自反思节点要求重试",
            )

        if orchestration.needs_user_input and not (clarification_ctx and clarification_ctx.pending_question):
            return self._build_execution_plan(
                state,
                ["clarification"],
                reason="继续执行前需要先生成澄清问题",
            )

        if has_image and not domain.agent_outputs.get("vision"):
            requested.append("vision")

        if any(keyword.lower() in question for keyword in KNOWLEDGE_KEYWORDS):
            requested.append("knowledge")

        if self._followup_needs_knowledge(state, question) and "knowledge" not in requested:
            requested.append("knowledge")

        if not requested and has_image and not domain.agent_outputs.get("vision"):
            requested.append("vision")

        return self._build_execution_plan(state, requested, reason="规则回退路由")

    def _build_plan_payload(self, state: DetectionState) -> dict[str, Any]:
        task_runtime = state.task_runtime()
        orchestration = state.orchestration_runtime()
        domain = state.domain_runtime()
        return {
            "task_id": task_runtime.task.task_id,
            "question": task_runtime.task.question or "",
            "is_followup": bool(state.context.get("is_followup")),
            "latest_question": state.context.get("latest_question") or task_runtime.task.question or "",
            "has_new_image": bool(state.context.get("has_new_image")),
            "has_image": bool((task_runtime.task.parameters or {}).get("image_base64")),
            "report_requested": task_runtime.report_requested,
            "needs_user_input": orchestration.needs_user_input,
            "unknown_anomaly_types": list(orchestration.unknown_anomaly_types),
            "existing_agent_outputs": list(domain.agent_outputs.keys()),
            "agent_trace": list(domain.agent_trace),
            "shared_context": domain.shared_context.model_dump(exclude_none=True),
            "confidence": orchestration.confidence,
        }

    def plan(self, state: DetectionState) -> SupervisorExecutionPlan:
        orchestration = state.orchestration_runtime()
        if orchestration.reflection_decision == "retry" and orchestration.retry_target:
            return self._build_execution_plan(
                state,
                [orchestration.retry_target],
                reason=orchestration.retry_reason or "自反思节点要求重试",
            )

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
            if not planned_agents and self._followup_needs_knowledge(
                state,
                (state.task_runtime().task.question or "").lower(),
            ):
                planned_agents.append("knowledge")

            if plan.reason:
                state.context["supervisor_reason"] = plan.reason
            return self._build_execution_plan(state, planned_agents, reason=plan.reason)
        except Exception as exc:
            logger.warning("[Supervisor] LLM planning failed, fallback to rules: %s", exc)
            return self._fallback_plan(state)
