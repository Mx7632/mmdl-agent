from __future__ import annotations

import logging

from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from app.config.settings import settings
from app.exceptions.base import ConfigurationError
from app.memory.config import DEFAULT_USER_ID
from app.memory.memory_manager import memory_manager
from app.memory.models import LongTermMemory
from app.memory.state import DetectionState
from app.orchestration.context_store import get_prompt_context
from app.prompts.image_report import IMAGE_REPORT_PROMPT
from app.schemas.detection import DetectionResult

logger = logging.getLogger(__name__)


def _ensure_result_from_shared_context(state: DetectionState) -> DetectionResult:
    domain_runtime = state.domain_runtime()
    if domain_runtime.result is None:
        domain_runtime.result = DetectionResult(task_id=state.task.task_id, status="success")

    vision_ctx = domain_runtime.shared_context.vision
    if vision_ctx and vision_ctx.anomalies and not domain_runtime.result.anomalies:
        domain_runtime.result.anomalies = list(vision_ctx.anomalies)
    if vision_ctx and vision_ctx.metadata:
        domain_runtime.result.metadata.update(vision_ctx.metadata)
    if vision_ctx and vision_ctx.answer and not domain_runtime.result.answer:
        domain_runtime.result.answer = vision_ctx.answer

    state.apply_domain_runtime(domain_runtime)
    return state.result


def _build_history_text(state: DetectionState, *, user_id: str, asset_id: str | None) -> str:
    mem_ctx = memory_manager.build_memory_context(
        user_id=user_id,
        asset_id=asset_id,
        task_id=state.task.task_id,
    )

    history_parts: list[str] = []
    short_term_text = mem_ctx["short_term"]
    long_term_text = mem_ctx["long_term"]
    tool_effect_text = mem_ctx["tool_effect"]

    if asset_id and short_term_text != "(no historical detection records)":
        history_parts.append(f"[Short-term memory]\n{short_term_text}")
    if long_term_text != "(no long-term memory)":
        history_parts.append(f"[Long-term memory]\n{long_term_text}")
    if asset_id and tool_effect_text != "(no historical tool traces)":
        history_parts.append(f"[Tool effectiveness]\n{tool_effect_text}")

    return "\n\n".join(history_parts) or "(no historical detection records)"


def _collect_defect_descriptions(anomalies: list[dict]) -> list[str]:
    descriptions: list[str] = []
    for item in anomalies or []:
        if not isinstance(item, dict):
            continue
        description = item.get("description")
        if description:
            descriptions.append(str(description))
    return descriptions


def _build_defect_description_block(anomalies: list[dict]) -> str:
    descriptions = _collect_defect_descriptions(anomalies)
    if not descriptions:
        return "(no structured defect descriptions)"
    return "\n".join(f"- {item}" for item in descriptions)


