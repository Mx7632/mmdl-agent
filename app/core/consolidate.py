# LEGACY: retained for reference only; not used by the current supervisor-based graph.
"""
结果整合节点 (Consolidate Node)
职责�?  1. �?Executor 执行的多个工具输出进行逻辑整合
  2. 填充到标准的 state.result 中，供下游节点（自检、回答、报告）使用
"""
from __future__ import annotations

import logging
from typing import List, Dict, Any

from app.memory.state import DetectionState
from app.schemas.detection import DetectionResult

logger = logging.getLogger(__name__)

async def consolidate_node(state: DetectionState) -> DetectionState:
    """整合节点：汇总所有工具输出到 state.result�?""
    # 始终初始�?result，防止下�?generate_report 报错
    if not state.result:
        state.result = DetectionResult(
            task_id=state.task.task_id,
            status="success",
            anomalies=[],
            metadata={"logs": "Initial result created by consolidate_node"}
        )

    if not state.tool_outputs:
        state.logs.append("[Consolidate] 无工具输出可整合")
        return state

    all_anomalies = []
    seen_anomalies = set() # 简单去重逻辑
    
    for output in state.tool_outputs:
        tool_name = output.get("tool", "unknown")
        anomalies = output.get("anomalies", [])
        
        for anomaly in anomalies:
            # 标记来源
            anomaly["source"] = tool_name
            
            # 简单的唯一标识符（基于类型和描述）用于去重
            anomaly_id = f"{anomaly.get('type')}_{anomaly.get('details')}"
            if anomaly_id not in seen_anomalies:
                all_anomalies.append(anomaly)
                seen_anomalies.add(anomaly_id)

    # 创建或更�?DetectionResult
    # 即使没有检出异常（all_anomalies 为空），也应该创�?result 对象，标记为 success
    state.result = DetectionResult(
        task_id=state.task.task_id,
        status="success", # 即使没有异常，检测过程本身也是成功的
        anomalies=all_anomalies,
        metadata={
            "consolidated_from": [out.get("tool") for out in state.tool_outputs],
            "loop_count": state.loop_count,
            "planner_thought": state.context.get("planner_thought")
        }
    )
    
    state.logs.append(f"[Consolidate] 整合完成，共汇�?{len(all_anomalies)} 个异�?)
    return state

