"""
Agent 执行入口。
封装 LangGraph 图的构建、执行、以及对话续传逻辑。

重构要点：
  - run_detection: 首次检测，走完整图 → 返回 answer
  - run_chat: 多轮对话，直接调用 answer_node（不重跑检测）
  - generate_report: 生成报告，直接调用 _summarize_node
  - continue_detection: 续传检测（需补分析），走完整图
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from app.core import build_graph
from app.core.answer_node import answer_node
from app.core.wait_user import build_continue_state
from app.memory.checkpoint import MemoryCheckpointStore
from app.memory.state import DetectionState
from app.schemas.detection import DetectionTask

logger = logging.getLogger(__name__)

# ── 检查点存储（用于任务挂起/续传）─────────────────────────────────────────
_checkpoint_store = MemoryCheckpointStore()


def get_pending_task(task_id: str) -> Optional[dict]:
    """查询挂起任务的澄清信息。"""
    state = _checkpoint_store.load(task_id)
    if state is None:
        return None
    if not state.get("needs_user_input", False):
        return None
    ctx = state.get("context", {})
    return {
        "task_id": task_id,
        "pending_clarification": ctx.get("pending_clarification"),
        "pending_question": ctx.get("pending_question"),
        "conversation_history": list(state.get("conversation_history", [])),
        "loop_count": state.get("loop_count", 0),
    }


def _restore_state(state_dict: dict) -> DetectionState:
    """从 dict 安全恢复 DetectionState，处理嵌套 Pydantic 对象。"""
    try:
        return DetectionState.model_validate(state_dict)
    except Exception as e:
        logger.error(f"[Agent] 状态恢复失败: {e}")
        raise ValueError(f"任务状态损坏，无法恢复: {e}")


async def run_detection(task: DetectionTask) -> dict[str, Any]:
    """
    执行检测任务（主入口）。
    首次检测：走完整图 → 返回 answer，不生成报告。
    """
    logger.info(f"[run_detection] START task_id={task.task_id}, question={task.question}")
    graph = build_graph()
    state = DetectionState(task=task, stage="chat")

    # ── 执行图（支持中途挂起），返回原始 dict ──
    logger.info(f"[run_detection] calling _run_with_suspend...")
    result_dict = await _run_with_suspend(graph, state)
    logger.info(
        f"[run_detection] _run_with_suspend returned, "
        f"keys={list(result_dict.keys()) if isinstance(result_dict, dict) else 'NOT_DICT'}"
    )

    # ── 判断是否挂起 ──
    needs_suspend = result_dict.get("needs_user_input") and not result_dict.get("user_reply")
    if needs_suspend:
        _checkpoint_store.save(result_dict)
        ctx = result_dict.get("context", {})
        return {
            "status": "pending",
            "task_id": task.task_id,
            "message": "需要用户澄清，请调用续传接口提交回复",
            "pending_clarification": ctx.get("pending_clarification"),
            "pending_question": ctx.get("pending_question"),
            "loop_count": result_dict.get("loop_count", 0),
            "conversation_history": list(result_dict.get("conversation_history", [])),
        }

    # 正常完成，保存状态供后续对话使用
    _checkpoint_store.save(result_dict)

    # 从 dict 提取 answer（graph.ainvoke 返回的嵌套对象可能是 Pydantic 实例，需兼容）
    answer = result_dict.get("context", {}).get("answer", "已检测到异常，请继续提问或点击生成报告。")
    result_obj = result_dict.get("result")
    if result_obj is not None:
        if isinstance(result_obj, dict):
            anomalies = result_obj.get("anomalies", [])
        elif hasattr(result_obj, "anomalies"):
            anomalies = result_obj.anomalies or []
        else:
            anomalies = []
    else:
        anomalies = []

    ans_for_log = repr(answer[:50]) if answer else "(empty)"
    logger.info(f"[Agent] answer提取成功 len={len(answer) if answer else 0}, preview={ans_for_log}")

    return {
        "task_id": task.task_id,
        "status": "success",
        "answer": answer,
        "anomalies": anomalies,
        "metadata": {
            "logs": list(result_dict.get("logs", [])),
            "loop_count": result_dict.get("loop_count", 0),
            "confidence": result_dict.get("confidence", 0.0),
        },
    }


async def run_chat(task_id: str, question: str) -> dict[str, Any]:
    """
    多轮对话接口。
    直接调用 answer_node，不重跑完整检测图（避免重复调用视觉模型）。
    """
    previous_state = _checkpoint_store.load(task_id)
    if previous_state is None:
        raise ValueError(f"未找到任务: {task_id}，请先调用 /v1/detect 进行检测")

    # 从 dict 恢复 DetectionState
    state = _restore_state(previous_state)

    # 更新问题和对话历史
    state.task.question = question
    state.conversation_history.append({"role": "user", "content": question})
    state.report_requested = False

    # ── 直接调用 answer_node（不重跑完整图）──
    state = await answer_node(state)

    # 保存状态
    _checkpoint_store.save(state.model_dump())

    # 提取结果
    answer = state.context.get("answer", "抱歉，生成回答时出现错误，请重试。")
    anomalies = state.result.anomalies if state.result else []
    return {
        "task_id": task_id,
        "status": "success",
        "answer": answer,
        "anomalies": anomalies,
        "metadata": {
            "logs": list(state.logs),
            "loop_count": state.loop_count,
        },
    }


async def generate_report(task_id: str) -> dict[str, Any]:
    """
    生成完整报告接口。
    直接调用 _summarize_node，不重跑完整检测图。
    """
    previous_state = _checkpoint_store.load(task_id)
    if previous_state is None:
        raise ValueError(f"未找到任务: {task_id}，请先调用 /v1/detect 进行检测")

    state = _restore_state(previous_state)

    if not state.result:
        raise ValueError(f"任务 {task_id} 没有检测结果，无法生成报告")

    state.report_requested = True
    state.stage = "report"

    # ── 直接调用 _summarize_node ──
    from app.core import _summarize_node
    state = await _summarize_node(state)

    # 保存状态
    _checkpoint_store.save(state.model_dump())

    result = state.result
    return {
        "task_id": task_id,
        "status": result.status if result else "success",
        "summary": result.summary if result else None,
        "anomalies": result.anomalies if result else [],
        "has_report": True,
        "conversation_history": list(state.conversation_history),
        "metadata": {
            "logs": list(state.logs),
            "loop_count": state.loop_count,
        },
    }


async def continue_detection(task_id: str, user_reply: str) -> dict[str, Any]:
    """
    续传检测任务（用户澄清后调用）。
    此场景需要重新跑图（因为要经过 supplement → self_reflect 路径）。
    """
    previous_state = _checkpoint_store.load(task_id)
    if previous_state is None:
        raise ValueError(f"未找到挂起的任务: {task_id}")

    continued_state = build_continue_state(task_id, user_reply, previous_state)
    continued_state["needs_user_input"] = False

    graph = build_graph()
    result_dict = await _run_with_suspend(graph, continued_state)

    needs_suspend = result_dict.get("needs_user_input") and not result_dict.get("user_reply")
    if needs_suspend:
        _checkpoint_store.save(result_dict)
        ctx = result_dict.get("context", {})
        return {
            "status": "pending",
            "task_id": task_id,
            "message": "需要用户进一步澄清",
            "pending_clarification": ctx.get("pending_clarification"),
            "pending_question": ctx.get("pending_question"),
            "loop_count": result_dict.get("loop_count", 0),
            "conversation_history": list(result_dict.get("conversation_history", [])),
        }

    # 正常结束
    _checkpoint_store.save(result_dict)
    answer = result_dict.get("context", {}).get("answer", "")
    result_obj = result_dict.get("result")
    if result_obj is not None:
        if isinstance(result_obj, dict):
            anomalies = result_obj.get("anomalies", [])
        elif hasattr(result_obj, "anomalies"):
            anomalies = result_obj.anomalies or []
        else:
            anomalies = []
    else:
        anomalies = []
    return {
        "task_id": task_id,
        "status": "success",
        "answer": answer,
        "anomalies": anomalies,
        "has_report": False,
        "conversation_history": list(result_dict.get("conversation_history", [])),
        "metadata": {
            "logs": list(result_dict.get("logs", [])),
            "loop_count": result_dict.get("loop_count", 0),
        },
    }


async def _run_with_suspend(graph, initial_state) -> dict:
    """
    内部方法：执行图，允许在 wait_user 节点处挂起并返回。
    graph.invoke() 返回 dict（LangGraph 1.0 行为）。
    直接返回 dict，避免 model_validate 破坏 context。
    """
    logger.info("[_run_with_suspend] invoking graph.ainvoke...")

    # 确保输入是 dict 格式（graph.ainvoke 接受 dict）
    if isinstance(initial_state, DetectionState):
        invoke_input = initial_state.model_dump()
    else:
        invoke_input = initial_state

    result_dict: dict = await graph.ainvoke(invoke_input)
    logger.info(
        f"[_run_with_suspend] invoke returned, "
        f"keys={list(result_dict.keys()) if isinstance(result_dict, dict) else type(result_dict)}"
    )
    ctx = result_dict.get("context", {}) if isinstance(result_dict, dict) else {}
    answer_preview = ctx.get("answer", "")[:80] if ctx.get("answer") else "EMPTY"
    logger.info(f"[_run_with_suspend] answer from dict={repr(answer_preview)}")

    return result_dict
