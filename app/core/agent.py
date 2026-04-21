"""
Agent execution entrypoints.

This module wraps LangGraph workflow execution, checkpoint recovery, and
multi-turn conversation orchestration.
"""

from __future__ import annotations

import json
import logging
from typing import Any, AsyncGenerator, Optional

from app.core import build_graph
from app.core.wait_user import build_continue_state
from app.exceptions.base import AppError, TaskNotFoundError
from app.memory.checkpoint import MemoryCheckpointStore
from app.memory.state import DetectionState
from app.schemas.detection import DetectionTask

logger = logging.getLogger(__name__)

_checkpoint_store = MemoryCheckpointStore()


def get_pending_task(task_id: str) -> Optional[dict]:
    """Return the pending clarification payload for a suspended task."""
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
    """Safely restore DetectionState from a checkpoint dict."""
    try:
        return DetectionState.model_validate(state_dict)
    except Exception as e:
        logger.error(f"[Agent] state restore failed: {e}. State data: {state_dict.keys()}")
        raise AppError(f"Task state is corrupted and cannot be restored: {e}")


def _extract_anomalies(result_obj: Any) -> list[Any]:
    """Extract anomalies from either a dict result or a Pydantic model."""
    if result_obj is None:
        return []
    if isinstance(result_obj, dict):
        return result_obj.get("anomalies", [])
    if hasattr(result_obj, "anomalies"):
        return result_obj.anomalies or []
    return []


def _prepare_followup_state(
    previous_state: dict,
    *,
    question: Optional[str],
    parameters: Optional[dict[str, Any]] = None,
) -> DetectionState:
    """Restore a previous task state and prepare it for a new agent turn."""
    state = _restore_state(previous_state)

    state.task.question = question
    if parameters:
        state.task.parameters.update(parameters)

    if question:
        state.conversation_history.append({"role": "user", "content": question})

    state.report_requested = False
    state.stage = "chat"
    state.intermediate_steps = []
    state.tool_calls = []
    state.tool_outputs = []
    state.loop_count = 0
    state.reflection_decision = None
    state.needs_user_input = False
    state.user_reply = None

    return state


