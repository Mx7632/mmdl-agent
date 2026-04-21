"""
工具执行器节点 (Executor Node)
职责：
  1. 接收 Planner 的 tool_calls 指令
  2. 映射并执行对应的工业检测工具
  3. 捕获结果并返回给 State，供 Planner 下一轮参考
"""
from __future__ import annotations

import logging
from typing import Dict, Any, List

from app.memory.state import DetectionState
from app.core.tools import get_industrial_tools

logger = logging.getLogger(__name__)

async def executor_node(state: DetectionState) -> DetectionState:
    """执行器节点：并行执行 Planner 指定的工具。"""
    if not state.tool_calls:
        state.logs.append("[Executor] 无待执行工具")
        return state

    state.logs.append(f"[Executor] 正在执行 {len(state.tool_calls)} 个工具调用...")
    
    # 获取可用工具映射
    tools = {t.name: t for t in get_industrial_tools()}
    
    new_results = []
    
    for tool_call in state.tool_calls:
        tool_name = tool_call["name"]
        tool_args = tool_call["args"]
        tool_id = tool_call["id"]
        
        if tool_name not in tools:
            observation = f"Error: Tool {tool_name} not found."
        else:
            try:
                # 【重要修复】自动补全工具调用所需的通用参数
                if "task_id" not in tool_args:
                    tool_args["task_id"] = state.task.task_id
                if "asset_id" not in tool_args:
                    tool_args["asset_id"] = state.task.asset_id
                
                # 【重要修复】如果调用视觉检测且未传图片，从 state 中补全
                if tool_name == "visual_anomaly_detection" and not tool_args.get("image_base64"):
                    image_data = state.task.parameters.get("image_base64")
                    if image_data:
                        tool_args["image_base64"] = image_data
                        state.logs.append("[Executor] 已自动从任务上下文中注入图像数据")

                state.logs.append(f"[Executor] 运行工具: {tool_name}...")
                observation = await tools[tool_name].arun(tool_args)
            except Exception as e:
                logger.error(f"[Executor] 工具 {tool_name} 执行异常: {e}")
                observation = f"Error: {str(e)}"
        
        # 记录到中间步骤
        state.intermediate_steps.append((tool_call, observation))
        
        # 尝试解析结构化结果（如果是检测结果）
        try:
            import json
            parsed_obs = json.loads(observation)
            if isinstance(parsed_obs, dict) and "anomalies" in parsed_obs:
                state.tool_outputs.append({
                    "tool": tool_name,
                    "anomalies": parsed_obs["anomalies"]
                })
        except:
            pass # 非 JSON 结果或非检测结果，仅保留在 intermediate_steps

    # 清空 tool_calls 避免重复执行
    state.tool_calls = []
    
    # 增加循环计数，返回 Planner
    state.loop_count += 1
    
    return state
