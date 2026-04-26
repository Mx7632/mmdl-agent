"""
Executor node for running planner-selected tools.
"""

from __future__ import annotations

import json
import logging

from app.core.tools import get_industrial_tools
from app.memory.state import DetectionState

logger = logging.getLogger(__name__)

_VISUAL_TOOL_NAMES = {"visual_anomaly_detection", "visual_anomaly_localization"}


async def executor_node(state: DetectionState) -> DetectionState:
    """Execute planner tool calls and append structured observations into state."""
    if not state.tool_calls:
        state.logs.append("[Executor] No pending tools")
        return state

    state.logs.append(f"[Executor] Executing {len(state.tool_calls)} tool call(s)")
    tools = {tool.name: tool for tool in get_industrial_tools()}

    for tool_call in state.tool_calls:
        tool_name = tool_call["name"]
        tool_args = dict(tool_call["args"])

        if "task_id" not in tool_args:
            tool_args["task_id"] = state.task.task_id
        if "asset_id" not in tool_args:
            tool_args["asset_id"] = state.task.asset_id

        if tool_name in _VISUAL_TOOL_NAMES and not tool_args.get("image_base64"):
            image_data = state.task.parameters.get("image_base64")
            if image_data:
                tool_args["image_base64"] = image_data
                state.logs.append(f"[Executor] Injected image payload for {tool_name}")

        if tool_name not in tools:
            observation = f"Error: Tool {tool_name} not found."
        else:
            try:
                state.logs.append(f"[Executor] Running tool: {tool_name}")
                observation = await tools[tool_name].arun(tool_args)
            except Exception as exc:
                logger.error("[Executor] Tool %s failed: %s", tool_name, exc)
                observation = f"Error: {str(exc)}"

        state.intermediate_steps.append((tool_call, observation))

        try:
            parsed = json.loads(observation)
        except Exception:
            continue

        if isinstance(parsed, dict) and "anomalies" in parsed:
            state.tool_outputs.append(
                {
                    "tool": tool_name,
                    "anomalies": parsed["anomalies"],
                }
            )

    state.tool_calls = []
    state.loop_count += 1
    return state
