from __future__ import annotations

import logging
from typing import Any, Optional

from app.agents.report.service import generate_report_state
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
    restore_state,
)

logger = logging.getLogger(__name__)


async def get_pending_task(task_id: str) -> Optional[dict[str, Any]]:
    state, _ = await load_state_values(task_id)
    if state is None:
        return None
    if not state.get("needs_user_input", False):
        return None
    pending_clarification, pending_question = extract_pending_context(state)
    return {
        "task_id": task_id,
        "pending_clarification": pending_clarification,
        "pending_question": pending_question,
        "conversation_history": list(state.get("conversation_history", [])),
        "loop_count": state.get("loop_count", 0),
        **build_execution_metadata(state),
    }


async def run_detection(task: DetectionTask) -> dict[str, Any]:
    try:
        logger.info("[run_detection] START task_id=%s, question=%s", task.task_id, task.question)
        state = DetectionState(task=task, stage="chat")
        async with graph_session(task.task_id) as (graph, config, backend):
            logger.info("[run_detection] checkpoint backend=%s", backend)
            result_dict = await run_graph(graph, state, config=config)
            persist_runtime_state(task.task_id, result_dict, backend=backend)
    except Exception:
        logger.exception("[run_detection] CRITICAL ERROR")
        raise

    needs_suspend = result_dict.get("needs_user_input") and not result_dict.get("user_reply")
    if needs_suspend:
        pending_clarification, pending_question = extract_pending_context(result_dict)
        return {
            "status": "pending",
            "task_id": task.task_id,
            "message": "Additional user clarification is required before continuing.",
            "pending_clarification": pending_clarification,
            "pending_question": pending_question,
            "loop_count": result_dict.get("loop_count", 0),
            "conversation_history": list(result_dict.get("conversation_history", [])),
            **build_execution_metadata(result_dict),
        }

    answer = result_dict.get("context", {}).get(
        "answer",
        "An anomaly was detected. You can continue asking questions or generate a report.",
    )
    anomalies = extract_anomalies(result_dict.get("result"))
    result_metadata = extract_result_metadata(result_dict.get("result"))

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
            **build_execution_metadata(result_dict),
        },
    }


async def run_chat(task_id: str, question: str) -> dict[str, Any]:
    previous_state, _ = await load_state_values(task_id)
    if previous_state is None:
        raise TaskNotFoundError(f"Task {task_id} was not found. Please run detection first.")

    state = prepare_followup_state(previous_state, question=question)
    async with graph_session(task_id) as (graph, config, backend):
        logger.info("[run_chat] checkpoint backend=%s", backend)
        result_dict = await run_graph(graph, state, config=config)
        persist_runtime_state(task_id, result_dict, backend=backend)

    needs_suspend = result_dict.get("needs_user_input") and not result_dict.get("user_reply")
    if needs_suspend:
        pending_clarification, pending_question = extract_pending_context(result_dict)
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
                **build_execution_metadata(result_dict),
            },
        }

    answer = result_dict.get("context", {}).get(
        "answer",
        "Sorry, an error occurred while generating the answer. Please try again.",
    )
    anomalies = extract_anomalies(result_dict.get("result"))
    result_metadata = extract_result_metadata(result_dict.get("result"))
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
            **build_execution_metadata(result_dict),
        },
    }


async def generate_report(task_id: str) -> dict[str, Any]:
    previous_state, _ = await load_state_values(task_id)
    if previous_state is None:
        raise TaskNotFoundError(f"Task {task_id} was not found. Please run detection first.")

    state = restore_state(previous_state)
    task_runtime = state.task_runtime()
    domain_runtime = state.domain_runtime()

    if not domain_runtime.result:
        from app.schemas.detection import DetectionResult

        domain_runtime.result = DetectionResult(
            task_id=task_id,
            status="success",
            anomalies=[],
            summary="No obvious anomaly was found.",
        )
        state.apply_domain_runtime(domain_runtime)

    task_runtime.report_requested = True
    task_runtime.stage = "report"
    state.apply_task_runtime(task_runtime)

    state = await generate_report_state(state)
    async with graph_session(task_id) as (graph, config, backend):
        await graph.aupdate_state(config, state.model_dump())
        persist_runtime_state(task_id, state.model_dump(), backend=backend)

    task_runtime = state.task_runtime()
    orchestration_runtime = state.orchestration_runtime()
    result = state.domain_runtime().result
    return {
        "task_id": task_id,
        "status": result.status if result else "success",
        "summary": result.summary if result else None,
        "anomalies": result.anomalies if result else [],
        "has_report": True,
        "conversation_history": list(task_runtime.conversation_history),
        "metadata": {
            "logs": list(state.logs),
            "loop_count": orchestration_runtime.loop_count,
            "result_metadata": result.metadata if result else {},
            **build_execution_metadata(state.model_dump()),
        },
    }


async def continue_detection(task_id: str, user_reply: str) -> dict[str, Any]:
    previous_state, _ = await load_state_values(task_id)
    if previous_state is None:
        raise TaskNotFoundError(f"Suspended task not found: {task_id}")

    continued_state = build_continue_state(task_id, user_reply, previous_state)
    continued_state["needs_user_input"] = False

    async with graph_session(task_id) as (graph, config, backend):
        logger.info("[continue_detection] checkpoint backend=%s", backend)
        await graph.aupdate_state(config, continued_state)
        result_dict = await run_graph(graph, None, config=config)
        persist_runtime_state(task_id, result_dict, backend=backend)

    needs_suspend = result_dict.get("needs_user_input") and not result_dict.get("user_reply")
    if needs_suspend:
        pending_clarification, pending_question = extract_pending_context(result_dict)
        return {
            "status": "pending",
            "task_id": task_id,
            "message": "More user clarification is still required.",
            "pending_clarification": pending_clarification,
            "pending_question": pending_question,
            "loop_count": result_dict.get("loop_count", 0),
            "conversation_history": list(result_dict.get("conversation_history", [])),
            **build_execution_metadata(result_dict),
        }

    answer = result_dict.get("context", {}).get("answer", "")
    anomalies = extract_anomalies(result_dict.get("result"))
    result_metadata = extract_result_metadata(result_dict.get("result"))
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
            **build_execution_metadata(result_dict),
        },
    }


async def run_graph(graph: Any, initial_state: DetectionState | dict[str, Any] | None, *, config: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    logger.info("[run_graph] invoking graph.ainvoke...")

    if isinstance(initial_state, DetectionState):
        invoke_input = initial_state.model_dump()
    else:
        invoke_input = initial_state

    result_dict: dict[str, Any] = await graph.ainvoke(invoke_input, config=config)
    logger.info(
        "[run_graph] invoke returned, keys=%s",
        list(result_dict.keys()) if isinstance(result_dict, dict) else type(result_dict),
    )
    return result_dict
