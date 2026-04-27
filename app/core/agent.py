"""
Agent execution entrypoints.

This module wraps LangGraph workflow execution, checkpoint recovery, and
multi-turn conversation orchestration.
"""

from __future__ import annotations

import json
import logging
from typing import Any, AsyncGenerator, Optional

from app.agents.report.service import generate_report_state
from app.core import build_graph
from app.core.runtime import graph_session, load_state_values, persist_runtime_state
from app.core.wait_user import build_continue_state
from app.exceptions.base import AppError, TaskNotFoundError
from app.memory.state import DetectionState
from app.schemas.detection import DetectionTask

logger = logging.getLogger(__name__)


def _build_execution_metadata(state_dict: dict[str, Any]) -> dict[str, Any]:
    return {
        "agent_trace": list(state_dict.get("agent_trace", [])),
        "execution_plan": state_dict.get("execution_plan"),
        "step_status": dict(state_dict.get("step_status", {})),
        "step_attempts": dict(state_dict.get("step_attempts", {})),
        "execution_events": list(state_dict.get("execution_events", [])),
    }


def _build_stream_final_payload(task_id: str, final_output: dict[str, Any]) -> dict[str, Any]:
    needs_suspend = final_output.get("needs_user_input") and not final_output.get("user_reply")
    anomalies = _extract_anomalies(final_output.get("result"))
    result_metadata = _extract_result_metadata(final_output.get("result"))
    context = final_output.get("context", {}) or {}
    pending_clarification, pending_question = _extract_pending_context(final_output)

    payload = {
        "type": "final_result",
        "task_id": task_id,
        "status": "pending" if needs_suspend else "success",
        "answer": context.get("answer", ""),
        "anomalies": anomalies,
        "summary": final_output.get("result", {}).get("summary") if isinstance(final_output.get("result"), dict) else getattr(final_output.get("result"), "summary", None),
        "pending_clarification": pending_clarification,
        "pending_question": pending_question,
        "metadata": {
            "logs": list(final_output.get("logs", [])),
            "loop_count": final_output.get("loop_count", 0),
            "confidence": final_output.get("confidence", 0.0),
            "result_metadata": result_metadata,
            **_build_execution_metadata(final_output),
        },
    }
    return payload


def _extract_pending_context(state_dict: dict[str, Any]) -> tuple[str | None, str | None]:
    ctx = state_dict.get("context", {}) or {}
    shared_context = state_dict.get("shared_context", {}) or {}
    clarification = shared_context.get("clarification", {}) if isinstance(shared_context, dict) else {}
    pending_clarification = clarification.get("pending_clarification") or ctx.get("pending_clarification")
    pending_question = clarification.get("pending_question") or ctx.get("pending_question")
    return pending_clarification, pending_question


async def get_pending_task(task_id: str) -> Optional[dict]:
    """Return the pending clarification payload for a suspended task."""
    state, _ = await load_state_values(task_id)
    if state is None:
        return None
    if not state.get("needs_user_input", False):
        return None
    pending_clarification, pending_question = _extract_pending_context(state)
    return {
        "task_id": task_id,
        "pending_clarification": pending_clarification,
        "pending_question": pending_question,
        "conversation_history": list(state.get("conversation_history", [])),
        "loop_count": state.get("loop_count", 0),
        **_build_execution_metadata(state),
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


def _extract_result_metadata(result_obj: Any) -> dict[str, Any]:
    """Extract result metadata from either a dict result or a Pydantic model."""
    if result_obj is None:
        return {}
    if isinstance(result_obj, dict):
        return result_obj.get("metadata", {}) or {}
    if hasattr(result_obj, "metadata"):
        return result_obj.metadata or {}
    return {}


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
    state.agent_outputs = {}
    state.agent_trace = []
    state.active_agent = None
    from app.orchestration import SharedContext

    state.shared_context = SharedContext()
    state.execution_plan = None
    state.step_status = {}
    state.step_attempts = {}
    state.step_outputs = {}
    state.execution_events = []
    state.last_failed_step = None
    state.loop_count = 0
    state.reflection_decision = None
    state.retry_target = None
    state.retry_reason = None
    state.retry_strategy = None
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
        state = DetectionState(task=task, stage="chat")
        async with graph_session(task.task_id) as (graph, config, backend):
            logger.info("[run_detection] checkpoint backend=%s", backend)
            logger.info("[run_detection] calling _run_with_suspend...")
            result_dict = await _run_with_suspend(graph, state, config=config)
            persist_runtime_state(task.task_id, result_dict, backend=backend)
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
        pending_clarification, pending_question = _extract_pending_context(result_dict)
        return {
            "status": "pending",
            "task_id": task.task_id,
            "message": "Additional user clarification is required before continuing.",
            "pending_clarification": pending_clarification,
            "pending_question": pending_question,
            "loop_count": result_dict.get("loop_count", 0),
            "conversation_history": list(result_dict.get("conversation_history", [])),
            **_build_execution_metadata(result_dict),
        }

    answer = result_dict.get("context", {}).get(
        "answer",
        "An anomaly was detected. You can continue asking questions or generate a report.",
    )
    anomalies = _extract_anomalies(result_dict.get("result"))
    result_metadata = _extract_result_metadata(result_dict.get("result"))

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
            "result_metadata": result_metadata,
            **_build_execution_metadata(result_dict),
        },
        }


