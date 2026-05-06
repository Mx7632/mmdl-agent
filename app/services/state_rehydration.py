from __future__ import annotations

import logging
from typing import Any, Optional

from app.exceptions.base import AppError
from app.memory.conversation import compact_state_conversation
from app.memory.state import DetectionState
from app.analysis.mmad_pipeline import dump_mmad_analysis
from app.orchestration.context_store import get_pending_context_from_mapping
from app.orchestration.context import KnowledgeContext, MMADAnalysisContext
from app.rag.knowledge_pipeline import dump_analysis_contracts

logger = logging.getLogger(__name__)


def extract_analysis_contracts(state_dict: dict[str, Any]) -> dict[str, Any]:
    def read_contracts(source: dict[str, Any]) -> dict[str, Any]:
        knowledge = KnowledgeContext.model_validate(source)
        contracts = dump_analysis_contracts(knowledge)
        return {
            key: value
            for key, value in contracts.items()
            if isinstance(value, dict) and any(item not in (None, "", [], {}) for item in value.values())
        }

    shared_context = state_dict.get("shared_context") or {}
    knowledge = shared_context.get("knowledge") or {}
    if isinstance(knowledge, dict):
        contracts = read_contracts(knowledge)
        if contracts:
            return contracts

    result_obj = state_dict.get("result") or {}
    result_metadata = result_obj.get("metadata", {}) if isinstance(result_obj, dict) else {}
    if isinstance(result_metadata, dict):
        contracts = read_contracts(result_metadata)
        if contracts:
            return contracts

    return {}


def extract_mmad_analysis(state_dict: dict[str, Any]) -> dict[str, Any]:
    def read_mmad(source: Any) -> dict[str, Any]:
        if not isinstance(source, dict) or not source:
            return {}
        return dump_mmad_analysis(MMADAnalysisContext.model_validate(source))

    shared_context = state_dict.get("shared_context") or {}
    if isinstance(shared_context, dict):
        contracts = read_mmad(shared_context.get("mmad_analysis"))
        if contracts:
            return contracts

    result_obj = state_dict.get("result") or {}
    result_metadata = result_obj.get("metadata", {}) if isinstance(result_obj, dict) else {}
    if isinstance(result_metadata, dict):
        contracts = read_mmad(result_metadata.get("mmad_analysis"))
        if contracts:
            return contracts

    return {}


def build_execution_metadata(state_dict: dict[str, Any]) -> dict[str, Any]:
    result_metadata = extract_result_metadata(state_dict.get("result"))
    return {
        "agent_trace": list(state_dict.get("agent_trace", [])),
        "execution_plan": state_dict.get("execution_plan"),
        "step_status": dict(state_dict.get("step_status", {})),
        "step_attempts": dict(state_dict.get("step_attempts", {})),
        "execution_events": list(state_dict.get("execution_events", [])),
        "analysis_contracts": extract_analysis_contracts(state_dict),
        "mmad_analysis": extract_mmad_analysis(state_dict),
        "few_shot": {
            "vision": result_metadata.get("few_shot_examples")
            or result_metadata.get("vision_few_shot", {}).get("examples")
            or {},
            "vision_context": result_metadata.get("few_shot_context")
            or result_metadata.get("vision_few_shot", {}).get("context")
            or "",
            "knowledge": result_metadata.get("knowledge_few_shot", {}).get("examples", {}),
            "knowledge_context": result_metadata.get("knowledge_few_shot", {}).get("context", ""),
        },
    }


def extract_pending_context(state_dict: dict[str, Any]) -> tuple[str | None, str | None]:
    return get_pending_context_from_mapping(state_dict)


def restore_state(state_dict: dict[str, Any]) -> DetectionState:
    try:
        state = DetectionState.model_validate(state_dict)
        if not state.conversation_summary:
            state.conversation_summary = state.context.get("conversation_summary")
        if not state.conversation_compacted_turns:
            state.conversation_compacted_turns = state.context.get("conversation_compacted_turns", 0)
        return state
    except Exception as exc:
        logger.error("[state_rehydration] state restore failed: %s. keys=%s", exc, state_dict.keys())
        raise AppError(f"Task state is corrupted and cannot be restored: {exc}") from exc


def extract_anomalies(result_obj: Any) -> list[Any]:
    if result_obj is None:
        return []
    if isinstance(result_obj, dict):
        return result_obj.get("anomalies", [])
    if hasattr(result_obj, "anomalies"):
        return result_obj.anomalies or []
    return []


def extract_result_metadata(result_obj: Any) -> dict[str, Any]:
    if result_obj is None:
        return {}
    if isinstance(result_obj, dict):
        return result_obj.get("metadata", {}) or {}
    if hasattr(result_obj, "metadata"):
        return result_obj.metadata or {}
    return {}


def prepare_followup_state(
    previous_state: dict[str, Any],
    *,
    question: Optional[str],
    parameters: Optional[dict[str, Any]] = None,
) -> DetectionState:
    state = restore_state(previous_state)
    has_new_image = bool(parameters and parameters.get("image_base64"))
    task_runtime = state.task_runtime()
    task_runtime.task.question = question
    if parameters:
        task_runtime.task.parameters.update(parameters)
    if question:
        task_runtime.conversation_history.append({"role": "user", "content": question})
    task_runtime.report_requested = False
    task_runtime.stage = "chat"
    state.apply_task_runtime(task_runtime)

    domain_runtime = state.domain_runtime()
    domain_runtime.intermediate_steps = []
    domain_runtime.tool_calls = []
    domain_runtime.tool_outputs = []
    domain_runtime.agent_trace = []
    if has_new_image:
        from app.orchestration import SharedContext

        domain_runtime.result = None
        domain_runtime.agent_outputs = {}
        domain_runtime.shared_context = SharedContext()
    state.apply_domain_runtime(domain_runtime)

    orchestration_runtime = state.orchestration_runtime()
    orchestration_runtime.active_agent = None
    orchestration_runtime.execution_plan = None
    orchestration_runtime.step_status = {}
    orchestration_runtime.step_attempts = {}
    orchestration_runtime.step_outputs = {}
    orchestration_runtime.execution_events = []
    orchestration_runtime.last_failed_step = None
    orchestration_runtime.loop_count = 0
    orchestration_runtime.reflection_decision = None
    orchestration_runtime.retry_target = None
    orchestration_runtime.retry_reason = None
    orchestration_runtime.retry_strategy = None
    orchestration_runtime.needs_user_input = False
    state.apply_orchestration_runtime(orchestration_runtime)

    task_runtime = state.task_runtime()
    task_runtime.user_reply = None
    state.apply_task_runtime(task_runtime)
    compact_state_conversation(state)

    return state
