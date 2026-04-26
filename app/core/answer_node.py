from __future__ import annotations

import json
import logging

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from app.config.settings import settings
from app.exceptions.base import ConfigurationError
from app.memory.memory_manager import memory_manager
from app.memory.models import WorkingMemory
from app.memory.state import DetectionState
from app.schemas.detection import DetectionResult

logger = logging.getLogger(__name__)

ANSWER_PROMPT_TEMPLATE = """你是一名工业异常诊断专家。

请基于当前检测结果、检索知识和历史记忆，直接给出结构化专业结论。

## 当前检测结果
{result_json}

## 知识与记忆上下文
{memory_context}

## 用户问题
资产ID: {asset_id}
对话历史: {conversation_history}
当前问题: {question}

回答要求：
- 使用中文
- 输出包括【状态判定】【核心依据】【后续建议】
- 不要提及 JSON、字段、API、模型分数等系统实现细节
- 如果信息充分，可提示用户点击“生成报告”获取完整技术报告
"""


def _ensure_result_from_shared_context(state: DetectionState) -> DetectionResult:
    if state.result is None:
        state.result = DetectionResult(task_id=state.task.task_id, status="success")

    vision_payload = state.shared_context.get("vision") or {}
    if vision_payload.get("anomalies") and not state.result.anomalies:
        state.result.anomalies = list(vision_payload.get("anomalies", []))
    if vision_payload.get("metadata"):
        state.result.metadata.update(vision_payload["metadata"])
    if vision_payload.get("answer") and not state.result.answer:
        state.result.answer = vision_payload["answer"]

    return state.result


async def answer_node(state: DetectionState) -> DetectionState:
    task = state.task
    question = task.question or "请分析这张图像中的异常情况"
    user_id = (task.parameters or {}).get("user_id", "default_user")
    asset_id = task.asset_id
    result = _ensure_result_from_shared_context(state)

    mem_ctx = memory_manager.build_memory_context(
        user_id=user_id,
        asset_id=asset_id,
        task_id=task.task_id,
    )
    knowledge_payload = state.shared_context.get("knowledge") or {}
    knowledge_context = knowledge_payload.get("prompt_context") or "（无额外知识检索结果）"
    memory_context_text = (
        f"【中期同设备】\n{mem_ctx['short_term']}\n\n"
        f"【长期积累】\n{mem_ctx['long_term']}\n\n"
        f"【知识检索】\n{knowledge_context}"
    )

    result_json = json.dumps(
        {
            "status": result.status,
            "anomalies": result.anomalies or [],
            "summary": result.summary,
            "metadata": result.metadata,
        },
        ensure_ascii=False,
        indent=2,
    )

    history_text = ""
    if state.conversation_history:
        for msg in state.conversation_history:
            role = "用户" if msg.get("role") == "user" else "助手"
            history_text += f"{role}: {msg.get('content', '')}\n"

    prompt = ANSWER_PROMPT_TEMPLATE.format(
        result_json=result_json,
        memory_context=memory_context_text,
        conversation_history=history_text or "（首次对话）",
        question=question,
        asset_id=asset_id or "未知资产",
    )

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
        response = await llm.ainvoke(
            [
                SystemMessage(content="你是一名工业异常诊断专家。"),
                HumanMessage(content=prompt),
            ],
            config={"tags": ["final_answer"], "metadata": {"langgraph_node": "answer"}},
        )
        answer = (getattr(response, "content", None) or "").strip()
    except Exception as exc:
        logger.error("[answer_node] LLM call failed: %s", exc)
        state.errors.append(f"answer_generation_failed: {exc}")
        state.context["answer"] = "抱歉，生成回答时出现错误，请稍后重试。"
        state.context["has_report"] = False
        return state

    step_id = state.current_step
    working_mem = WorkingMemory(
        task_id=task.task_id,
        step_id=step_id,
        user_id=user_id,
        agent_context={
            "question": question,
            "answer": answer,
            "anomaly_count": len(result.anomalies or []),
            "asset_id": asset_id,
        },
    )
    memory_manager.add_working_memory(working_mem)

    state.conversation_history.append({"role": "assistant", "content": answer})
    state.context["answer"] = answer
    state.context["has_report"] = False
    state.current_step = step_id + 1
    state.logs.append(
        f"[Answer] step={step_id}, anomalies={len(result.anomalies or [])}, answer_len={len(answer)}"
    )
    return state
