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
    domain_runtime = state.domain_runtime()
    if domain_runtime.result is None:
        default_status = "success" if domain_runtime.agent_outputs else ("failed" if state.last_failed_step else "success")
        domain_runtime.result = DetectionResult(task_id=state.task.task_id, status=default_status)

    vision_ctx = domain_runtime.shared_context.vision
    if vision_ctx and vision_ctx.anomalies and not domain_runtime.result.anomalies:
        domain_runtime.result.anomalies = list(vision_ctx.anomalies)
    if vision_ctx and vision_ctx.metadata:
        domain_runtime.result.metadata.update(vision_ctx.metadata)

    state.apply_domain_runtime(domain_runtime)
    return state.result


def _build_reflection_prompt(anomalies: list[Any], history_text: str) -> str:
    anomaly_str = "\n".join(
        f"- type={item.get('type', 'unknown')}, details={item.get('details', '')}"
        for item in anomalies
        if isinstance(item, dict)
    )
    return f"""You are auditing the quality of an industrial anomaly diagnosis.
Assess whether the current anomaly result is strong enough to continue.

Current anomalies:
{anomaly_str or '(none)'}

History:
{history_text or '(none)'}

Return strict JSON only:
{{
  "confidence": 0.0,
  "unknown_anomaly_types": [],
  "can_proceed": true,
  "reason": "short reason",
  "retry_target": "vision|knowledge|null",
  "retry_strategy": "short label"
}}
"""


async def self_reflect_node(state: DetectionState) -> DetectionState:
    orchestration = state.orchestration_runtime()
    task_runtime = state.task_runtime()

    if orchestration.loop_count >= MAX_LOOP:
        state.logs.append(f"[SelfReflect] loop_count reached {MAX_LOOP}, proceed directly")
        orchestration.reflection_decision = "proceed"
        orchestration.needs_user_input = False
        orchestration.retry_target = None
        orchestration.retry_reason = None
        orchestration.retry_strategy = None
        state.apply_orchestration_runtime(orchestration)
        return state

    result = _ensure_result_from_shared_context(state)
    if orchestration.last_failed_step:
        failed_output = orchestration.step_outputs.get(orchestration.last_failed_step, {}) or {}
        failed_agent = failed_output.get("agent_name") or orchestration.last_failed_step.split("-", 1)[0]
        orchestration.confidence = 0.0
        orchestration.unknown_anomaly_types = []
        orchestration.reflection_decision = "retry"
        orchestration.needs_user_input = False
        orchestration.retry_target = failed_agent if failed_agent in {"vision", "knowledge"} else "vision"
        orchestration.retry_reason = failed_output.get("summary") or "specialist step failed and needs another run"
        orchestration.retry_strategy = "rerun_after_failure"
        state.logs.append(
            f"[SelfReflect] detected failed step {orchestration.last_failed_step}, retry {orchestration.retry_target}"
        )
        state.apply_orchestration_runtime(orchestration)
        return state

    user_id = (task_runtime.task.parameters or {}).get("user_id", "default_user")
    long_term_memories = memory_manager.get_long_term_memory(user_id, asset_id=task_runtime.task.asset_id)
    history_text = "\n".join(f"- {item.memory_summary[:200]}" for item in long_term_memories[-3:])

    if not settings.openai_api_key:
        raise ConfigurationError(
            "openai_api_key is not configured",
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
        orchestration.confidence = float(parsed.get("confidence", 0.5))
        orchestration.unknown_anomaly_types = parsed.get("unknown_anomaly_types") or []
        can_proceed = bool(parsed.get("can_proceed", False))
        retry_target = parsed.get("retry_target")
        retry_strategy = parsed.get("retry_strategy")
        retry_reason = parsed.get("reason")
    else:
        orchestration.confidence = float(result.metadata.get("confidence", 0.0) or 0.0)
        orchestration.unknown_anomaly_types = []
        can_proceed = result.status != "failed"
        retry_target = None
        retry_strategy = None
        retry_reason = "result remains unreliable after fallback reflection" if not can_proceed else None

    if not can_proceed:
        if orchestration.unknown_anomaly_types:
            orchestration.reflection_decision = "need_user"
            orchestration.needs_user_input = True
            orchestration.retry_target = None
            orchestration.retry_reason = None
            orchestration.retry_strategy = None
            state.logs.append(
                f"[SelfReflect] confidence={orchestration.confidence:.2f}, need user clarification"
            )
        else:
            has_image = bool((task_runtime.task.parameters or {}).get("image_base64"))
            orchestration.reflection_decision = "retry"
            orchestration.needs_user_input = False
            if retry_target not in {"vision", "knowledge"}:
                retry_target = "vision" if has_image else "knowledge"
            orchestration.retry_target = retry_target
            orchestration.retry_reason = retry_reason or "self_reflect requested another specialist pass"
            orchestration.retry_strategy = retry_strategy or "rerun_with_focus"
            state.logs.append(
                f"[SelfReflect] confidence={orchestration.confidence:.2f} below threshold, retry {orchestration.retry_target}"
            )
    else:
        orchestration.reflection_decision = "proceed"
        orchestration.needs_user_input = False
        orchestration.retry_target = None
        orchestration.retry_reason = None
        orchestration.retry_strategy = None
        state.logs.append(f"[SelfReflect] confidence={orchestration.confidence:.2f}, proceed")

    state.apply_orchestration_runtime(orchestration)
    return state
