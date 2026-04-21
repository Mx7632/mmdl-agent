# LangGraph 循环工作流构建与编译入口
from __future__ import annotations

from typing import Any, Literal

from langgraph.graph import StateGraph, END
from app.memory.state import DetectionState
from app.core.self_reflect import self_reflect_node
from app.core.wait_user import wait_user_node
from app.core.supplement import supplement_node
from app.core.answer_node import answer_node
from app.core.planner import planner_node
from app.core.executor import executor_node
from app.core.consolidate import consolidate_node

# 节点函数（延迟导入，避免循环依赖）
async def _load_data_node(state: DetectionState) -> DetectionState:
    """数据加载节点。"""
    if not state.task:
        from app.exceptions.base import DataMissingError
        raise DataMissingError("DetectionTask missing")
    state.context["loaded"] = True
    state.logs.append("[数据加载] 任务数据已就绪")
    return state


# ---------------------------------------------------------------------------
# 路由决策函数（条件边）
# ---------------------------------------------------------------------------

def _route_after_planner(state: DetectionState) -> Literal["executor", "consolidate"]:
    """规划器后的路由：执行工具或进入整合阶段。"""
    if state.reflection_decision == "retry":
        return "executor"
    return "consolidate"


def _route_after_reflect(state: DetectionState) -> Literal["wait_user", "planner", "answer"]:
    """
    自检节点后的条件路由：
      need_user  → wait_user（用户澄清）
      retry      → planner（回到规划器，可能需要补充调用工具）
      proceed    → answer（进入对话回答）
    """
    decision = state.reflection_decision or "proceed"
    if decision == "need_user":
        return "wait_user"
    elif decision == "retry":
        return "planner"
    else:
        return "answer"


def _route_after_wait_user(state: DetectionState) -> Literal["planner", "answer"]:
    """
    用户澄清后的路由：
      有补充信息 → planner（重新规划）
      无补充信息 → answer（直接回答）
    """
    has_reply = bool(
        state.conversation_history
        and any(m.get("role") == "user" for m in state.conversation_history)
    )
    return "planner" if has_reply else "answer"


def _route_after_answer(state: DetectionState) -> Literal["report", END]:
    """
    对话回答后的路由：
      report_requested=True → report（生成完整报告）
      否则 → END（结束，等待用户后续操作）
    """
    if state.report_requested:
        return "report"
    return END


# ---------------------------------------------------------------------------
# 图构建
# ---------------------------------------------------------------------------

def build_graph() -> Any:
    """
    构建并编译循环检测工作流图（支持对话+报告模式）。

    节点执行顺序：
      load_data → anomaly_detect → self_reflect
                                              ↓
                              need_user → wait_user → supplement → self_reflect
                              retry     → supplement ↻
                              proceed   → answer → [report → END | END]
    """
    graph = StateGraph(DetectionState)

    # ── 注册节点 ──
    graph.add_node("load_data", _load_data_node)
    graph.add_node("planner", planner_node)
    graph.add_node("executor", executor_node)
    graph.add_node("consolidate", consolidate_node)
    graph.add_node("self_reflect", self_reflect_node)
    graph.add_node("wait_user", wait_user_node)
    graph.add_node("answer", answer_node)

    # report_node 复用原有 summarize 逻辑
    from app.core import _summarize_node
    graph.add_node("report", _summarize_node)

    # ── 固定边 ──
    graph.set_entry_point("load_data")
    graph.add_edge("load_data", "planner")
    graph.add_edge("executor", "planner") # 循环执行工具
    graph.add_edge("consolidate", "self_reflect")

    # ── 条件边 ──
    # planner → [executor | consolidate]
    graph.add_conditional_edges(
        "planner",
        _route_after_planner,
        {
            "executor": "executor",
            "consolidate": "consolidate",
        },
    )

    # self_reflect → [wait_user | planner | answer]
    graph.add_conditional_edges(
        "self_reflect",
        _route_after_reflect,
        {
            "wait_user": "wait_user",
            "planner": "planner",
            "answer": "answer",
        },
    )

    # wait_user → [planner | answer]
    graph.add_conditional_edges(
        "wait_user",
        _route_after_wait_user,
        {
            "planner": "planner",
            "answer": "answer",
        },
    )

    # answer → [report | END]
    graph.add_conditional_edges(
        "answer",
        _route_after_answer,
        {
            "report": "report",
            END: END,
        },
    )

    graph.add_edge("report", END)

    return graph.compile()
