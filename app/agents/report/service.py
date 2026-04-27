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

    if state.context.get("conversation_summary"):
        dialogue_text = (
            f"[Earlier conversation summary]\n{state.context['conversation_summary']}\n\n"
            f"{dialogue_text}"
        )

    rag_context = get_prompt_context(state) or "(no RAG retrieval context)"

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
            history=history_text,
            dialogue=dialogue_text,
            rag_context=rag_context,
        )
        response = await llm.ainvoke(messages)
        summary = getattr(response, "content", str(response)) or ""

        if summary:
            result.summary = summary
            result.metadata["loop_count"] = orchestration_runtime.loop_count
            result.metadata["confidence"] = orchestration_runtime.confidence
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
