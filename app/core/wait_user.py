from __future__ import annotations

import copy
import logging
from typing import Union

from app.memory.state import DetectionState

logger = logging.getLogger(__name__)


async def wait_user_node(state: DetectionState) -> DetectionState:
    clarification_ctx = state.shared_context.clarification

    if state.user_reply:
        state.conversation_history.append({"role": "user", "content": state.user_reply})
        state.context["user_reply_received"] = True
        state.context["pending_clarification"] = None
        state.context["pending_question"] = None
        if clarification_ctx:
            clarification_ctx.pending_clarification = None
            clarification_ctx.pending_question = None
            clarification_ctx.requires_human = False
        state.logs.append(
            f"[WaitUser] Received user reply, conversation turns={len(state.conversation_history)}"
        )
        state.execution_events.append(
            {
                "type": "task_resumed",
                "task_id": state.task.task_id,
                "conversation_turns": len(state.conversation_history),
            }
        )
        state.user_reply = None
        state.needs_user_input = False
    else:
        if clarification_ctx:
            state.context["pending_clarification"] = clarification_ctx.pending_clarification
            state.context["pending_question"] = clarification_ctx.pending_question
            state.logs.append(
                f"[WaitUser] Suspended for clarification: {clarification_ctx.unknown_anomaly_types}"
            )
            state.execution_events.append(
                {
                    "type": "task_suspended",
                    "task_id": state.task.task_id,
                    "pending_question": clarification_ctx.pending_question,
                    "unknown_anomaly_types": list(clarification_ctx.unknown_anomaly_types),
                }
            )
        else:
            state.context["pending_clarification"] = "Additional user information is required."
            state.context["pending_question"] = "Please provide more concrete observations from the site."
            state.logs.append("[WaitUser] Suspended without structured clarification context")
            state.execution_events.append(
                {
                    "type": "task_suspended",
                    "task_id": state.task.task_id,
                    "pending_question": state.context["pending_question"],
                    "unknown_anomaly_types": [],
                }
            )

    return state


def build_continue_state(task_id: str, user_reply: str, previous_state: Union[DetectionState, dict]) -> dict:
    if isinstance(previous_state, DetectionState):
        state_dict = previous_state.model_dump()
    else:
        state_dict = copy.deepcopy(previous_state)

    state_dict["user_reply"] = user_reply
    state_dict["needs_user_input"] = False
    state_dict["logs"] = list(state_dict.get("logs", []))
    state_dict["logs"].append(f"[Continue] User reply accepted, task_id={task_id}")
    context = dict(state_dict.get("context", {}))
    context["user_reply_received"] = False
    state_dict["context"] = context
    return state_dict