def _build_defect_analysis_block(state: DetectionState) -> str:
    knowledge_ctx = state.domain_runtime().shared_context.knowledge
    if not knowledge_ctx:
        return "(no structured defect analysis)"

    defect_block = knowledge_ctx.defect_analysis or {}
    object_block = knowledge_ctx.object_analysis or {}
    sections: list[str] = []
    defect_summary = defect_block.get("analysis_summary") or knowledge_ctx.analysis_summary
    object_summary = object_block.get("object_summary") or knowledge_ctx.object_summary
    object_knowledge_summary = object_block.get("object_knowledge_summary") or knowledge_ctx.object_knowledge_summary
    object_knowledge_hits = object_block.get("object_knowledge_hits") or knowledge_ctx.object_knowledge_hits
    component_scope = object_block.get("component_scope") or knowledge_ctx.component_scope
    component_findings = object_block.get("component_findings") or knowledge_ctx.component_findings
    functional_impact = object_block.get("functional_impact") or knowledge_ctx.functional_impact
    object_knowledge_notes = object_block.get("object_knowledge_notes") or knowledge_ctx.object_knowledge_notes
    similar_cases = defect_block.get("similar_cases") or knowledge_ctx.similar_cases
    possible_causes = defect_block.get("possible_causes") or knowledge_ctx.possible_causes
    risk_notes = defect_block.get("risk_notes") or knowledge_ctx.risk_notes
    repair_actions = defect_block.get("repair_actions") or knowledge_ctx.repair_actions

    if defect_summary:
        sections.append(f"[Analysis summary]\n{defect_summary}")
    if object_summary:
        sections.append(f"[Object summary]\n{object_summary}")
    if object_knowledge_summary:
        sections.append(f"[Object knowledge summary]\n{object_knowledge_summary}")
    if object_knowledge_hits:
        sections.append(
            "[Object knowledge hits]\n"
            + "\n".join(
                f"- {item.get('title')}: {item.get('note')}"
                for item in object_knowledge_hits
            )
        )
    if component_scope:
        sections.append("[Component scope]\n" + "\n".join(f"- {item}" for item in component_scope))
    if component_findings:
        sections.append(
            "[Component findings]\n"
            + "\n".join(
                f"- {item.get('location')} 对应 {item.get('component')}，异常类型 {item.get('anomaly_type')}"
                for item in component_findings
            )
        )
    if functional_impact:
        sections.append("[Component impact assessment]\n" + "\n".join(f"- {item}" for item in functional_impact))
    if object_knowledge_notes:
        sections.append("[Object knowledge]\n" + "\n".join(f"- {item}" for item in object_knowledge_notes))
    if similar_cases:
        sections.append(
            "[Similar cases]\n"
            + "\n".join(f"- {item.get('summary') or item.get('id')}" for item in similar_cases)
        )
    if possible_causes:
        sections.append("[Possible causes]\n" + "\n".join(f"- {item}" for item in possible_causes))
    if risk_notes:
        sections.append("[Risk notes]\n" + "\n".join(f"- {item}" for item in risk_notes))
    if repair_actions:
        sections.append("[Repair actions]\n" + "\n".join(f"- {item}" for item in repair_actions))

    return "\n\n".join(sections) if sections else "(no structured defect analysis)"


def _build_analysis_metadata(state: DetectionState) -> dict[str, object]:
    knowledge_ctx = state.domain_runtime().shared_context.knowledge
    if not knowledge_ctx:
        return {}

    defect_block = knowledge_ctx.defect_analysis or {}
    object_block = knowledge_ctx.object_analysis or {}
    return {
        "defect_analysis": {
            "similar_cases": list(defect_block.get("similar_cases") or knowledge_ctx.similar_cases),
            "possible_causes": list(defect_block.get("possible_causes") or knowledge_ctx.possible_causes),
            "risk_notes": list(defect_block.get("risk_notes") or knowledge_ctx.risk_notes),
            "repair_actions": list(defect_block.get("repair_actions") or knowledge_ctx.repair_actions),
            "analysis_summary": defect_block.get("analysis_summary") or knowledge_ctx.analysis_summary,
        },
        "object_analysis": {
            "object_profile": dict(object_block.get("object_profile") or knowledge_ctx.object_profile),
            "component_scope": list(object_block.get("component_scope") or knowledge_ctx.component_scope),
            "component_findings": list(object_block.get("component_findings") or knowledge_ctx.component_findings),
            "functional_impact": list(object_block.get("functional_impact") or knowledge_ctx.functional_impact),
            "object_summary": object_block.get("object_summary") or knowledge_ctx.object_summary,
            "object_knowledge_notes": list(
                object_block.get("object_knowledge_notes") or knowledge_ctx.object_knowledge_notes
            ),
            "object_knowledge_hits": list(
                object_block.get("object_knowledge_hits") or knowledge_ctx.object_knowledge_hits
            ),
            "object_knowledge_summary": (
                object_block.get("object_knowledge_summary") or knowledge_ctx.object_knowledge_summary
            ),
        },
    }


