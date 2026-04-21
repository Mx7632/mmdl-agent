"""
智能规划器节点 (Planner Node)
职责：
  1. 分析用户问题和任务上下文
  2. 决定是否需要调用工具（时序检测、视觉检测、知识检索）
  3. 生成工具调用指令或最终回答决策
"""
from __future__ import annotations

import logging
from typing import List, Dict, Any

from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from app.config.settings import settings
from app.memory.state import DetectionState
from app.core.tools import get_industrial_tools

logger = logging.getLogger(__name__)

PLANNER_SYSTEM_PROMPT = """你是一个专业的工业异常检测调度专家。
你的任务是根据用户提出的问题和设备上下文，编排合适的工具来完成诊断。

可用工具：
1. timeseries_anomaly_detection: 分析时序数据（振动、压力、温度等）。
2. visual_anomaly_detection: 分析图像数据（缺陷、仪表、环境）。
3. knowledge_retrieval: 检索专家知识库、手册、相似案例。

规划策略：
- 如果问题涉及具体指标异常，优先调用 timeseries 工具。
- 如果提供了图像数据或涉及外观检查，优先调用 visual 工具。
- 如果需要判断异常原因、风险等级或维修建议，务必调用 knowledge_retrieval 工具。
- 你可以一次性决定调用多个工具，也可以根据上一步的执行结果（Observation）逐步推进。
- 如果你认为信息已经足够回答用户，请输出你的分析结论，不再调用工具。

当前任务上下文：
- Asset ID: {asset_id}
- Time Range: {start_time} 至 {end_time}
"""

async def planner_node(state: DetectionState) -> DetectionState:
    """规划器节点：决定下一步行动。"""
    if state.loop_count >= 3: # 熔断限制
        state.logs.append("[Planner] 达到最大编排深度，停止规划")
        state.reflection_decision = "proceed"
        return state

    state.logs.append(f"[Planner] 开始分析任务，当前步骤: {len(state.intermediate_steps) + 1}")

    # 1. 准备 LLM
    llm = ChatOpenAI(
        model=settings.llm_model,
        temperature=0,
        api_key=SecretStr(settings.openai_api_key),
        base_url=settings.llm_base_url
    )
    tools = get_industrial_tools()
    llm_with_tools = llm.bind_tools(tools)

    # 2. 构造消息列表
    system_msg = PLANNER_SYSTEM_PROMPT.format(
        asset_id=state.task.asset_id,
        start_time=state.task.start_time,
        end_time=state.task.end_time
    )
    
    messages = [
        {"role": "system", "content": system_msg},
        {"role": "user", "content": f"用户问题：{state.task.question}"}
    ]

    # 注入中间步骤
    for action, observation in state.intermediate_steps:
        # 这里简化处理，将 action 转为消息
        messages.append({"role": "assistant", "content": None, "tool_calls": [action]})
        messages.append({"role": "tool", "content": observation, "tool_call_id": action["id"]})

    # 3. 调用 LLM
    try:
        response = await llm_with_tools.ainvoke(
            messages,
            config={
                "tags": ["planner_thought"],
                "metadata": {"langgraph_node": "planner"}
            }
        )
        
        if response.tool_calls:
            state.tool_calls = response.tool_calls
            state.reflection_decision = "retry" # 意味着需要去执行工具
            state.logs.append(f"[Planner] 决定调用工具: {[tc['name'] for tc in response.tool_calls]}")
        else:
            state.reflection_decision = "proceed" # 意味着可以直接回答
            state.context["planner_thought"] = response.content
            state.logs.append("[Planner] 信息已充足，准备回答")
            
    except Exception as e:
        logger.error(f"[Planner] 规划失败: {e}")
        state.errors.append(f"Planner error: {str(e)}")
        state.reflection_decision = "proceed"

    return state
