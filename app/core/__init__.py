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

    # ── 获取长期记忆（用于报告写作参考）──
    memories = memory_manager.get_long_term_memory(user_id)
    history_text = (
        "\n".join(f"- {m.memory_summary[:300]}" for m in memories[-5:])
        or "（无历史检测记录）"
    )

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
            dialogue=dialogue_text,  # 新增：注入对话历史
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

    # ── 写入长期记忆 ──
    try:
        memory_summary = (state.result.summary or "").strip()[:1500]
        if memory_summary:
            memory_manager.add_long_term_memory(
                LongTermMemory(
                    user_id=user_id,
                    memory_summary=memory_summary,
                    related_tasks=[state.task.task_id],
                )
            )
            state.logs.append(f"[长期记忆] 已写入，摘要长度={len(memory_summary)}")
    except Exception as e:
        logger.warning(f"[长期记忆] 写入失败: {e}")
        state.errors.append(f"memory_write_failed: {e}")

    return state


from app.core.graph import build_graph

__all__ = ["build_graph", "_summarize_node"]
