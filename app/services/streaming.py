from __future__ import annotations

import json
import logging
from typing import Any, AsyncGenerator

from app.core.runtime import graph_session, load_state_values, persist_runtime_state
from app.core.wait_user import build_continue_state
from app.exceptions.base import TaskNotFoundError
from app.memory.state import DetectionState
from app.schemas.detection import DetectionTask
from app.services.industrial_runtime import industrial_store
from app.services.state_rehydration import (
    build_execution_metadata,
    extract_anomalies,
    extract_pending_context,
    extract_result_metadata,
    prepare_followup_state,
)

logger = logging.getLogger(__name__)


def _persist_task_record(task_id: str, final_payload: dict[str, Any], final_output: dict[str, Any]) -> None:
    """Fire-and-forget: save detection result to industrial_store for /v1/tasks listing."""
    try:
        meta = final_payload.get("metadata", {}) or {}
        anomalies = final_payload.get("anomalies") or []
        is_anomaly = bool(anomalies)
        score = float(meta.get("confidence", 0) or 0)
        # Build conversation history: merge with existing store data to avoid losing previous turns
        new_conv = list(final_output.get("conversation_history", []))
        try:
            from app.services.industrial_runtime import get_industrial_store
            existing_task = get_industrial_store().get_task(task_id)
            if existing_task and existing_task.get("result", {}).get("conversation_history"):
                old_conv = existing_task["result"]["conversation_history"]
                # Keep old entries not present in new_conv (by content+role dedup)
                old_content_set = {(m.get("role", ""), m.get("content", "")) for m in new_conv}
                for msg in old_conv:
                    key = (msg.get("role", ""), msg.get("content", ""))
                    if key not in old_content_set:
                        new_conv.insert(0, msg)
        except Exception:
            pass

        # Ensure user question is included if missing
        user_question = (
            (final_output.get("task", {}).get("question") if isinstance(final_output.get("task"), dict) else None)
            or getattr(final_output.get("task"), "question", None)
        )
        has_user_msg = any(m.get("role") == "user" for m in new_conv)
        if user_question and not has_user_msg:
            new_conv.insert(0, {"role": "user", "content": user_question})

        # Preserve original question: follow-up updates task.question in LangGraph state,
        # but we must keep the first user question for conversation restoration.
        original_question = user_question
        try:
            if existing_task and existing_task.get("result", {}).get("question"):
                original_question = existing_task["result"]["question"]
        except Exception:
            pass

        result_record = {
            "task_id": task_id,
            "status": final_payload.get("status", "success"),
            "answer": final_payload.get("answer", ""),
            "anomalies": anomalies,
            "is_anomaly": is_anomaly,
            "score": score,
            "defect_type": anomalies[0].get("defect_type", "unknown") if anomalies else "good",
            "metadata": meta,
            "question": original_question,
            "conversation_history": new_conv,
            "execution_events": list(final_output.get("execution_events", [])),
            "execution_plan": final_output.get("execution_plan"),
            "step_status": final_output.get("step_status"),
            "step_attempts": final_output.get("step_attempts"),
        }
        # Extract original image for preview restoration (if available)
        _task_params = {}
        _task_obj_tmp = final_output.get("task")
        if isinstance(_task_obj_tmp, dict):
            _task_params = _task_obj_tmp.get("parameters", {}) or {}
        elif hasattr(_task_obj_tmp, "parameters"):
            _task_params = _task_obj_tmp.parameters or {}
        if _task_params.get("image_base64"):
            result_record["image_base64"] = _task_params["image_base64"]
            result_record["image_mime"] = _task_params.get("image_mime", "image/jpeg")
        # build a lightweight task-like object for record_task
        # extract asset_id from LangGraph state or task sub-object
        _task_obj = final_output.get("task")
        if isinstance(_task_obj, dict):
            _asset_id = _task_obj.get("asset_id", "") or ""
        else:
            _asset_id = getattr(_task_obj, "asset_id", "") or ""
        _asset_id = _asset_id or final_output.get("asset_id") or ""
        class _MinimalTask:
            def __init__(self, tid, aid):
                self.task_id = tid
                self.asset_id = aid
                self.parameters = {}
        industrial_store.record_task(_MinimalTask(task_id, _asset_id), result_record)
        logger.info("[stream] Task %s recorded to industrial_store", task_id)
    except Exception as exc:
        import traceback
        logger.warning("[stream] Failed to record task %s: %s\n%s", task_id, exc, traceback.format_exc())


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
                # Immediately persist to industrial_store when first result is ready
                _persist_task_record(task_id, final_payload, final_output if isinstance(final_output, dict) else {})


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
                # Restore conversation_history from industrial_store when checkpoint is empty
                try:
                    from app.services.industrial_runtime import get_industrial_store
                    store_task = get_industrial_store().get_task(task.task_id)
                    if store_task and store_task.get("result", {}).get("conversation_history"):
                        existing_conv = store_task["result"]["conversation_history"]
                        if task.question:
                            existing_conv.append({"role": "user", "content": task.question})
                        state.task_runtime().conversation_history = existing_conv
                except Exception:
                    pass
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
