from __future__ import annotations

import json
import logging

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from app.config.settings import settings
from app.exceptions.base import ConfigurationError
from app.memory.conversation import compact_state_conversation
from app.memory.memory_manager import memory_manager
from app.memory.models import ShortTermMemory, WorkingMemory
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
Conversation summary: {conversation_summary}
Current question: {question}

Requirements:
- Respond in Chinese.
- Include status judgment, key evidence, and next-step suggestion.
- When anomalies include location, appearance, severity, or description, use them as primary evidence.
- Do not mention JSON, field names, APIs, or model internals.
- If the information is already sufficient, you may suggest generating a full report.
"""


def _ensure_result_from_shared_context(state: DetectionState) -> DetectionResult:
    domain_runtime = state.domain_runtime()
    if domain_runtime.result is None:
        default_status = "success" if domain_runtime.agent_outputs else ("failed" if state.last_failed_step else "success")
        domain_runtime.result = DetectionResult(task_id=state.task.task_id, status=default_status)

    vision_ctx = domain_runtime.shared_context.vision
    if vision_ctx and vision_ctx.anomalies and not domain_runtime.result.anomalies:
        domain_runtime.result.anomalies = list(vision_ctx.anomalies)
    if vision_ctx and vision_ctx.metadata:
        domain_runtime.result.metadata.update(vision_ctx.metadata)
    if vision_ctx and vision_ctx.answer and not domain_runtime.result.answer:
        domain_runtime.result.answer = vision_ctx.answer

    state.apply_domain_runtime(domain_runtime)
    return state.result


def _build_structured_analysis_metadata(state: DetectionState) -> dict[str, object]:
    knowledge_ctx = state.domain_runtime().shared_context.knowledge
    if not knowledge_ctx:
        return {}

    defect_block = knowledge_ctx.defect_analysis or {}
    object_block = knowledge_ctx.object_analysis or {}

    defect_analysis = {
        "similar_cases": list(defect_block.get("similar_cases") or knowledge_ctx.similar_cases),
        "possible_causes": list(defect_block.get("possible_causes") or knowledge_ctx.possible_causes),
        "risk_notes": list(defect_block.get("risk_notes") or knowledge_ctx.risk_notes),
        "repair_actions": list(defect_block.get("repair_actions") or knowledge_ctx.repair_actions),
        "analysis_summary": defect_block.get("analysis_summary") or knowledge_ctx.analysis_summary,
    }
    object_analysis = {
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
    }
    return {
        "defect_analysis": defect_analysis,
        "object_analysis": object_analysis,
    }


async def answer_node(state: DetectionState) -> DetectionState:
    task_runtime = state.task_runtime()
    task = task_runtime.task
    question = task.question or "Please analyze the anomaly in this image."
    user_id = (task.parameters or {}).get("user_id", "default_user")
    asset_id = task.asset_id
    result = _ensure_result_from_shared_context(state)

    if result.status == "failed" and not (result.anomalies or []):
        failed_step = state.orchestration_runtime().last_failed_step or "vision"
        answer = f"本次检测未能得到可靠结果，{failed_step} 执行失败，当前不能据此判断设备正常。请重试检测，或检查 PatchCore 类别、模型产物和输入图片后再试。"
        task_runtime.conversation_history.append({"role": "assistant", "content": answer})
        task_runtime.current_step += 1
        state.apply_task_runtime(task_runtime)
        compact_state_conversation(state)
        state.context["answer"] = answer
        state.context["has_report"] = False
        result.summary = result.summary or "检测流程失败，未得到可靠的视觉结论。"
        state.logs.append(f"[Answer] generated deterministic failure answer for step={failed_step}")
        return state

    mem_ctx = memory_manager.build_memory_context(
        user_id=user_id,
        asset_id=asset_id,
        task_id=task.task_id,
    )
    knowledge_context = get_prompt_context(state) or "(no extra retrieved knowledge)"
    knowledge_ctx = state.domain_runtime().shared_context.knowledge
    structured_analysis = "(no structured defect analysis)"
    defect_block = knowledge_ctx.defect_analysis if knowledge_ctx and knowledge_ctx.defect_analysis else {}
    object_block = knowledge_ctx.object_analysis if knowledge_ctx and knowledge_ctx.object_analysis else {}
    if knowledge_ctx and (
        knowledge_ctx.possible_causes
        or knowledge_ctx.risk_notes
        or knowledge_ctx.repair_actions
        or knowledge_ctx.analysis_summary
        or knowledge_ctx.component_scope
        or knowledge_ctx.component_findings
        or knowledge_ctx.functional_impact
        or knowledge_ctx.object_summary
        or knowledge_ctx.object_knowledge_notes
        or knowledge_ctx.object_knowledge_hits
        or knowledge_ctx.object_knowledge_summary
        or defect_block
        or object_block
    ):
        analysis_lines = []
        defect_summary = defect_block.get("analysis_summary") or knowledge_ctx.analysis_summary
        object_summary = object_block.get("object_summary") or knowledge_ctx.object_summary
        object_knowledge_summary = object_block.get("object_knowledge_summary") or knowledge_ctx.object_knowledge_summary
        object_knowledge_hits = object_block.get("object_knowledge_hits") or knowledge_ctx.object_knowledge_hits
        component_scope = object_block.get("component_scope") or knowledge_ctx.component_scope
        component_findings = object_block.get("component_findings") or knowledge_ctx.component_findings
        functional_impact = object_block.get("functional_impact") or knowledge_ctx.functional_impact
        object_knowledge_notes = object_block.get("object_knowledge_notes") or knowledge_ctx.object_knowledge_notes
        possible_causes = defect_block.get("possible_causes") or knowledge_ctx.possible_causes
        risk_notes = defect_block.get("risk_notes") or knowledge_ctx.risk_notes
        repair_actions = defect_block.get("repair_actions") or knowledge_ctx.repair_actions

        if defect_summary:
            analysis_lines.append(f"[Analysis summary]\n{defect_summary}")
        if object_summary:
            analysis_lines.append(f"[Object summary]\n{object_summary}")
        if object_knowledge_summary:
            analysis_lines.append(f"[Object knowledge summary]\n{object_knowledge_summary}")
        if object_knowledge_hits:
            analysis_lines.append(
                "[Object knowledge hits]\n"
                + "\n".join(
                    f"- {item.get('title')}: {item.get('note')}"
                    for item in object_knowledge_hits
                )
            )
        if component_scope:
            analysis_lines.append("[Component scope]\n" + "\n".join(f"- {item}" for item in component_scope))
        if component_findings:
            analysis_lines.append(
                "[Component findings]\n"
                + "\n".join(
                    f"- {item.get('location')} 对应 {item.get('component')}，异常类型 {item.get('anomaly_type')}"
                    for item in component_findings
                )
            )
        if functional_impact:
            analysis_lines.append("[Functional impact]\n" + "\n".join(f"- {item}" for item in functional_impact))
        if object_knowledge_notes:
            analysis_lines.append("[Object knowledge]\n" + "\n".join(f"- {item}" for item in object_knowledge_notes))
        if possible_causes:
            analysis_lines.append("[Possible causes]\n" + "\n".join(f"- {item}" for item in possible_causes))
        if risk_notes:
            analysis_lines.append("[Risk notes]\n" + "\n".join(f"- {item}" for item in risk_notes))
        if repair_actions:
            analysis_lines.append("[Repair actions]\n" + "\n".join(f"- {item}" for item in repair_actions))
        structured_analysis = "\n\n".join(analysis_lines)
    memory_context_text = (
        f"[Short-term same asset]\n{mem_ctx['short_term']}\n\n"
        f"[Long-term history]\n{mem_ctx['long_term']}\n\n"
        f"[Tool effectiveness]\n{mem_ctx['tool_effect']}\n\n"
        f"[Knowledge retrieval]\n{knowledge_context}\n\n"
        f"[Structured defect analysis]\n{structured_analysis}"
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
        conversation_summary=task_runtime.conversation_summary or "(no earlier summary)",
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
    structured_metadata = _build_structured_analysis_metadata(state)
    if structured_metadata:
        result.metadata.update(structured_metadata)

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

    if step_id == 1 and asset_id and result.status == "success":
        anomaly_types = [
            item.get("type", "unknown")
            for item in (result.anomalies or [])
            if isinstance(item, dict)
        ]
        summary = (
            f"检出 {len(result.anomalies or [])} 个异常：{', '.join(anomaly_types)}"
            if anomaly_types
            else "未检出明显异常"
        )
        memory_manager.add_short_term_memory(
            ShortTermMemory(
                asset_id=asset_id,
                user_id=user_id,
                memory_summary=summary,
                memory_details={
                    "task_id": task.task_id,
                    "question": question,
                    "anomalies": result.anomalies or [],
                    "answer": answer,
                },
                tags=anomaly_types,
                anomaly_count=len(result.anomalies or []),
            )
        )

    task_runtime.conversation_history.append({"role": "assistant", "content": answer})
    task_runtime.current_step = step_id + 1
    state.apply_task_runtime(task_runtime)
    compact_state_conversation(state)
    state.context["answer"] = answer
    state.context["has_report"] = False
    state.logs.append(
        f"[Answer] step={step_id}, anomalies={len(result.anomalies or [])}, answer_len={len(answer)}"
    )
    return state
