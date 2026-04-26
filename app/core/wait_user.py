"""
用户澄清节点（Wait for User Node）
职责：
  - 将任务状态挂起，写入待确认清单
  - 对话续传时读取 user_reply 并写入 conversation_history
  - 本节点为可中断节点：收到用户回复后继续，回复内容供后续节点消费
"""

from __future__ import annotations

import copy
import logging
from typing import Any, Union

from app.memory.state import DetectionState

logger = logging.getLogger(__name__)


async def wait_user_node(state: DetectionState) -> DetectionState:
    """
    用户澄清节点。

    两种调用时机：
      1. 首次进入：state.needs_user_input=True，state.user_reply=None
         → 写入澄清请求内容到 context（供 API 查询），返回状态等待外部续传
      2. 续传：state.user_reply 有值
         → 将用户回复追加到 conversation_history，清除挂起标记，继续流转
    """
    if state.user_reply:
        # ── 用户已回复，追加对话历史 ──
        state.conversation_history.append({
            "role": "user",
            "content": state.user_reply,
        })
        state.context["user_reply_received"] = True
        state.context["pending_clarification"] = None
        state.logs.append(
            f"[等待用户] 收到用户回复，已追加到对话历史，共 {len(state.conversation_history)} 条"
        )
        # 清除回复字段，避免重复追加
        state.user_reply = None
    else:
        # ── 首次进入，挂起等待 ──
        clarification_items = state.unknown_anomaly_types or []
        pending_text = (
            f"请协助确认以下异常类型的具体情况：\n"
            + "\n".join(f"  - {t}" for t in clarification_items)
        )
        state.context["pending_clarification"] = pending_text
        state.context["pending_question"] = (
            "以上异常类型需要人工核实，请提供你观察到的具体情况或补充信息，"
            "帮助我生成更准确的检测报告。"
        )
        state.logs.append(
            f"[等待用户] 任务 {state.task.task_id} 挂起，等待用户澄清 "
            f"异常类型: {clarification_items}"
        )

    return state


# ---------------------------------------------------------------------------
# 对话续传接口（供 API 层调用）
# ---------------------------------------------------------------------------

def build_continue_state(
    task_id: str,
    user_reply: str,
    previous_state: Union[DetectionState, dict],
) -> dict:
    """
    在 API 收到用户回复后，构造一个新的检测状态（续传）。
    支持 dict 或 DetectionState 输入（checkpoint 现在存 dict）。
    """
    # 统一为 dict
    if isinstance(previous_state, DetectionState):
        state_dict = previous_state.model_dump()
    else:
        state_dict = copy.deepcopy(previous_state)

    state_dict["user_reply"] = None
    state_dict["conversation_history"] = list(state_dict.get("conversation_history", []))
    state_dict["conversation_history"].append({"role": "user", "content": user_reply})
    state_dict["needs_user_input"] = False
    state_dict["logs"] = list(state_dict.get("logs", []))
    state_dict["logs"].append(f"[续传] 用户回复已写入，task_id={task_id}")
    return state_dict
