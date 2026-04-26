from __future__ import annotations

from typing import Any, Literal

from langgraph.graph import END, StateGraph

from app.agents.report.service import generate_report_state
from app.core.answer_node import answer_node
from app.core.self_reflect import self_reflect_node
from app.core.supervisor import (
    supervisor_execute_node,
    supervisor_merge_node,
    supervisor_plan_node,
)
from app.core.wait_user import wait_user_node
from app.memory.state import DetectionState


async def _load_data_node(state: DetectionState) -> DetectionState:
    if not state.task:
        from app.exceptions.base import DataMissingError

        raise DataMissingError("DetectionTask missing")
    state.context["loaded"] = True
    state.logs.append("[LoadData] Task data loaded")
    return state


def _route_after_supervisor_plan(state: DetectionState) -> Literal["supervisor_execute", "supervisor_merge"]:
    planned_agents = state.context.get("planned_agents") or []
    if planned_agents:
        return "supervisor_execute"
    return "supervisor_merge"


def _route_after_reflect(state: DetectionState) -> Literal["wait_user", "supervisor_plan", "answer"]:
    decision = state.reflection_decision or "proceed"
    if decision == "need_user":
        return "wait_user"
    if decision == "retry":
        return "supervisor_plan"
    return "answer"


def _route_after_wait_user(state: DetectionState) -> Literal["supervisor_plan", "answer"]:
    has_reply = bool(
        state.conversation_history
        and any(message.get("role") == "user" for message in state.conversation_history)
    )
    return "supervisor_plan" if has_reply else "answer"


def _route_after_answer(state: DetectionState) -> Literal["report", END]:
    if state.report_requested:
        return "report"
    return END


def build_graph(*, checkpointer: Any = None, store: Any = None) -> Any:
    graph = StateGraph(DetectionState)

    graph.add_node("load_data", _load_data_node)
    graph.add_node("supervisor_plan", supervisor_plan_node)
    graph.add_node("supervisor_execute", supervisor_execute_node)
    graph.add_node("supervisor_merge", supervisor_merge_node)
    graph.add_node("self_reflect", self_reflect_node)
    graph.add_node("wait_user", wait_user_node)
    graph.add_node("answer", answer_node)
    graph.add_node("report", generate_report_state)

    graph.set_entry_point("load_data")
    graph.add_edge("load_data", "supervisor_plan")
    graph.add_edge("supervisor_execute", "supervisor_merge")
    graph.add_edge("supervisor_merge", "self_reflect")
    graph.add_edge("report", END)

    graph.add_conditional_edges(
        "supervisor_plan",
        _route_after_supervisor_plan,
        {
            "supervisor_execute": "supervisor_execute",
            "supervisor_merge": "supervisor_merge",
        },
    )

    graph.add_conditional_edges(
        "self_reflect",
        _route_after_reflect,
        {
            "wait_user": "wait_user",
            "supervisor_plan": "supervisor_plan",
            "answer": "answer",
        },
    )

    graph.add_conditional_edges(
        "wait_user",
        _route_after_wait_user,
        {
            "supervisor_plan": "supervisor_plan",
            "answer": "answer",
        },
    )

    graph.add_conditional_edges(
        "answer",
        _route_after_answer,
        {
            "report": "report",
            END: END,
        },
    )

    return graph.compile(checkpointer=checkpointer, store=store)
