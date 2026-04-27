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
from app.orchestration.context_store import get_prompt_context
from app.schemas.detection import DetectionResult

logger = logging.getLogger(__name__)

ANSWER_PROMPT_TEMPLATE = """You are an industrial anomaly diagnosis expert.
Use the current detection result, retrieved knowledge, and memory context to answer the user directly.

Current detection result:
{result_json}

Memory and knowledge context:
{memory_context}

User task context:
Asset ID: {asset_id}
Conversation history: {conversation_history}
Current question: {question}

Requirements:
- Respond in Chinese.
- Include status judgment, key evidence, and next-step suggestion.
- Do not mention JSON, field names, APIs, or model internals.
- If the information is already sufficient, you may suggest generating a full report.
"""


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


async def answer_node(state: DetectionState) -> DetectionState:
    task_runtime = state.task_runtime()
    task = task_runtime.task
    question = task.question or "Please analyze the anomaly in this image."
    user_id = (task.parameters or {}).get("user_id", "default_user")
    asset_id = task.asset_id
    result = _ensure_result_from_shared_context(state)

    mem_ctx = memory_manager.build_memory_context(
        user_id=user_id,
        asset_id=asset_id,
        task_id=task.task_id,
    )
    knowledge_context = get_prompt_context(state) or "(no extra retrieved knowledge)"
    memory_context_text = (
        f"[Short-term same asset]\n{mem_ctx['short_term']}\n\n"
        f"[Long-term history]\n{mem_ctx['long_term']}\n\n"
        f"[Knowledge retrieval]\n{knowledge_context}"
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
    if task_runtime.conversation_history:
        for msg in task_runtime.conversation_history:
            role = "user" if msg.get("role") == "user" else "assistant"
            history_text += f"{role}: {msg.get('content', '')}\n"

    prompt = ANSWER_PROMPT_TEMPLATE.format(
        result_json=result_json,
        memory_context=memory_context_text,
        conversation_history=history_text or "(first turn)",
        question=question,
        asset_id=asset_id or "unknown asset",
    )

    try:
        if not settings.openai_api_key:
            raise ConfigurationError(
                "openai_api_key is not configured",
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
                SystemMessage(content="You are an industrial anomaly diagnosis expert."),
                HumanMessage(content=prompt),
            ],
            config={"tags": ["final_answer"], "metadata": {"langgraph_node": "answer"}},
        )
        answer = (getattr(response, "content", None) or "").strip()
    except Exception as exc:
        logger.error("[Answer] LLM call failed: %s", exc)
        state.errors.append(f"answer_generation_failed: {exc}")
        state.context["answer"] = "Sorry, an error occurred while generating the answer. Please try again later."
        state.context["has_report"] = False
        return state

    step_id = task_runtime.current_step
    memory_manager.add_working_memory(
        WorkingMemory(
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
    )

    task_runtime.conversation_history.append({"role": "assistant", "content": answer})
    task_runtime.current_step = step_id + 1
    state.apply_task_runtime(task_runtime)
    state.context["answer"] = answer
    state.context["has_report"] = False
    state.logs.append(
        f"[Answer] step={step_id}, anomalies={len(result.anomalies or [])}, answer_len={len(answer)}"
    )
    return state
