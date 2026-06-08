from __future__ import annotations

import logging

from app.memory.state import DetectionState
from app.schemas.detection import DetectionResult

logger = logging.getLogger(__name__)


async def consolidate_node(state: DetectionState) -> DetectionState:
    """Legacy result consolidation node kept for old graph compatibility."""
    if not state.result:
        state.result = DetectionResult(
            task_id=state.task.task_id,
            status="success",
            anomalies=[],
            metadata={"logs": "Initial result created by consolidate_node"},
        )

    if not state.tool_outputs:
        state.logs.append("[Consolidate] No tool outputs to merge.")
        return state

    all_anomalies: list[dict] = []
    seen_anomalies: set[str] = set()

    for output in state.tool_outputs:
        tool_name = output.get("tool", "unknown")
        anomalies = output.get("anomalies", [])

        for anomaly in anomalies:
            anomaly["source"] = tool_name
            anomaly_id = f"{anomaly.get('type')}_{anomaly.get('details')}"
            if anomaly_id not in seen_anomalies:
                all_anomalies.append(anomaly)
                seen_anomalies.add(anomaly_id)

    state.result = DetectionResult(
        task_id=state.task.task_id,
        status="success",
        anomalies=all_anomalies,
        metadata={
            "consolidated_from": [out.get("tool") for out in state.tool_outputs],
            "loop_count": state.loop_count,
            "planner_thought": state.context.get("planner_thought"),
        },
    )
    state.logs.append(f"[Consolidate] Merged {len(all_anomalies)} anomaly item(s).")
    return state
