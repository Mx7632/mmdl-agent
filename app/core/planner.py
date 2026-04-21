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
1. timeseries_anomaly_detection: 分析传感器数值序列、振动数据、压力、温度等时序数据。
2. visual_anomaly_detection: 分析工业设备图像、照片。用于识别表面缺陷、破损、漏油、仪表读数异常、环境风险等。
3. knowledge_retrieval: 检索工业领域专家知识库、设备手册、历史故障案例、相似异常样本。

规划策略：
- **图像优先**：如果任务上下文中显示【已附带图像】，且用户问题涉及“看看”、“图像里有什么”、“有没有异常”、“检查照片”等，必须调用 `visual_anomaly_detection`。
- **数据互补**：如果问题涉及具体指标（如振动高、压力大），调用 `timeseries` 工具。
- **深度诊断**：如果需要判断异常原因、风险等级或维修建议，务必调用 `knowledge_retrieval` 工具。
- **多步决策**：你可以一次性决定调用多个工具，也可以根据上一步的执行结果（Observation）逐步推进。
- **直接回答**：如果你认为信息已经足够回答用户，请输出你的分析结论，不再调用工具。

当前任务上下文：
- Asset ID: {asset_id}
- Time Range: {start_time} 至 {end_time}
"""

async def planner_node(state: DetectionState) -> DetectionState:
    """规划器 node：决定下一步行动。"""
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
    has_image = bool(state.task.parameters.get("image_base64"))
    image_info = "【重要提示：当前任务已附带工业现场图像，如需分析图像内容，请务必调用 visual_anomaly_detection 工具】" if has_image else "（注：当前任务未提供图像数据）"

    system_msg = PLANNER_SYSTEM_PROMPT.format(
        asset_id=state.task.asset_id,
        start_time=state.task.start_time,
        end_time=state.task.end_time
    ) + f"\n\n实时环境信息：\n{image_info}"
    
    messages = [
        {"role": "system", "content": system_msg},
    ]

    # 注入历史对话背景
    if state.conversation_history:
        # 只保留最近几轮对话，避免上下文过长
        recent_history = state.conversation_history[-6:] if len(state.conversation_history) > 6 else state.conversation_history
        for msg in recent_history[:-1]: # 除了最后一条（当前问题）
            messages.append(msg)

    # 注入当前用户提问
    messages.append({"role": "user", "content": f"当前提问：{state.task.question}"})

    # 注入当前问题的中间步骤（如果有）
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
