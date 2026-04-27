from __future__ import annotations

import asyncio
import logging

from app.agents.factory import get_specialist_agents, get_supervisor_agent
from app.memory.state import DetectionState
from app.schemas.detection import DetectionResult

logger = logging.getLogger(__name__)


def _ensure_result(state: DetectionState) -> DetectionResult:
    if state.result is None:
        state.result = DetectionResult(task_id=state.task.task_id, status="success")
    return state.result


def _append_execution_event(state: DetectionState, event_type: str, **payload: object) -> None:
    event = {"type": event_type, **payload}
    state.execution_events.append(event)


def _merge_vision_output(state: DetectionState, payload: dict, result: DetectionResult) -> None:
    state.tool_outputs.append({"tool": "vision_agent", "anomalies": payload.get("anomalies", [])})
    state.shared_context["vision"] = payload
    result.anomalies = list(payload.get("anomalies", []))
    if payload.get("answer"):
        result.answer = payload["answer"]
    if payload.get("metadata"):
        result.metadata.update(payload["metadata"])


def _merge_knowledge_output(state: DetectionState, payload: dict, result: DetectionResult) -> None:
    del result  # unused for now, kept for a stable adapter signature
    state.shared_context["knowledge"] = payload
    state.context["rag_context"] = payload.get("prompt_context", state.context.get("rag_context"))


def _merge_clarification_output(state: DetectionState, payload: dict, result: DetectionResult) -> None:
    del result  # unused for now, kept for a stable adapter signature
    state.shared_context["clarification"] = payload
    state.context["pending_clarification"] = payload.get("pending_clarification")
    state.context["pending_question"] = payload.get("pending_question")
    state.unknown_anomaly_types = payload.get("unknown_anomaly_types", state.unknown_anomaly_types)
    state.needs_user_input = bool(payload.get("requires_human", True))


def _merge_report_output(state: DetectionState, payload: dict, result: DetectionResult) -> None:
    state.shared_context["report"] = payload
    result.summary = payload.get("summary", result.summary)
    if payload.get("metadata"):
        result.metadata.update(payload["metadata"])


MERGE_ADAPTERS = {
    "vision": _merge_vision_output,
    "knowledge": _merge_knowledge_output,
    "clarification": _merge_clarification_output,
    "report": _merge_report_output,
}


def _get_ready_steps(planned_steps: list[dict], completed_step_ids: set[str]) -> list[dict]:
    ready_steps: list[dict] = []
    for step in planned_steps:
        step_id = step["id"]
        if step_id in completed_step_ids:
            continue
        depends_on = step.get("depends_on") or []
        if all(dep in completed_step_ids for dep in depends_on):
            ready_steps.append(step)
    return ready_steps


async def _run_supervisor_step(
    state: DetectionState,
    step: dict,
    *,
    agents: dict[str, object],
) -> tuple[str, str, int, object | None, Exception | None]:
    step_id = step["id"]
    agent_name = step["agent"]
    agent = agents.get(agent_name)
    if agent is None:
        return step_id, agent_name, 0, None, RuntimeError(f"Unknown agent: {agent_name}")

    attempt = state.step_attempts.get(agent_name, 0) + 1

    if agent_name in {"report", "clarification"}:
        envelope = await agent.run(state)  # type: ignore[attr-defined]
    elif agent_name == "knowledge":
        anomalies = (state.shared_context.vision.anomalies if state.shared_context.vision else [])
        if not anomalies:
            anomalies = state.agent_outputs.get("vision", {}).get("payload", {}).get("anomalies", [])
        envelope = await agent.run(state.task, anomalies=anomalies)  # type: ignore[attr-defined]
    else:
        envelope = await agent.run(state.task)  # type: ignore[attr-defined]

    return step_id, agent_name, attempt, envelope, None


async def supervisor_plan_node(state: DetectionState) -> DetectionState:
    supervisor = get_supervisor_agent()
    execution_plan = supervisor.plan(state)
    state.execution_plan = execution_plan.model_dump()
    planned_agents = [step.agent for step in execution_plan.steps]
    state.context["planned_agents"] = planned_agents
    state.context["execution_plan"] = state.execution_plan
    if execution_plan.reason:
        state.context["supervisor_reason"] = execution_plan.reason
    _append_execution_event(
        state,
        "plan_created",
        planned_agents=planned_agents,
        step_count=len(execution_plan.steps),
        reason=execution_plan.reason,
    )
    state.logs.append(f"[Supervisor] Planned agents: {planned_agents or ['answer']}")
    return state


