# LangGraph 循环工作流构建与编译入口
from __future__ import annotations

from typing import Any, Literal

from langgraph.graph import StateGraph, END
from app.memory.state import DetectionState
from app.core.self_reflect import self_reflect_node
from app.core.wait_user import wait_user_node
from app.core.supplement import supplement_node
from app.core.answer_node import answer_node

# 节点函数（延迟导入，避免循环依赖）
async def _load_data_node(state: DetectionState) -> DetectionState:
    """数据加载节点。"""
    if not state.task:
        from app.exceptions.base import DataMissingError
        raise DataMissingError("DetectionTask missing")
    state.context["loaded"] = True
    state.logs.append("[数据加载] 任务数据已就绪")
    return state


async def _anomaly_detect_node(state: DetectionState) -> DetectionState:
    """异常检测节点（复用原有逻辑）。"""
    from app.tools.image_anomaly_detection import ImageAnomalyDetectionTool
    from app.exceptions.base import ToolExecutionError
    from app.memory.memory_manager import memory_manager
    from app.memory.models import ToolContextMemory

    params = state.task.parameters or {}
    tool_type = params.get("tool_type")

    if tool_type not in (None, "qwen3.5-plus", "qwen3.5-plus_image"):
        state.errors.append(f"unsupported_tool_type: {tool_type}")

    tool = ImageAnomalyDetectionTool()
    try:
        response = await tool.run(state.task)
    except Exception as e:
        raise ToolExecutionError(
            tool.name, {"task_id": state.task.task_id}, e
        )

    if response.success and response.result:
        state.result = response.result
        asset_id = state.task.asset_id

        # ── 记录工具上下文记忆（含 asset_id，供效果追踪）──
        memory_manager.add_tool_context(
            ToolContextMemory(
                task_id=state.task.task_id,
                step_id=1,
                asset_id=asset_id,  # 【优化】关联资产
                tool_name=tool.name,
                tool_input={"tool_type": tool_type},
                tool_output={
                    "status": response.result.status,
                    "anomaly_count": len(response.result.anomalies or []),
                },
            )
        )

        # ── 写中期记忆（ShortTermMemory）【优化新增】──
        if state.result.anomalies:
            from app.memory.models import ShortTermMemory
            anomaly_types = [a.get("type", "未知") for a in state.result.anomalies]
            short_mem = ShortTermMemory(
                asset_id=asset_id or "",
                user_id=(state.task.parameters or {}).get("user_id", "default_user"),
                memory_summary=(
                    f"检出 {len(state.result.anomalies)} 个异常："
                    + "、".join(anomaly_types)
                ),
                memory_details={"anomalies": state.result.anomalies},
                tags=anomaly_types,
                anomaly_count=len(state.result.anomalies),
            )
            memory_manager.add_short_term_memory(short_mem)
            state.logs.append(
                f"[中期记忆] 已写入 asset_id={asset_id}，异常类型={anomaly_types}"
            )

        state.logs.append(f"[异常检测] 完成，检出 {len(response.result.anomalies)} 个异常")
    else:
        state.errors.append(response.error or "Unknown tool error")

    return state


# ---------------------------------------------------------------------------
# 路由决策函数（条件边）
# ---------------------------------------------------------------------------

def _route_after_reflect(state: DetectionState) -> Literal["wait_user", "supplement", "answer"]:
    """
    自检节点后的条件路由：
      need_user  → wait_user（用户澄清）
      retry      → supplement（补充分析，重新回到异常检测区）
      proceed    → answer（进入对话回答，不直接生成报告）
    """
    decision = state.reflection_decision or "proceed"
    if decision == "need_user":
        return "wait_user"
    elif decision == "retry":
        return "supplement"
    else:
        return "answer"


def _route_after_supplement(state: DetectionState) -> Literal["self_reflect", "answer"]:
    """
    补充分析后的路由：
      loop_count < MAX_LOOP → 回到 self_reflect 重新评估
      否则强制进入 answer
    """
    from app.core.self_reflect import MAX_LOOP
    if state.loop_count < MAX_LOOP:
        return "self_reflect"
    return "answer"


def _route_after_wait_user(state: DetectionState) -> Literal["supplement", "answer"]:
    """
    用户澄清后的路由：
      有补充信息 → supplement（基于用户回复深化分析）
      无补充信息 → answer（进入对话回答）
    """
    has_reply = bool(
        state.conversation_history
        and any(m.get("role") == "user" for m in state.conversation_history)
    )
    return "supplement" if has_reply else "answer"


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
    graph.add_node("anomaly_detect", _anomaly_detect_node)
    graph.add_node("self_reflect", self_reflect_node)
    graph.add_node("wait_user", wait_user_node)
    graph.add_node("supplement", supplement_node)
    graph.add_node("answer", answer_node)

    # report_node 复用原有 summarize 逻辑
    from app.core import _summarize_node
    graph.add_node("report", _summarize_node)

    # ── 固定边 ──
    graph.set_entry_point("load_data")
    graph.add_edge("load_data", "anomaly_detect")
    graph.add_edge("anomaly_detect", "self_reflect")

    # ── 条件边 ──
    # self_reflect → [wait_user | supplement | answer]
    graph.add_conditional_edges(
        "self_reflect",
        _route_after_reflect,
        {
            "wait_user": "wait_user",
            "supplement": "supplement",
            "answer": "answer",
        },
    )

    # supplement → [self_reflect（循环）| answer]
    graph.add_conditional_edges(
        "supplement",
        _route_after_supplement,
        {
            "self_reflect": "self_reflect",
            "answer": "answer",  # 循环结束进入回答
        },
    )

    # wait_user → [supplement | answer]
    graph.add_conditional_edges(
        "wait_user",
        _route_after_wait_user,
        {
            "supplement": "supplement",
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