async def run_chat(task_id: str, question: str) -> dict[str, Any]:
    """
    Execute a new multi-turn question by re-entering the agent graph.

    Each follow-up turn is treated as a fresh agent run, so planner/executor can
    re-plan retrieval and tool usage in ReAct style.
    """
    previous_state, _ = await load_state_values(task_id)
    if previous_state is None:
        raise TaskNotFoundError(f"Task {task_id} was not found. Please run detection first.")

    state = _prepare_followup_state(previous_state, question=question)
    async with graph_session(task_id) as (graph, config, backend):
        logger.info("[run_chat] checkpoint backend=%s", backend)
        await graph.aupdate_state(config, state.model_dump())
        result_dict = await _run_with_suspend(graph, None, config=config)
        persist_runtime_state(task_id, result_dict, backend=backend)

    needs_suspend = result_dict.get("needs_user_input") and not result_dict.get("user_reply")
    if needs_suspend:
        pending_clarification, pending_question = _extract_pending_context(result_dict)
        return {
            "status": "pending",
            "task_id": task_id,
            "message": "Additional user clarification is required before continuing.",
            "pending_clarification": pending_clarification,
            "pending_question": pending_question,
            "conversation_history": list(result_dict.get("conversation_history", [])),
            "metadata": {
                "logs": list(result_dict.get("logs", [])),
                "loop_count": result_dict.get("loop_count", 0),
                "confidence": result_dict.get("confidence", 0.0),
                **_build_execution_metadata(result_dict),
            },
        }

    answer = result_dict.get("context", {}).get(
        "answer",
        "Sorry, an error occurred while generating the answer. Please try again.",
    )
    anomalies = _extract_anomalies(result_dict.get("result"))
    result_metadata = _extract_result_metadata(result_dict.get("result"))
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
            "result_metadata": result_metadata,
            **_build_execution_metadata(result_dict),
        },
    }


async def generate_report(task_id: str) -> dict[str, Any]:
    """Generate a full report directly from an existing task state."""
    previous_state, _ = await load_state_values(task_id)
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

    state = await generate_report_state(state)
    async with graph_session(task_id) as (graph, config, backend):
        await graph.aupdate_state(config, state.model_dump())
        persist_runtime_state(task_id, state.model_dump(), backend=backend)

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
            "result_metadata": result.metadata if result else {},
            **_build_execution_metadata(state.model_dump()),
        },
    }


async def continue_detection(task_id: str, user_reply: str) -> dict[str, Any]:
    """Continue a suspended task after the user provides clarification."""
    previous_state, _ = await load_state_values(task_id)
    if previous_state is None:
        raise TaskNotFoundError(f"Suspended task not found: {task_id}")

    continued_state = build_continue_state(task_id, user_reply, previous_state)
    continued_state["needs_user_input"] = False

    async with graph_session(task_id) as (graph, config, backend):
        logger.info("[continue_detection] checkpoint backend=%s", backend)
        await graph.aupdate_state(config, continued_state)
        result_dict = await _run_with_suspend(graph, None, config=config)
        persist_runtime_state(task_id, result_dict, backend=backend)

    needs_suspend = result_dict.get("needs_user_input") and not result_dict.get("user_reply")
    if needs_suspend:
        pending_clarification, pending_question = _extract_pending_context(result_dict)
        return {
            "status": "pending",
            "task_id": task_id,
            "message": "More user clarification is still required.",
            "pending_clarification": pending_clarification,
            "pending_question": pending_question,
            "loop_count": result_dict.get("loop_count", 0),
            "conversation_history": list(result_dict.get("conversation_history", [])),
            **_build_execution_metadata(result_dict),
        }

    answer = result_dict.get("context", {}).get("answer", "")
    anomalies = _extract_anomalies(result_dict.get("result"))
    result_metadata = _extract_result_metadata(result_dict.get("result"))
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
            "result_metadata": result_metadata,
            **_build_execution_metadata(result_dict),
        },
    }


