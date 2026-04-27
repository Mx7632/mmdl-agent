from __future__ import annotations

import copy
import logging
from typing import Union

from app.memory.conversation import compact_state_conversation
from app.memory.state import DetectionState
from app.orchestration.context_store import clear_pending_clarification, set_pending_clarification

logger = logging.getLogger(__name__)


async def wait_user_node(state: DetectionState) -> DetectionState:
    task_runtime = state.task_runtime()
    orchestration_runtime = state.orchestration_runtime()
    clarification_ctx = state.domain_runtime().shared_context.clarification

    if task_runtime.user_reply:
        task_runtime.conversation_history.append({"role": "user", "content": task_runtime.user_reply})
        state.context["user_reply_received"] = True
        clear_pending_clarification(state)
        state.logs.append(
            f"[WaitUser] Received user reply, conversation turns={len(task_runtime.conversation_history)}"
        )
        orchestration_runtime.execution_events.append(
            {
                "type": "task_resumed",
                "task_id": state.task.task_id,
                "conversation_turns": len(task_runtime.conversation_history),
            }
        )
        task_runtime.user_reply = None
        orchestration_runtime.needs_user_input = False
    else:
        if clarification_ctx:
            set_pending_clarification(
                state,
                pending_clarification=clarification_ctx.pending_clarification,
                pending_question=clarification_ctx.pending_question,
                unknown_anomaly_types=list(clarification_ctx.unknown_anomaly_types),
                requires_human=True,
            )
            state.logs.append(
                f"[WaitUser] Suspended for clarification: {clarification_ctx.unknown_anomaly_types}"
            )
            orchestration_runtime.execution_events.append(
                {
                    "type": "task_suspended",
                    "task_id": state.task.task_id,
                    "pending_question": clarification_ctx.pending_question,
                    "unknown_anomaly_types": list(clarification_ctx.unknown_anomaly_types),
                }
            )
        else:
            set_pending_clarification(
                state,
                pending_clarification="Additional user information is required.",
                pending_question="Please provide more concrete observations from the site.",
                unknown_anomaly_types=[],
                requires_human=True,
            )
            state.logs.append("[WaitUser] Suspended without structured clarification context")
            orchestration_runtime.execution_events.append(
                {
                    "type": "task_suspended",
                    "task_id": state.task.task_id,
                    "pending_question": state.context["pending_question"],
                    "unknown_anomaly_types": [],
                }
            )

    state.apply_task_runtime(task_runtime)
    if task_runtime.conversation_history:
        compact_state_conversation(state)
    state.apply_orchestration_runtime(orchestration_runtime)
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
