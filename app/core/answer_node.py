"""
对话回答节点（Answer Node）
职责：
  - 基于检测结果回答用户问题
  - 只返回简洁回答，不生成完整报告
  - 支持多轮对话，维护 conversation_history
  - 【优化】每轮对话写入 WorkingMemory，下轮可参考
"""

from __future__ import annotations

import logging
import json
from typing import Any

from langchain_openai import ChatOpenAI
from pydantic import SecretStr
from langchain_core.messages import HumanMessage, SystemMessage

from app.memory.state import DetectionState
from app.memory.memory_manager import memory_manager
from app.memory.models import WorkingMemory
from app.config.settings import settings
from app.exceptions.base import ConfigurationError

logger = logging.getLogger(__name__)

ANSWER_PROMPT_TEMPLATE = """你是工业图像异常检测专家。请基于以下检测结果，简洁回答用户的问题。

## 检测结果
{result_json}

## 历史记忆参考（中期同设备 / 长期积累）【如有则参考，无则忽略】
{memory_context}

## 对话历史
{conversation_history}

## 用户当前问题
{question}

## 回答要求
1. 直接回答问题，不要生成完整报告格式
2. 如果问题与检测结果无关，礼貌说明
3. 回答控制在 200 字以内，简洁明了
4. 如有必要，可以询问用户是否需要生成完整报告

请直接输出回答内容："""


async def answer_node(state: DetectionState) -> DetectionState:
    """对话回答节点，支持多轮对话，记忆上下文注入。"""
    task = state.task
    question = task.question or "请分析这张图片"
    user_id = (task.parameters or {}).get("user_id", "default_user")
    asset_id = task.asset_id

    # ── 构建记忆上下文（三层记忆）【优化】──
    mem_ctx = memory_manager.build_memory_context(
        user_id=user_id,
        asset_id=asset_id,
        task_id=task.task_id,
    )
    memory_context_text = (
        f"【中期同设备】\n{mem_ctx['short_term']}\n\n"
        f"【长期积累】\n{mem_ctx['long_term']}"
    )

    # ── 构建检测结果 JSON ──
    result_json = ""
    if state.result:
        result_dict = {
            "status": state.result.status,
            "anomalies": state.result.anomalies or [],
            "summary": state.result.summary,
        }
        result_json = json.dumps(result_dict, ensure_ascii=False, indent=2)

    # ── 构建对话历史文本 ──
    history_text = ""
    if state.conversation_history:
        for msg in state.conversation_history:
            role = "用户" if msg.get("role") == "user" else "助手"
            history_text += f"{role}: {msg.get('content', '')}\n"

    prompt = ANSWER_PROMPT_TEMPLATE.format(
        result_json=result_json or "暂无检测结果",
        memory_context=memory_context_text,
        conversation_history=history_text or "（首次对话）",
        question=question,
    )

    # ── 调用 LLM ──
    try:
        if not settings.openai_api_key:
            raise ConfigurationError(
                "openai_api_key 未配置",
                config_key="APP_OPENAI_API_KEY",
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
        messages = [
            SystemMessage(content="你是工业图像异常检测专家，擅长简洁回答用户问题。"),
            HumanMessage(content=prompt),
        ]
        response = await llm.ainvoke(messages)
        raw_content = getattr(response, "content", None)
        logger.info(f"[answer_node] raw_content type={type(raw_content)}, repr={repr(raw_content)[:200]}")
        answer = (raw_content or "").strip()
    except Exception as e:
        logger.error(f"[answer_node] LLM 调用失败: {e}")
        state.errors.append(f"answer_generation_failed: {str(e)}")
        state.context["answer"] = "抱歉，生成回答时出现错误，请重试。"
        state.context["has_report"] = False
        return state

    # ── 写入会话工作记忆（WorkingMemory）【优化新增】──
    step_id = state.current_step
    working_mem = WorkingMemory(
        task_id=task.task_id,
        step_id=step_id,
        user_id=user_id,
        agent_context={
            "question": question,
            "answer": answer,
            "anomaly_count": len(state.result.anomalies or []) if state.result else 0,
            "asset_id": asset_id,
        },
    )
    memory_manager.add_working_memory(working_mem)

    # ── 记录对话历史 & 更新状态 ──
    state.conversation_history.append({"role": "assistant", "content": answer})
    state.context["answer"] = answer
    state.context["has_report"] = False
    state.current_step = step_id + 1
    state.logs.append(
        f"[对话回答] 第 {step_id} 轮，WorkingMemory 已写入，回答长度={len(answer)}字"
    )

    return state
