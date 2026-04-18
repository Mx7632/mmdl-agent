"""
对话回答节点（Answer Node）
职责：
  - 基于检测结果回答用户问题
  - 只返回简洁回答，不生成完整报告
  - 支持多轮对话，维护 conversation_history
"""

from __future__ import annotations

import logging
from typing import Any

from app.memory.state import DetectionState
from app.config.settings import settings
from app.exceptions.base import ConfigurationError

logger = logging.getLogger(__name__)


# 对话回答提示词模板
ANSWER_PROMPT_TEMPLATE = """你是工业图像异常检测专家。请基于以下检测结果，简洁回答用户的问题。

## 检测结果
{result_json}

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
    """
    对话回答节点。
    基于检测结果回答用户问题，不生成完整报告。
    """
    from langchain_openai import ChatOpenAI
    from pydantic import SecretStr
    from langchain_core.messages import HumanMessage, SystemMessage
    from app.config.settings import settings
    from app.exceptions.base import ConfigurationError
    import json

    task = state.task
    question = task.question or "请分析这张图片"

    # 构建提示词
    result_json = ""
    if state.result:
        # anomalies 已经是字典列表
        anomalies_list = state.result.anomalies or []
        result_dict = {
            "status": state.result.status,
            "anomalies": anomalies_list,
            "summary": state.result.summary,
        }
        result_json = json.dumps(result_dict, ensure_ascii=False, indent=2)

    # 构建对话历史文本
    history_text = ""
    if state.conversation_history:
        for msg in state.conversation_history:
            role = "用户" if msg.get("role") == "user" else "助手"
            history_text += f"{role}: {msg.get('content', '')}\n"

    prompt = ANSWER_PROMPT_TEMPLATE.format(
        result_json=result_json or "暂无检测结果",
        conversation_history=history_text or "（首次对话）",
        question=question,
    )

    # 调用 LLM 生成回答
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
        answer = response.content.strip()

        # 记录到对话历史
        state.conversation_history.append({
            "role": "assistant",
            "content": answer,
        })

        # 将回答存入 context 供 API 返回
        state.context["answer"] = answer
        state.context["has_report"] = False

        state.logs.append(f"[对话回答] 已生成回答，长度={len(answer)}字")

    except Exception as e:
        logger.error(f"[answer_node] LLM 调用失败: {e}")
        state.errors.append(f"answer_generation_failed: {str(e)}")
        state.context["answer"] = "抱歉，生成回答时出现错误，请重试。"
        state.context["has_report"] = False

    return state
