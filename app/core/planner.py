"""
Planner node for ReAct-style tool orchestration.

LEGACY: this module is retained for reference only and is not used by the
current supervisor-based graph in app/core/graph.py.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from app.config.settings import settings
from app.core.tools import get_industrial_tools
from app.memory.state import DetectionState

logger = logging.getLogger(__name__)

MAX_HISTORY_MESSAGES = 6
MAX_QUESTION_CHARS = 2000
MAX_TOOL_OBSERVATION_CHARS = 6000
MAX_DIRECT_THOUGHT_CHARS = 4000

PLANNER_SYSTEM_PROMPT = """
You are a planner for industrial anomaly diagnosis tasks.

Your job:
1. Understand the user's current question and the available context.
2. Decide whether tool calls are needed.
3. If tools are needed, choose the most suitable tool and arguments.
4. If the information is already sufficient, do not invent tool calls.

Available tools:
- timeseries_anomaly_detection: analyze time-series or sensor anomalies.
- visual_anomaly_detection: detect whether an image contains industrial anomalies.
- visual_anomaly_localization: locate where the anomaly appears in the image and return bounding boxes or coarse regions.
- knowledge_retrieval: retrieve similar cases, manuals, and handling suggestions.

Planning rules:
- If the task has an image and the user asks whether there is a defect, abnormal appearance, leakage, damage, or another visual issue, prefer visual_anomaly_detection.
- If the user explicitly asks where the anomaly is, which region is affected, asks for a bbox, highlighted area, location, position, or mask, prefer visual_anomaly_localization.
- If the user asks about causes, mechanisms, risks, maintenance, or similar historical cases, prefer knowledge_retrieval.
- If previous tool output is insufficient, you may call additional tools.

Current task context:
- Asset ID: {asset_id}
- Time Range: {start_time} to {end_time}
- Has Image: {has_image}
"""


def _truncate_text(text: Any, limit: int) -> str:
    """Return a bounded string representation."""
    if text is None:
        return ""
    value = str(text)
    if len(value) <= limit:
        return value
    return value[:limit] + f"\n...[truncated {len(value) - limit} chars]"


def _compact_observation(observation: Any) -> str:
    """Reduce tool observations to a planner-friendly summary."""
    if observation is None:
        return ""

    text = str(observation)
    try:
        parsed = json.loads(text)
    except Exception:
        return _truncate_text(text, MAX_TOOL_OBSERVATION_CHARS)

    if not isinstance(parsed, dict):
        return _truncate_text(text, MAX_TOOL_OBSERVATION_CHARS)

    compact: dict[str, Any] = {}
    if "status" in parsed:
        compact["status"] = parsed.get("status")
    if "answer" in parsed:
        compact["answer"] = _truncate_text(parsed.get("answer"), 1200)
    if "summary" in parsed:
        compact["summary"] = _truncate_text(parsed.get("summary"), 1200)
    if "anomalies" in parsed:
        anomalies = parsed.get("anomalies") or []
        compact["anomaly_count"] = len(anomalies)
        compact["anomalies"] = anomalies[:5]
    if "metadata" in parsed and isinstance(parsed["metadata"], dict):
        metadata = dict(parsed["metadata"])
        metadata.pop("image_base64", None)
        compact["metadata"] = metadata

    if not compact:
        compact = parsed

    compact_text = json.dumps(compact, ensure_ascii=False, indent=2)
    return _truncate_text(compact_text, MAX_TOOL_OBSERVATION_CHARS)


async def planner_node(state: DetectionState) -> DetectionState:
    """Analyze the current turn and decide whether tools should be called."""
    if state.loop_count >= 3:
        state.logs.append("[Planner] Reached max planning depth, proceed to answer")
        state.reflection_decision = "proceed"
        return state

    state.logs.append(f"[Planner] Start planning round {len(state.intermediate_steps) + 1}")

    llm = ChatOpenAI(
        model=settings.llm_model,
        temperature=0,
        api_key=SecretStr(settings.openai_api_key),
        base_url=settings.llm_base_url,
        timeout=settings.llm_timeout,
    )
    llm_with_tools = llm.bind_tools(get_industrial_tools())

    has_image = bool((state.task.parameters or {}).get("image_base64"))
    system_msg = PLANNER_SYSTEM_PROMPT.format(
        asset_id=state.task.asset_id,
        start_time=state.task.start_time,
        end_time=state.task.end_time,
        has_image="yes" if has_image else "no",
    )

    messages: list[Any] = [SystemMessage(content=system_msg)]

    recent_history = state.conversation_history[-MAX_HISTORY_MESSAGES:]
    for msg in recent_history[:-1]:
        role = msg.get("role")
        content = _truncate_text(msg.get("content", ""), 1200)
        if not content:
            continue
        if role == "assistant":
            messages.append(AIMessage(content=content))
        else:
            messages.append(HumanMessage(content=content))

    current_question = _truncate_text(state.task.question or "", MAX_QUESTION_CHARS)
    messages.append(HumanMessage(content=f"Current user question:\n{current_question}"))

    for action, observation in state.intermediate_steps[-3:]:
        messages.append(
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": action["id"],
                        "name": action["name"],
                        "args": action.get("args", {}),
                    }
                ],
            )
        )
        messages.append(
            ToolMessage(
                content=_compact_observation(observation),
                tool_call_id=action["id"],
            )
        )

    try:
        response = await llm_with_tools.ainvoke(
            messages,
            config={
                "tags": ["planner_thought"],
                "metadata": {"langgraph_node": "planner"},
            },
        )

        if response.tool_calls:
            state.tool_calls = response.tool_calls
            state.reflection_decision = "retry"
            state.logs.append(
                f"[Planner] Selected tools: {[tool_call['name'] for tool_call in response.tool_calls]}"
            )
        else:
            state.reflection_decision = "proceed"
            state.context["planner_thought"] = _truncate_text(response.content, MAX_DIRECT_THOUGHT_CHARS)
            state.logs.append("[Planner] Information is sufficient, proceed to answer")
    except Exception as exc:
        logger.error("[Planner] Planning failed: %s", exc)
        state.errors.append(f"Planner error: {str(exc)}")
        state.reflection_decision = "proceed"

    return state