async def _stream_langgraph_events(
    graph,
    *,
    task_id: str,
    backend: str,
    config: dict[str, Any],
    invoke_input: Any,
) -> AsyncGenerator[str, None]:
    emitted_execution_events = 0

    async for event in graph.astream_events(invoke_input, config=config, version="v2"):
        kind = event["event"]
        name = event["name"]

        if kind == "on_chain_start" and name in [
            "supervisor_plan",
            "supervisor_execute",
            "supervisor_merge",
            "self_reflect",
            "wait_user",
            "answer",
            "report",
        ]:
            yield f"data: {json.dumps({'type': 'node_start', 'node': name})}\n\n"
        elif kind == "on_chat_model_stream":
            data = event.get("data", {})
            chunk = data.get("chunk")
            content = getattr(chunk, "content", None)
            if content:
                tags = event.get("tags", [])
                metadata = event.get("metadata", {})
                langgraph_node = metadata.get("langgraph_node", "")

                if "planner_thought" in tags or langgraph_node == "supervisor_plan":
                    yield f"data: {json.dumps({'type': 'stream', 'subtype': 'thought', 'content': content})}\n\n"
                elif "final_answer" in tags or langgraph_node == "answer":
                    yield f"data: {json.dumps({'type': 'stream', 'subtype': 'answer', 'content': content})}\n\n"
        elif kind == "on_tool_start":
            yield f"data: {json.dumps({'type': 'tool_start', 'tool': name, 'input': event['data'].get('input')})}\n\n"
        elif kind == "on_tool_end":
            yield f"data: {json.dumps({'type': 'tool_end', 'tool': name, 'output': event['data'].get('output')})}\n\n"
        elif kind == "on_chain_end" and name in [
            "supervisor_plan",
            "supervisor_execute",
            "supervisor_merge",
            "wait_user",
        ]:
            output = event.get("data", {}).get("output")
            if isinstance(output, dict):
                execution_events = list(output.get("execution_events", []))
                new_events = execution_events[emitted_execution_events:]
                for item in new_events:
                    yield f"data: {json.dumps({'type': 'execution_event', 'event': item})}\n\n"
                emitted_execution_events += len(new_events)
        elif kind == "on_chain_end" and name == "LangGraph":
            final_output = event["data"].get("output")
            if final_output:
                persist_runtime_state(task_id, final_output, backend=backend)
                final_payload = _build_stream_final_payload(
                    task_id,
                    final_output if isinstance(final_output, dict) else {},
                )
                yield f"data: {json.dumps(final_payload)}\n\n"


async def stream_detection(task: DetectionTask) -> AsyncGenerator[str, None]:
    """Execute detection/chat in streaming mode and emit SSE events."""
    try:
        async with graph_session(task.task_id) as (graph, config, backend):
            previous_state_dict, _ = await load_state_values(task.task_id)
            if previous_state_dict:
                state = _prepare_followup_state(
                    previous_state_dict,
                    question=task.question,
                    parameters=task.parameters,
                )
                await graph.aupdate_state(config, state.model_dump())
                invoke_input = None
            else:
                state = DetectionState(task=task, stage="chat")
                invoke_input = state.model_dump()

            logger.info(
                f"[stream_detection] START task_id={task.task_id}, "
                f"is_continue={bool(previous_state_dict)}, checkpoint_backend={backend}"
            )
            async for chunk in _stream_langgraph_events(
                graph,
                task_id=task.task_id,
                backend=backend,
                config=config,
                invoke_input=invoke_input,
            ):
                yield chunk

    except Exception as e:
        import traceback

        logger.error(f"[stream_detection] Error: {e}\n{traceback.format_exc()}")
        yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    yield "event: close\ndata: close\n\n"


async def stream_continue_detection(task_id: str, user_reply: str) -> AsyncGenerator[str, None]:
    """Continue a suspended task in streaming mode after the user provides clarification."""
    try:
        previous_state, _ = await load_state_values(task_id)
        if previous_state is None:
            raise TaskNotFoundError(f"Suspended task not found: {task_id}")

        continued_state = build_continue_state(task_id, user_reply, previous_state)
        continued_state["needs_user_input"] = False

        async with graph_session(task_id) as (graph, config, backend):
            logger.info("[stream_continue_detection] checkpoint backend=%s", backend)
            await graph.aupdate_state(config, continued_state)
            async for chunk in _stream_langgraph_events(
                graph,
                task_id=task_id,
                backend=backend,
                config=config,
                invoke_input=None,
            ):
                yield chunk

    except Exception as e:
        import traceback

        logger.error(f"[stream_continue_detection] Error: {e}\n{traceback.format_exc()}")
        yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    yield "event: close\ndata: close\n\n"


async def _run_with_suspend(graph, initial_state, *, config: Optional[dict[str, Any]] = None) -> dict:
    """Run the graph and return the raw dict state result."""
    logger.info("[_run_with_suspend] invoking graph.ainvoke...")

    if isinstance(initial_state, DetectionState):
        invoke_input = initial_state.model_dump()
    else:
        invoke_input = initial_state

    result_dict: dict = await graph.ainvoke(invoke_input, config=config)
    logger.info(
        f"[_run_with_suspend] invoke returned, "
        f"keys={list(result_dict.keys()) if isinstance(result_dict, dict) else type(result_dict)}"
    )
    ctx = result_dict.get("context", {}) if isinstance(result_dict, dict) else {}
    answer_preview = ctx.get("answer", "")[:80] if ctx.get("answer") else "EMPTY"
    logger.info(f"[_run_with_suspend] answer from dict={repr(answer_preview)}")

    return result_dict
