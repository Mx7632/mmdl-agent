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
from app.prompts.image_report import IMAGE_REPORT_PROMPT
from app.schemas.detection import DetectionResult

logger = logging.getLogger(__name__)


def _ensure_result_from_shared_context(state: DetectionState) -> DetectionResult:
    if state.result is None:
        state.result = DetectionResult(task_id=state.task.task_id, status="success")

    vision_ctx = state.shared_context.vision
    if vision_ctx and vision_ctx.anomalies and not state.result.anomalies:
        state.result.anomalies = list(vision_ctx.anomalies)
    if vision_ctx and vision_ctx.metadata:
        state.result.metadata.update(vision_ctx.metadata)
    if vision_ctx and vision_ctx.answer and not state.result.answer:
        state.result.answer = vision_ctx.answer

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

    if asset_id and short_term_text != "（无历史检测记录）":
        history_parts.append(f"【中期记忆（同设备近期检测）】\n{short_term_text}")
    if long_term_text != "（无长期记忆）":
        history_parts.append(f"【长期记忆】\n{long_term_text}")
    if asset_id and tool_effect_text != "（无历史工具调用记录）":
        history_parts.append(f"【工具效果追踪】\n{tool_effect_text}")

    return "\n\n".join(history_parts) or "（无历史检测记录）"


async def generate_report_state(state: DetectionState) -> DetectionState:
    result = _ensure_result_from_shared_context(state)

    if not settings.openai_api_key:
        raise ConfigurationError(
            "openai_api_key 未配置",
            config_key="APP_OPENAI_API_KEY",
        )

    user_id = (state.task.parameters or {}).get("user_id") or DEFAULT_USER_ID
    asset_id = state.task.asset_id
    history_text = _build_history_text(state, user_id=user_id, asset_id=asset_id)

    if state.conversation_history:
        dialogue_text = "\n".join(
            f"[{item['role']}] {item['content']}"
            for item in state.conversation_history
            if item.get("content")
        )
        state.logs.append(f"[Report] Included {len(state.conversation_history)} conversation turn(s)")
    else:
        dialogue_text = "（无对话补充）"

    rag_context = (
        state.shared_context.knowledge.prompt_context
        if state.shared_context.knowledge and state.shared_context.knowledge.prompt_context
        else state.context.get("rag_context", "（无 RAG 检索结果）")
    )

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
            task_id=state.task.task_id,
            asset_id=state.task.asset_id,
            start_time=state.task.start_time,
            end_time=state.task.end_time,
            question=state.task.question or "",
            anomalies=result.anomalies,
            history=history_text,
            dialogue=dialogue_text,
            rag_context=rag_context,
        )
        response = await llm.ainvoke(messages)
        summary = getattr(response, "content", str(response)) or ""

        if summary:
            result.summary = summary
            result.metadata["loop_count"] = state.loop_count
            result.metadata["confidence"] = state.confidence
            state.logs.append(
                f"[Report] Completed with loop_count={state.loop_count}, confidence={state.confidence:.2f}"
            )
        else:
            result.summary = "报告生成内容为空。"
            state.errors.append("summary LLM returned empty content")
    except Exception as exc:
        logger.error(f"[Report] LLM call failed: {exc}")
        result.summary = "报告生成失败（LLM 不可用或鉴权失败）。"
        result.metadata = dict(result.metadata or {})
        result.metadata["summary_failed"] = True
        state.errors.append(f"summary_failed: {exc}")
        return state

    try:
        memory_summary = (result.summary or "").strip()[:1500]
        if memory_summary:
            anomaly_types = list(
                {
                    item.get("type", "未知")
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
                        "confidence": state.confidence,
                        "loop_count": state.loop_count,
                    },
                    tags=anomaly_types,
                    related_tasks=[state.task.task_id],
                )
            )
            state.logs.append(
                f"[LongTermMemory] Saved report memory for asset_id={asset_id or 'unknown'}"
            )
    except Exception as exc:
        logger.warning(f"[LongTermMemory] Failed to persist report memory: {exc}")
        state.errors.append(f"memory_write_failed: {exc}")

    state.shared_context["report"] = {
        "summary": result.summary,
        "anomalies": result.anomalies,
        "metadata": result.metadata,
    }
    return state