async def supervisor_execute_node(state: DetectionState) -> DetectionState:
    execution_plan = state.execution_plan or {}
    planned_steps: list[dict] = list(execution_plan.get("steps") or [])
    agents = get_specialist_agents()

    if not planned_steps:
        state.logs.append("[Supervisor] No specialist agents were planned")
        return state

    state.loop_count += 1

    completed_step_ids = {step_id for step_id, status in state.step_status.items() if status in {"success", "failed"}}

    while len(completed_step_ids) < len(planned_steps):
        ready_steps = _get_ready_steps(planned_steps, completed_step_ids)
        if not ready_steps:
            state.errors.append("supervisor_deadlock: no dependency-ready steps available")
            state.logs.append("[Supervisor] Deadlock detected while resolving execution plan dependencies")
            break

        for step in ready_steps:
            step_id = step["id"]
            agent_name = step["agent"]
            state.active_agent = agent_name
            state.step_status[step_id] = "running"
            attempt = state.step_attempts.get(agent_name, 0) + 1
            _append_execution_event(
                state,
                "step_started",
                step_id=step_id,
                agent=agent_name,
                attempt=attempt,
                depends_on=list(step.get("depends_on") or []),
            )
            state.logs.append(
                f"[Supervisor] Running agent: {agent_name} (step={step_id}, attempt={attempt})"
            )

        batch_results = await asyncio.gather(
            *[_run_supervisor_step(state, step, agents=agents) for step in ready_steps],
            return_exceptions=True,
        )

        for step, outcome in zip(ready_steps, batch_results):
            step_id = step["id"]
            agent_name = step["agent"]

            if isinstance(outcome, Exception):
                state.step_status[step_id] = "failed"
                state.last_failed_step = step_id
                state.errors.append(f"{agent_name}_failed: {outcome}")
                _append_execution_event(
                    state,
                    "step_failed",
                    step_id=step_id,
                    agent=agent_name,
                    error=str(outcome),
                )
                state.logs.append(f"[Supervisor] Agent failed: {agent_name} (step={step_id})")
                completed_step_ids.add(step_id)
                continue

            _, _, attempt, envelope, error = outcome
            state.step_attempts[agent_name] = attempt

            if error is not None or envelope is None:
                state.step_status[step_id] = "failed"
                state.last_failed_step = step_id
                state.errors.append(f"{agent_name}_failed: {error}")
                _append_execution_event(
                    state,
                    "step_failed",
                    step_id=step_id,
                    agent=agent_name,
                    error=str(error),
                )
                state.logs.append(f"[Supervisor] Agent failed: {agent_name} (step={step_id})")
                completed_step_ids.add(step_id)
                continue

            state.agent_outputs[agent_name] = envelope.model_dump()
            state.step_outputs[step_id] = envelope.model_dump()
            state.step_status[step_id] = envelope.status
            _append_execution_event(
                state,
                "step_completed",
                step_id=step_id,
                agent=agent_name,
                attempt=attempt,
                status=envelope.status,
                confidence=envelope.confidence,
                requires_human=envelope.requires_human,
            )
            state.agent_trace.append(
                {
                    "step_id": step_id,
                    "agent": agent_name,
                    "attempt": attempt,
                    "status": envelope.status,
                    "summary": envelope.summary,
                    "confidence": envelope.confidence,
                    "requires_human": envelope.requires_human,
                    "next_recommendation": envelope.next_recommendation,
                }
            )
            completed_step_ids.add(step_id)

    state.active_agent = None
    return state


async def supervisor_merge_node(state: DetectionState) -> DetectionState:
    result = _ensure_result(state)
    for agent_name, merge_adapter in MERGE_ADAPTERS.items():
        output = state.agent_outputs.get(agent_name) or {}
        if not output:
            continue
        payload = output.get("payload", {})
        merge_adapter(state, payload, result)

    state.context["agent_trace"] = list(state.agent_trace)
    state.context["step_status"] = dict(state.step_status)
    state.context["step_attempts"] = dict(state.step_attempts)
    state.context["execution_events"] = list(state.execution_events)
    state.logs.append(f"[Supervisor] Merge complete, agent outputs={list(state.agent_outputs.keys())}")
    return state
