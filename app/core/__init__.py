"""
app/core 包初始化
导出 build_graph 和 _summarize_node（供 graph.py 内部使用）。
"""

from __future__ import annotations

import logging

from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from app.config.settings import settings
from app.memory.config import DEFAULT_USER_ID
from app.memory.memory_manager import memory_manager
from app.memory.models import LongTermMemory
from app.memory.state import DetectionState
from app.exceptions.base import ConfigurationError
from app.prompts.image_report import IMAGE_REPORT_PROMPT

logger = logging.getLogger(__name__)


async def _summarize_node(state: DetectionState) -> DetectionState:
    """
    报告生成节点（Summary Node）。

    职责：
      1. 调用 LLM 生成检测报告
      2. 将对话历史（conversation_history）注入 prompt
      3. 成功后写入长期记忆（LongTermMemory）
      4. 出错时降级，不阻塞返回结果
    """
    if not state.result:
        state.logs.append("[报告生成] 无检测结果，跳过")
        return state

    if not settings.openai_api_key:
        raise ConfigurationError(
            "openai_api_key 未配置",
            config_key="APP_OPENAI_API_KEY",
        )

    user_id = (state.task.parameters or {}).get("user_id") or DEFAULT_USER_ID
    asset_id = state.task.asset_id

    # ── 获取三层记忆上下文（【优化】统一入口）──
    mem_ctx = memory_manager.build_memory_context(
        user_id=user_id,
        asset_id=asset_id,
        task_id=state.task.task_id,
    )
    short_term_text = mem_ctx["short_term"]
    long_term_text = mem_ctx["long_term"]
    tool_effect_text = mem_ctx["tool_effect"]

    # ── 合并为历史参考文本 ──
    history_parts = []
    if asset_id and short_term_text != "（无历史检测记录）":
        history_parts.append(f"【中期记忆（同设备近期检测）】\n{short_term_text}")
    if long_term_text != "（无长期记忆）":
        history_parts.append(f"【长期记忆】\n{long_term_text}")
    if asset_id and tool_effect_text != "（无历史工具调用记录）":
        history_parts.append(f"【工具效果追踪】\n{tool_effect_text}")
    history_text = "\n\n".join(history_parts) or "（无历史检测记录）"

    # ── 获取对话历史（用于报告补充）──
    if state.conversation_history:
        dialogue_lines = [
            f"[{m['role']}] {m['content']}"
            for m in state.conversation_history
            if m.get("content")
        ]
        dialogue_text = "\n".join(dialogue_lines)
        state.logs.append(f"[报告生成] 包含 {len(state.conversation_history)} 条对话历史")
    else:
        dialogue_text = "（无对话补充）"

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
            anomalies=state.result.anomalies,
            history=history_text,
            dialogue=dialogue_text,
            rag_context=state.context.get("rag_context", "（无 RAG 检索结果）"),
        )

        response = await llm.ainvoke(messages)
        summary = getattr(response, "content", str(response)) or ""

        if summary:
            state.result.summary = summary
            state.result.metadata["loop_count"] = state.loop_count
            state.result.metadata["confidence"] = state.confidence
            state.logs.append(
                f"[报告生成] 完成，循环次数={state.loop_count}，置信度={state.confidence:.2f}"
            )
        else:
            state.result.summary = "报告生成内容为空。"
            state.errors.append("summary LLM 返回内容为空")

    except Exception as e:
        logger.error(f"[报告生成] LLM 调用失败: {e}")
        state.result.summary = "报告生成失败（LLM 不可用或鉴权失败）。"
        state.result.metadata = dict(state.result.metadata or {})
        state.result.metadata["summary_failed"] = True
        state.errors.append(f"summary_failed: {e}")
        return state

    # ── 长期记忆写入 ──
    try:
        asset_id = state.task.asset_id or "unknown"
        memory_summary = (state.result.summary or "").strip()[:1500]
        if memory_summary:
            anomaly_types = list({
                a.get("type", "未知") if isinstance(a, dict) else (a.type if hasattr(a, "type") else "未知")
                for a in (state.result.anomalies or [])
            })
            memory_manager.add_long_term_memory(
                LongTermMemory(
                    user_id=user_id,
                    asset_id=asset_id,
                    memory_summary=memory_summary,
                    memory_details={
                        "status": state.result.status,
                        "anomalies": state.result.anomalies or [],
                        "confidence": state.confidence,
                        "loop_count": state.loop_count,
                    },
                    tags=anomaly_types,
                    related_tasks=[state.task.task_id],
                )
            )
            state.logs.append(
                f"[长期记忆] 已写入，asset_id={asset_id}，"
                f"标签={anomaly_types}，摘要长度={len(memory_summary)}"
            )
    except Exception as e:
        logger.warning(f"[长期记忆] 写入失败: {e}")
        state.errors.append(f"memory_write_failed: {e}")

    return state


from app.core.graph import build_graph

__all__ = ["build_graph", "_summarize_node"]
