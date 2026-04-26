"""
LangGraph 状态模型定义，贯穿整个检测流程。
支持循环工作流：循环计数、置信度评估、用户输入挂起等。

注意：所有字段均使用「后写覆盖」策略（不用 add），
因为节点返回的是完整 state 对象（原地修改后返回），add 会导致日志/历史翻倍。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.schemas.detection import DetectionResult, DetectionTask


def merge_context(left: Dict[str, Any], right: Dict[str, Any]) -> Dict[str, Any]:
    """
    用于 LangGraph 的上下文字段合并函数。
    LangGraph 在多步更新同一字段时会调用此函数，将状态合并。
    对于 dict 类型，采用「后写覆盖前写」的策略。
    """
    merged = dict(left or {})
    merged.update(right or {})
    return merged


class DetectionState(BaseModel):
    """LangGraph 检测状态，贯穿整个循环工作流。"""

    # 必选：任务输入
    task: DetectionTask

    # 上下文字典（合并策略）
    context: Dict[str, Any] = Field(default_factory=dict)
    # 日志 / 错误列表（后写覆盖，因为节点返回完整 state）
    logs: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)

    # 检测结果
    result: Optional[DetectionResult] = None

    # ─── 动态编排相关字段 ───
    # 已执行的工具步骤：List[Tuple[AgentAction, str]] (action, observation)
    intermediate_steps: List[Any] = Field(default_factory=list)
    # 待执行的工具调用
    tool_calls: List[Dict[str, Any]] = Field(default_factory=list)
    # 工具执行结果汇总
    tool_outputs: List[Dict[str, Any]] = Field(default_factory=list)
    # 子 Agent 执行结果汇总（Phase 1）
    agent_outputs: Dict[str, Any] = Field(default_factory=dict)
    agent_trace: List[Dict[str, Any]] = Field(default_factory=list)
    active_agent: Optional[str] = None
    shared_context: Dict[str, Any] = Field(default_factory=dict)

    # 对话历史，支持多轮交互（后写覆盖，因为节点返回完整 state）
    conversation_history: List[Dict[str, str]] = Field(default_factory=list)

    # ─── 循环控制字段 ───
    # 当前循环轮次（从 1 开始）
    loop_count: int = 0

    # 是否需要用户澄清（human-in-the-loop）
    needs_user_input: bool = False

    # 用户回复内容（由 wait_user_node 写入，self_reflect_node 消费）
    user_reply: Optional[str] = None

    # 自检结论（由 self_reflect_node 写入，supplement_node / summarize_node 消费）
    # "proceed" | "retry" | "need_user"
    reflection_decision: Optional[str] = None

    # 自检详情（供下游节点使用）
    confidence: float = 0.0
    unknown_anomaly_types: List[str] = Field(default_factory=list)

    # 当前执行步骤（用于日志）
    current_step: int = 1

    # ─── 交互控制字段 ───
    # 用户是否请求生成报告（点击生成报告按钮后设为 True）
    report_requested: bool = False
    # 当前阶段："chat"（对话模式）| "report"（报告模式）
    stage: str = "chat"