async def generate_report_state(state: DetectionState) -> DetectionState:
    result = _ensure_result_from_shared_context(state)
    task_runtime = state.task_runtime()
    orchestration_runtime = state.orchestration_runtime()
    domain_runtime = state.domain_runtime()

    if not settings.openai_api_key:
        raise ConfigurationError(
            "openai_api_key is not configured",
            config_key="APP_OPENAI_API_KEY",
        )

    user_id = (task_runtime.task.parameters or {}).get("user_id") or DEFAULT_USER_ID
    asset_id = task_runtime.task.asset_id
    history_text = _build_history_text(state, user_id=user_id, asset_id=asset_id)

    if task_runtime.conversation_history:
        dialogue_text = "\n".join(
            f"[{item['role']}] {item['content']}"
            for item in task_runtime.conversation_history
            if item.get("content")
        )
        state.logs.append(f"[Report] Included {len(task_runtime.conversation_history)} conversation turn(s)")
    else:
        dialogue_text = "(no follow-up dialogue)"

    if task_runtime.conversation_summary:
        dialogue_text = (
            f"[Earlier conversation summary]\n{task_runtime.conversation_summary}\n\n"
            f"{dialogue_text}"
        )

    rag_context = get_prompt_context(state) or "(no RAG retrieval context)"
    defect_description_text = _build_defect_description_block(result.anomalies or [])
    defect_analysis_text = _build_defect_analysis_block(state)

    llm = ChatOpenAI(
        model=settings.llm_model,
        temperature=settings.llm_temperature,
        api_key=SecretStr(settings.openai_api_key),
        timeout=settings.llm_timeout,
        max_tokens=settings.llm_max_tokens,
        base_url=settings.llm_base_url,
        extra_body={"enable_thinking": False},
    )

    try:
        messages = IMAGE_REPORT_PROMPT.format_messages(
            task_id=task_runtime.task.task_id,
            asset_id=task_runtime.task.asset_id,
            start_time=task_runtime.task.start_time,
            end_time=task_runtime.task.end_time,
            question=task_runtime.task.question or "",
            anomalies=result.anomalies,
            history=(
                f"{history_text}\n\n"
                f"[Structured defect descriptions]\n{defect_description_text}\n\n"
                f"[Structured defect analysis]\n{defect_analysis_text}"
            ),
            dialogue=dialogue_text,
            rag_context=f"{rag_context}\n\n[Structured defect analysis]\n{defect_analysis_text}",
        )
        response = await llm.ainvoke(messages)
        summary = getattr(response, "content", str(response)) or ""

        if summary:
            result.summary = summary
            result.metadata["loop_count"] = orchestration_runtime.loop_count
            result.metadata["confidence"] = orchestration_runtime.confidence
            if result.anomalies:
                result.metadata["defect_descriptions"] = _collect_defect_descriptions(result.anomalies)
            result.metadata["defect_analysis_text"] = defect_analysis_text
            result.metadata.update(_build_analysis_metadata(state))
            state.logs.append(
                f"[Report] Completed with loop_count={orchestration_runtime.loop_count}, confidence={orchestration_runtime.confidence:.2f}"
            )
        else:
            result.summary = "Report generation returned empty content."
            state.errors.append("summary LLM returned empty content")
    except Exception as exc:
        logger.error("[Report] LLM call failed: %s", exc)
        result.summary = "Report generation failed because the LLM was unavailable or unauthorized."
        result.metadata = dict(result.metadata or {})
        result.metadata["summary_failed"] = True
        state.errors.append(f"summary_failed: {exc}")
        domain_runtime.result = result
        state.apply_domain_runtime(domain_runtime)
        return state

    try:
        memory_summary = (result.summary or "").strip()[:1500]
        if memory_summary:
            anomaly_types = list(
                {
                    item.get("type", "unknown")
                    for item in (result.anomalies or [])
                    if isinstance(item, dict)
                }
            )
            memory_manager.add_long_term_memory(
                LongTermMemory(
                    user_id=user_id,
                    asset_id=asset_id or "unknown",
                    memory_summary=memory_summary,
                    memory_details={
                        "status": result.status,
                        "anomalies": result.anomalies or [],
                        "confidence": orchestration_runtime.confidence,
                        "loop_count": orchestration_runtime.loop_count,
                    },
                    tags=anomaly_types,
                    related_tasks=[task_runtime.task.task_id],
                )
            )
            state.logs.append(
                f"[LongTermMemory] Saved report memory for asset_id={asset_id or 'unknown'}"
            )
    except Exception as exc:
        logger.warning("[LongTermMemory] Failed to persist report memory: %s", exc)
        state.errors.append(f"memory_write_failed: {exc}")

    domain_runtime.result = result
    domain_runtime.shared_context["report"] = {
        "summary": result.summary,
        "anomalies": result.anomalies,
        "metadata": result.metadata,
    }
    state.apply_domain_runtime(domain_runtime)
    return state
