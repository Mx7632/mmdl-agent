"""
Agent 执行入口。
封装 LangGraph 图的构建、执行、以及对话续传逻辑。
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from app.core import build_graph
from app.core.wait_user import build_continue_state
from app.memory.checkpoint import MemoryCheckpointStore
from app.memory.state import DetectionState
from app.schemas.detection import DetectionTask

logger = logging.getLogger(__name__)

# ── 检查点存储（用于任务挂起/续传）─────────────────────────────────────────
_checkpoint_store = MemoryCheckpointStore()


def get_pending_task(task_id: str) -> Optional[dict]:
    """
    查询挂起任务（等待用户输入的任务）的澄清信息。
    供 API 层调用，返回给前端展示。
    """
    state = _checkpoint_store.load(task_id)
    if state is None:
        return None
    if not getattr(state, "needs_user_input", False):
        return None
    return {
        "task_id": task_id,
        "pending_clarification": state.context.get("pending_clarification"),
        "pending_question": state.context.get("pending_question"),
        "conversation_history": list(state.conversation_history),
        "loop_count": state.loop_count,
    }


async def run_detection(task: DetectionTask) -> dict[str, Any]:
    """
    执行检测任务（主入口）。
    首次检测：只返回答案，不生成报告。
    自动判断是否首次执行还是续传：
      - needs_user_input=True & 无 user_reply → 挂起任务，等待续传
      - 正常执行完成 → 返回结果（包含 answer）
    """
    graph = build_graph()
    state = DetectionState(task=task, stage="chat")

    # ── 执行图（支持中途挂起）──
    result_state = await _run_with_suspend(graph, state)

    # ── 判断是否挂起 ──
    needs_suspend = (
        getattr(result_state, "needs_user_input", False)
        and not getattr(result_state, "user_reply", None)
    )
    if needs_suspend:
        # 保存检查点，供后续续传使用
        _checkpoint_store.save(result_state)
        return {
            "status": "pending",
            "task_id": task.task_id,
            "message": "需要用户澄清，请调用续传接口提交回复",
            "pending_clarification": result_state.context.get("pending_clarification"),
            "pending_question": result_state.context.get("pending_question"),
            "loop_count": result_state.loop_count,
            "conversation_history": list(result_state.conversation_history),
        }

    # 正常完成，保存状态供后续对话使用
    _checkpoint_store.save(result_state)

    # 返回对话模式结果（包含 answer，不包含完整报告）
    return _extract_chat_result(result_state)


async def run_chat(task_id: str, question: str) -> dict[str, Any]:
    """
    多轮对话接口。
    基于已有检测状态，回答用户新问题。
    """
    previous_state = _checkpoint_store.load(task_id)
    if previous_state is None:
        raise ValueError(f"未找到任务: {task_id}，请先调用 /v1/detect 进行检测")

    # 更新问题和对话历史
    previous_state.task.question = question
    previous_state.conversation_history.append({
        "role": "user",
        "content": question,
    })
    previous_state.report_requested = False  # 对话模式不生成报告

    # 重新执行图（从 answer 节点开始）
    graph = build_graph()
    result_state = await _run_with_suspend(graph, previous_state)

    # 保存更新后的状态
    _checkpoint_store.save(result_state)

    return _extract_chat_result(result_state)


async def generate_report(task_id: str) -> dict[str, Any]:
    """
    生成完整报告接口。
    用户点击"生成报告"按钮后调用。
    """
    previous_state = _checkpoint_store.load(task_id)
    if previous_state is None:
        raise ValueError(f"未找到任务: {task_id}，请先调用 /v1/detect 进行检测")

    if previous_state.result is None:
        raise ValueError(f"任务 {task_id} 没有检测结果，无法生成报告")

    # 设置报告请求标志，重新执行图
    previous_state.report_requested = True
    previous_state.stage = "report"

    graph = build_graph()
    result_state = await _run_with_suspend(graph, previous_state)

    # 保存更新后的状态
    _checkpoint_store.save(result_state)

    return _extract_report_result(result_state)


async def continue_detection(task_id: str, user_reply: str) -> dict[str, Any]:
    """
    续传检测任务（用户澄清后调用）。
    从检查点恢复状态，注入用户回复，继续执行图。
    """
    previous_state = _checkpoint_store.load(task_id)
    if previous_state is None:
        raise ValueError(f"未找到挂起的任务: {task_id}")

    # 注入用户回复，构造续传状态
    continued_state = build_continue_state(task_id, user_reply, previous_state)
    continued_state.needs_user_input = False

    # 重新执行图
    graph = build_graph()
    result_state = await _run_with_suspend(graph, continued_state)

    # 判断是否再次挂起
    needs_suspend = (
        getattr(result_state, "needs_user_input", False)
        and not getattr(result_state, "user_reply", None)
    )
    if needs_suspend:
        _checkpoint_store.save(result_state)
        return {
            "status": "pending",
            "task_id": task_id,
            "message": "需要用户进一步澄清",
            "pending_clarification": result_state.context.get("pending_clarification"),
            "pending_question": result_state.context.get("pending_question"),
            "loop_count": result_state.loop_count,
            "conversation_history": list(result_state.conversation_history),
        }

    return _extract_result(result_state)


async def _run_with_suspend(graph, initial_state: DetectionState) -> DetectionState:
    """
    内部方法：执行图，允许在 wait_user 节点处挂起并返回。
    LangGraph 1.0.10 astream() yields {"node_name": full_state_dict} 对象。
    每次迭代获取当前状态，检测到 needs_user_input=True 时中断。
    """
    result_state: DetectionState = initial_state

    # astream 每次 yield {"node_name": state_update_dict}
    async for event in graph.astream(result_state):
        # event key 是节点名，value 是当前完整状态快照
        if isinstance(event, dict):
            state_dict = next(iter(event.values()), None)
            if state_dict is not None:
                result_state = DetectionState.model_validate(state_dict)

        if (
            getattr(result_state, "needs_user_input", False)
            and not getattr(result_state, "user_reply", None)
        ):
            logger.info(f"[Agent] 任务 {result_state.task.task_id} 在 wait_user 节点挂起")
            break

    return result_state


def _extract_chat_result(state: DetectionState) -> dict[str, Any]:
    """从最终状态中提取对话模式结果（包含 answer，不包含完整报告）。"""
    result = getattr(state, "result", None)
    if result is None:
        return {
            "task_id": state.task.task_id,
            "status": "failed",
            "answer": "检测失败，请重试。",
            "anomalies": [],
            "has_report": False,
            "metadata": {"errors": list(state.errors), "logs": list(state.logs)},
        }

    # 附加元数据
    meta = dict(result.metadata or {})
    meta["loop_count"] = state.loop_count
    meta["confidence"] = getattr(state, "confidence", 0.0)
    meta["logs"] = list(state.logs)

    return {
        "task_id": state.task.task_id,
        "status": "success",
        "answer": state.context.get("answer", "已检测到异常，请继续提问或点击生成报告。"),
        "anomalies": result.anomalies or [],
        "has_report": False,
        "conversation_history": list(state.conversation_history),
        "metadata": meta,
    }


def _extract_report_result(state: DetectionState) -> dict[str, Any]:
    """从最终状态中提取报告模式结果（包含完整报告）。"""
    result = getattr(state, "result", None)
    if result is None:
        return {
            "task_id": state.task.task_id,
            "status": "failed",
            "summary": None,
            "anomalies": [],
            "has_report": False,
            "metadata": {"errors": list(state.errors), "logs": list(state.logs)},
        }

    # 附加元数据
    meta = dict(result.metadata or {})
    meta["loop_count"] = state.loop_count
    meta["confidence"] = getattr(state, "confidence", 0.0)
    meta["logs"] = list(state.logs)

    return {
        "task_id": state.task.task_id,
        "status": result.status,
        "summary": result.summary,
        "anomalies": result.anomalies or [],
        "has_report": True,
        "conversation_history": list(state.conversation_history),
        "metadata": meta,
    }


def _extract_result(state: DetectionState) -> dict[str, Any]:
    """从最终状态中提取结果字典（兼容旧接口）。"""
    return _extract_chat_result(state)