async def run_detection(task: DetectionTask) -> dict[str, Any]:
    """
    Execute a first-turn detection task.

    The full graph runs once and returns the answer without generating a report.
    """
    try:
        logger.info(f"[run_detection] START task_id={task.task_id}, question={task.question}")
        graph = build_graph()
        state = DetectionState(task=task, stage="chat")
        logger.info("[run_detection] calling _run_with_suspend...")
        result_dict = await _run_with_suspend(graph, state)
        logger.info("[run_detection] graph execution finished")
    except Exception as e:
        import traceback

        logger.error(f"[run_detection] CRITICAL ERROR: {e}\n{traceback.format_exc()}")
        raise

    logger.info(
        f"[run_detection] _run_with_suspend returned, "
        f"keys={list(result_dict.keys()) if isinstance(result_dict, dict) else 'NOT_DICT'}"
    )

    needs_suspend = result_dict.get("needs_user_input") and not result_dict.get("user_reply")
    if needs_suspend:
        _checkpoint_store.save(result_dict)
        ctx = result_dict.get("context", {})
        return {
            "status": "pending",
            "task_id": task.task_id,
            "message": "Additional user clarification is required before continuing.",
            "pending_clarification": ctx.get("pending_clarification"),
            "pending_question": ctx.get("pending_question"),
            "loop_count": result_dict.get("loop_count", 0),
            "conversation_history": list(result_dict.get("conversation_history", [])),
        }

    _checkpoint_store.save(result_dict)

    answer = result_dict.get("context", {}).get(
        "answer",
        "An anomaly was detected. You can continue asking questions or generate a report.",
    )
    anomalies = _extract_anomalies(result_dict.get("result"))

    ans_for_log = repr(answer[:50]) if answer else "(empty)"
    logger.info(
        f"[Agent] answer extracted successfully len={len(answer) if answer else 0}, preview={ans_for_log}"
    )

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
    Execute a new multi-turn question by re-entering the agent graph.

    Each follow-up turn is treated as a fresh agent run, so planner/executor can
    re-plan retrieval and tool usage in ReAct style.
    """
    previous_state = _checkpoint_store.load(task_id)
    if previous_state is None:
        raise TaskNotFoundError(f"Task {task_id} was not found. Please run detection first.")

    graph = build_graph()
    state = _prepare_followup_state(previous_state, question=question)
    result_dict = await _run_with_suspend(graph, state)

    needs_suspend = result_dict.get("needs_user_input") and not result_dict.get("user_reply")
    if needs_suspend:
        _checkpoint_store.save(result_dict)
        ctx = result_dict.get("context", {})
        return {
            "status": "pending",
            "task_id": task_id,
            "message": "Additional user clarification is required before continuing.",
            "pending_clarification": ctx.get("pending_clarification"),
            "pending_question": ctx.get("pending_question"),
            "conversation_history": list(result_dict.get("conversation_history", [])),
            "metadata": {
                "logs": list(result_dict.get("logs", [])),
                "loop_count": result_dict.get("loop_count", 0),
                "confidence": result_dict.get("confidence", 0.0),
            },
        }

    _checkpoint_store.save(result_dict)

    answer = result_dict.get("context", {}).get(
        "answer",
        "Sorry, an error occurred while generating the answer. Please try again.",
    )
    anomalies = _extract_anomalies(result_dict.get("result"))
    return {
        "task_id": task_id,
        "status": "success",
        "answer": answer,
        "anomalies": anomalies,
        "conversation_history": list(result_dict.get("conversation_history", [])),
        "metadata": {
            "logs": list(result_dict.get("logs", [])),
            "loop_count": result_dict.get("loop_count", 0),
            "confidence": result_dict.get("confidence", 0.0),
        },
    }


async def generate_report(task_id: str) -> dict[str, Any]:
    """Generate a full report directly from an existing task state."""
    previous_state = _checkpoint_store.load(task_id)
    if previous_state is None:
        raise TaskNotFoundError(f"Task {task_id} was not found. Please run detection first.")

    state = _restore_state(previous_state)

    if not state.result:
        from app.schemas.detection import DetectionResult

        state.result = DetectionResult(
            task_id=task_id,
            status="success",
            anomalies=[],
            summary="No obvious anomaly was found.",
        )

    state.report_requested = True
    state.stage = "report"

    from app.core import _summarize_node

    state = await _summarize_node(state)
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
    """Continue a suspended task after the user provides clarification."""
    previous_state = _checkpoint_store.load(task_id)
    if previous_state is None:
        raise TaskNotFoundError(f"Suspended task not found: {task_id}")

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
            "message": "More user clarification is still required.",
            "pending_clarification": ctx.get("pending_clarification"),
            "pending_question": ctx.get("pending_question"),
            "loop_count": result_dict.get("loop_count", 0),
            "conversation_history": list(result_dict.get("conversation_history", [])),
        }

    _checkpoint_store.save(result_dict)
    answer = result_dict.get("context", {}).get("answer", "")
    anomalies = _extract_anomalies(result_dict.get("result"))
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


async def stream_detection(task: DetectionTask) -> AsyncGenerator[str, None]:
    """Execute detection/chat in streaming mode and emit SSE events."""
    try:
        graph = build_graph()

        previous_state_dict = _checkpoint_store.load(task.task_id)
        if previous_state_dict:
            state = _prepare_followup_state(
                previous_state_dict,
                question=task.question,
                parameters=task.parameters,
            )
        else:
            state = DetectionState(task=task, stage="chat")

        invoke_input = state.model_dump()
        logger.info(f"[stream_detection] START task_id={task.task_id}, is_continue={bool(previous_state_dict)}")

        async for event in graph.astream_events(invoke_input, version="v2"):
            kind = event["event"]
            name = event["name"]

            if kind == "on_chain_start" and name in ["planner", "executor", "consolidate", "answer"]:
                yield f"data: {json.dumps({'type': 'node_start', 'node': name})}\n\n"
            elif kind == "on_chat_model_stream":
                data = event.get("data", {})
                chunk = data.get("chunk")
                content = getattr(chunk, "content", None)
                if content:
                    tags = event.get("tags", [])
                    metadata = event.get("metadata", {})
                    langgraph_node = metadata.get("langgraph_node", "")

                    if "planner_thought" in tags or langgraph_node == "planner":
                        yield f"data: {json.dumps({'type': 'stream', 'subtype': 'thought', 'content': content})}\n\n"
                    elif "final_answer" in tags or langgraph_node == "answer":
                        yield f"data: {json.dumps({'type': 'stream', 'subtype': 'answer', 'content': content})}\n\n"
            elif kind == "on_tool_start":
                yield f"data: {json.dumps({'type': 'tool_start', 'tool': name, 'input': event['data'].get('input')})}\n\n"
            elif kind == "on_tool_end":
                yield f"data: {json.dumps({'type': 'tool_end', 'tool': name, 'output': event['data'].get('output')})}\n\n"
            elif kind == "on_chain_end" and name == "LangGraph":
                final_output = event["data"].get("output")
                if final_output:
                    _checkpoint_store.save(final_output)
                    yield f"data: {json.dumps({'type': 'final_result', 'task_id': task.task_id, 'status': 'success'})}\n\n"

    except Exception as e:
        import traceback

        logger.error(f"[stream_detection] Error: {e}\n{traceback.format_exc()}")
        yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    yield "event: close\ndata: close\n\n"


async def _run_with_suspend(graph, initial_state) -> dict:
    """Run the graph and return the raw dict state result."""
    logger.info("[_run_with_suspend] invoking graph.ainvoke...")

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
