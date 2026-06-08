from __future__ import annotations

import json
import logging
import re
from typing import Any

from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from app.config.settings import settings
from app.exceptions.base import ConfigurationError
from app.memory.state import DetectionState

logger = logging.getLogger(__name__)


async def supplement_node(state: DetectionState) -> DetectionState:
    """Legacy supplement node kept for old graph compatibility."""
    state.loop_count += 1
    state.logs.append(
        f"[Supplement] Round {state.loop_count}, confidence={state.confidence:.2f}; "
        "starting deeper analysis."
    )

    if not state.result:
        state.errors.append("[Supplement] No detection result is available.")
        return state

    conversation_context = "\n".join(
        f"[{message['role']}] {message['content']}"
        for message in state.conversation_history
        if message.get("content")
    )
    anomaly_text = "\n".join(
        f"- type={item.get('type', 'unknown')}, score={item.get('score', 0):.2f}, "
        f"details={item.get('details', '')}"
        for item in (state.result.anomalies or [])
    )

    prompt = f"""You are an industrial visual anomaly detection expert.

Existing anomalies:
{anomaly_text or "(none)"}

Task:
- task_id: {state.task.task_id}
- asset_id: {state.task.asset_id}
- question: {state.task.question or "(none)"}

User-provided context:
{conversation_context or "(none)"}

Return strict JSON only:
{{
  "anomalies": [
    {{
      "type": "defect type",
      "score": 0.0,
      "details": "short evidence-based description",
      "possible_causes": ["cause"],
      "risk_level": "high|medium|low",
      "needs_verification": true
    }}
  ],
  "overall_confidence": 0.0
}}
"""

    if not settings.openai_api_key:
        raise ConfigurationError(
            "openai_api_key is not configured",
            config_key="APP_OPENAI_API_KEY",
        )

    llm = ChatOpenAI(
        model=settings.llm_model,
        temperature=0.1,
        api_key=SecretStr(settings.openai_api_key),
        timeout=settings.llm_timeout,
        max_tokens=600,
        base_url=settings.llm_base_url,
        extra_body={"enable_thinking": False},
    )

    try:
        response = await llm.ainvoke([{"role": "user", "content": prompt}])
        raw = getattr(response, "content", "") or ""
        parsed = _parse_json(raw)
    except Exception as exc:
        logger.warning("[Supplement] LLM call failed; keeping original result: %s", exc)
        parsed = None

    if parsed and isinstance(parsed.get("anomalies"), list):
        state.result.anomalies = parsed["anomalies"]
        state.confidence = float(parsed.get("overall_confidence", state.confidence))
        state.context["supplement_done"] = True
        state.context["supplement_round"] = state.loop_count
        state.logs.append(
            f"[Supplement] Round {state.loop_count} finished; confidence={state.confidence:.2f}."
        )
    else:
        state.context["supplement_done"] = False
        state.errors.append("[Supplement] Failed to parse supplement result; kept original result.")

    return state


def _parse_json(raw: str) -> Any:
    raw = raw.strip()
    try:
        return json.loads(raw)
    except Exception:
        pass

    match = re.search(r"\{[\s\S]*\}", raw)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except Exception:
        return None
