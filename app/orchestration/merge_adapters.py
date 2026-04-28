from __future__ import annotations

from app.memory.state import DetectionState
from app.orchestration.context_store import set_pending_clarification, set_prompt_context
from app.schemas.detection import DetectionResult


def ensure_result(state: DetectionState) -> DetectionResult:
    domain = state.domain_runtime()
    if domain.result is None:
        default_status = "success" if domain.agent_outputs else ("failed" if state.last_failed_step else "success")
        domain.result = DetectionResult(task_id=state.task.task_id, status=default_status)
        state.apply_domain_runtime(domain)
    return state.result


def merge_vision_output(state: DetectionState, payload: dict, result: DetectionResult) -> None:
    domain = state.domain_runtime()
    domain.tool_outputs.append({"tool": "vision_agent", "anomalies": payload.get("anomalies", [])})
    domain.shared_context["vision"] = payload
    state.apply_domain_runtime(domain)
    result.status = "success"
    result.anomalies = list(payload.get("anomalies", []))
    if payload.get("answer"):
        result.answer = payload["answer"]
    if payload.get("metadata"):
        result.metadata.update(payload["metadata"])


def merge_knowledge_output(state: DetectionState, payload: dict, result: DetectionResult) -> None:
    del result
    domain = state.domain_runtime()
    domain.shared_context["knowledge"] = payload
    state.apply_domain_runtime(domain)
    set_prompt_context(state, payload.get("prompt_context", state.context.get("rag_context")))


def merge_clarification_output(state: DetectionState, payload: dict, result: DetectionResult) -> None:
    del result
    domain = state.domain_runtime()
    domain.shared_context["clarification"] = payload
    state.apply_domain_runtime(domain)
    orchestration = state.orchestration_runtime()
    orchestration.unknown_anomaly_types = payload.get("unknown_anomaly_types", orchestration.unknown_anomaly_types)
    orchestration.needs_user_input = bool(payload.get("requires_human", True))
    state.apply_orchestration_runtime(orchestration)
    set_pending_clarification(
        state,
        pending_clarification=payload.get("pending_clarification"),
        pending_question=payload.get("pending_question"),
        unknown_anomaly_types=payload.get("unknown_anomaly_types"),
        requires_human=state.needs_user_input,
    )


def merge_report_output(state: DetectionState, payload: dict, result: DetectionResult) -> None:
    domain = state.domain_runtime()
    domain.shared_context["report"] = payload
    state.apply_domain_runtime(domain)
    result.summary = payload.get("summary", result.summary)
    if payload.get("metadata"):
        result.metadata.update(payload["metadata"])


MERGE_ADAPTERS = {
    "vision": merge_vision_output,
    "knowledge": merge_knowledge_output,
    "clarification": merge_clarification_output,
    "report": merge_report_output,
}


async def supervisor_merge_node(state: DetectionState) -> DetectionState:
    result = ensure_result(state)
    for agent_name, merge_adapter in MERGE_ADAPTERS.items():
        output = state.agent_outputs.get(agent_name) or {}
        if not output:
            continue
        payload = output.get("payload", {})
        merge_adapter(state, payload, result)

    state.context["agent_trace"] = list(state.agent_trace)
    state.context["step_status"] = dict(state.step_status)
    state.context["step_attempts"] = dict(state.step_attempts)
    state.context["execution_events"] = list(state.execution_events)
    state.logs.append(f"[Supervisor] Merge complete, agent outputs={list(state.agent_outputs.keys())}")
    return state
