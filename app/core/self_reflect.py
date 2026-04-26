from __future__ import annotations

import logging
from typing import Any

from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from app.config.settings import settings
from app.exceptions.base import ConfigurationError
from app.memory.memory_manager import memory_manager
from app.memory.state import DetectionState
from app.schemas.detection import DetectionResult
from app.utils.json_parser import parse_json_safely

logger = logging.getLogger(__name__)

MAX_LOOP = 3
CONFIDENCE_THRESHOLD = 0.7


def _ensure_result_from_shared_context(state: DetectionState) -> DetectionResult:
    if state.result is None:
        state.result = DetectionResult(task_id=state.task.task_id, status="success")

    vision_payload = state.shared_context.get("vision") or {}
    if vision_payload.get("anomalies") and not state.result.anomalies:
        state.result.anomalies = list(vision_payload.get("anomalies", []))
    if vision_payload.get("metadata"):
        state.result.metadata.update(vision_payload["metadata"])

    return state.result


def _build_reflection_prompt(anomalies: list[Any], history_text: str) -> str:
    anomaly_str = "\n".join(
        f"- type={item.get('type', 'unknown')}, details={item.get('details', '')}"
        for item in anomalies
        if isinstance(item, dict)
    )
    return f"""你是工业异常检测质量审核员。

请评估以下异常检测结果是否足以继续输出结论。

## 本次异常
{anomaly_str or '（无异常）'}

## 历史参考
{history_text or '（无历史记录）'}

请返回严格 JSON：
{{
  "confidence": 0.0,
  "unknown_anomaly_types": [],
  "can_proceed": true,
  "reason": "一句话说明"
}}
"""


async def self_reflect_node(state: DetectionState) -> DetectionState:
    if state.loop_count >= MAX_LOOP:
        state.logs.append(f"[SelfReflect] loop_count reached {MAX_LOOP}, proceed directly")
        state.reflection_decision = "proceed"
        state.needs_user_input = False
        return state

    result = _ensure_result_from_shared_context(state)
    if not result:
        state.reflection_decision = "proceed"
        return state

    user_id = (state.task.parameters or {}).get("user_id", "default_user")
    long_term_memories = memory_manager.get_long_term_memory(user_id)
    history_text = "\n".join(f"- {item.memory_summary[:200]}" for item in long_term_memories[-3:])

    if not settings.openai_api_key:
        raise ConfigurationError(
            "openai_api_key 未配置",
            config_key="APP_OPENAI_API_KEY",
        )

    try:
        llm = ChatOpenAI(
            model=settings.llm_model,
            temperature=0.0,
            api_key=SecretStr(settings.openai_api_key),
            timeout=settings.llm_timeout,
            max_tokens=300,
            base_url=settings.llm_base_url,
            extra_body={"enable_thinking": False},
        )
        response = await llm.ainvoke(
            [{"role": "user", "content": _build_reflection_prompt(result.anomalies or [], history_text)}],
            config={"tags": ["internal_reflect"], "metadata": {"langgraph_node": "self_reflect"}},
        )
        parsed = parse_json_safely(getattr(response, "content", "") or "")
    except Exception as exc:
        logger.warning("[SelfReflect] LLM reflect failed, fallback proceed: %s", exc)
        parsed = None

    if parsed:
        state.confidence = float(parsed.get("confidence", 0.5))
        state.unknown_anomaly_types = parsed.get("unknown_anomaly_types") or []
        can_proceed = bool(parsed.get("can_proceed", False))
    else:
        state.confidence = float(result.metadata.get("confidence", CONFIDENCE_THRESHOLD) or CONFIDENCE_THRESHOLD)
        state.unknown_anomaly_types = []
        can_proceed = True

    if not can_proceed:
        if state.unknown_anomaly_types:
            state.reflection_decision = "need_user"
            state.needs_user_input = True
            state.logs.append(
                f"[SelfReflect] confidence={state.confidence:.2f}, need user clarification"
            )
        else:
            state.reflection_decision = "retry"
            state.needs_user_input = False
            state.logs.append(
                f"[SelfReflect] confidence={state.confidence:.2f} below threshold, retry"
            )
    else:
        state.reflection_decision = "proceed"
        state.needs_user_input = False
        state.logs.append(f"[SelfReflect] confidence={state.confidence:.2f}, proceed")

    return state
