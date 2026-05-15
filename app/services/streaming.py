from __future__ import annotations

import json
import logging
from typing import Any, AsyncGenerator

from app.core.runtime import graph_session, load_state_values, persist_runtime_state
from app.core.wait_user import build_continue_state
from app.exceptions.base import TaskNotFoundError
from app.memory.state import DetectionState
from app.schemas.detection import DetectionTask
from app.services.state_rehydration import (
    build_execution_metadata,
    extract_anomalies,
    extract_pending_context,
    extract_result_metadata,
    prepare_followup_state,
)

logger = logging.getLogger(__name__)


def build_stream_final_payload(task_id: str, final_output: dict[str, Any]) -> dict[str, Any]:
    needs_suspend = final_output.get("needs_user_input") and not final_output.get("user_reply")
    result_obj = final_output.get("result")
    result_status = (
        result_obj.get("status")
        if isinstance(result_obj, dict)
        else getattr(result_obj, "status", None)
    )
    anomalies = extract_anomalies(final_output.get("result"))
    result_metadata = extract_result_metadata(final_output.get("result"))
    context = final_output.get("context", {}) or {}
    pending_clarification, pending_question = extract_pending_context(final_output)

    return {
        "type": "final_result",
        "task_id": task_id,
        "status": "pending" if needs_suspend else (result_status or "success"),
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
            **build_execution_metadata(final_output),
        },
    }


async def stream_langgraph_events(
    graph: Any,
    *,
    task_id: str,
    backend: str,
    config: dict[str, Any],
    invoke_input: Any,
) -> AsyncGenerator[str, None]:
    emitted_execution_events = 0

    def build_execution_snapshot(output: dict[str, Any]) -> dict[str, Any]:
        return {
            "type": "execution_snapshot",
            **build_execution_metadata(output),
        }

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
        elif kind == "on_chain_end" and name in ["supervisor_plan", "supervisor_execute", "supervisor_merge", "wait_user"]:
            output = event.get("data", {}).get("output")
            if isinstance(output, dict):
                yield f"data: {json.dumps(build_execution_snapshot(output))}\n\n"
                execution_events = list(output.get("execution_events", []))
                new_events = execution_events[emitted_execution_events:]
                for item in new_events:
                    yield f"data: {json.dumps({'type': 'execution_event', 'event': item})}\n\n"
                emitted_execution_events += len(new_events)
        elif kind == "on_chain_end" and name == "LangGraph":
            final_output = event["data"].get("output")
            if final_output:
                persist_runtime_state(task_id, final_output, backend=backend)
                final_payload = build_stream_final_payload(
                    task_id,
                    final_output if isinstance(final_output, dict) else {},
                )
                yield f"data: {json.dumps(final_payload)}\n\n"


async def stream_detection(task: DetectionTask) -> AsyncGenerator[str, None]:
    try:
        async with graph_session(task.task_id) as (graph, config, backend):
            previous_state_dict, _ = await load_state_values(task.task_id)
            if previous_state_dict:
                state = prepare_followup_state(
                    previous_state_dict,
                    question=task.question,
                    parameters=task.parameters,
                )
                # A normal follow-up is a new turn on an already-ended graph
                # thread. Passing None would only read the terminal checkpoint
                # back instead of scheduling load_data -> supervisor -> answer.
                invoke_input = state.model_dump()
            else:
                state = DetectionState(task=task, stage="chat")
                invoke_input = state.model_dump()

            logger.info(
                "[stream_detection] START task_id=%s, is_continue=%s, checkpoint_backend=%s",
                task.task_id,
                bool(previous_state_dict),
                backend,
            )
            async for chunk in stream_langgraph_events(
                graph,
                task_id=task.task_id,
                backend=backend,
                config=config,
                invoke_input=invoke_input,
            ):
                yield chunk

    except Exception as exc:
        logger.exception("[stream_detection] Error")
        yield f"data: {json.dumps({'type': 'error', 'message': str(exc)})}\n\n"

    yield "event: close\ndata: close\n\n"


async def stream_continue_detection(task_id: str, user_reply: str) -> AsyncGenerator[str, None]:
    try:
        previous_state, _ = await load_state_values(task_id)
        if previous_state is None:
            raise TaskNotFoundError(f"Suspended task not found: {task_id}")

        continued_state = build_continue_state(task_id, user_reply, previous_state)
        continued_state["needs_user_input"] = False

        async with graph_session(task_id) as (graph, config, backend):
            logger.info("[stream_continue_detection] checkpoint backend=%s", backend)
            await graph.aupdate_state(config, continued_state)
            async for chunk in stream_langgraph_events(
                graph,
                task_id=task_id,
                backend=backend,
                config=config,
                invoke_input=None,
            ):
                yield chunk

    except Exception as exc:
        logger.exception("[stream_continue_detection] Error")
        yield f"data: {json.dumps({'type': 'error', 'message': str(exc)})}\n\n"

    yield "event: close\ndata: close\n\n"
