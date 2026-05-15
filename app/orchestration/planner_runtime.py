from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.agents.factory import get_specialist_agents, get_supervisor_agent
from app.memory.memory_manager import memory_manager
from app.memory.models import ToolContextMemory
from app.memory.state import DetectionState
from app.orchestration.events import append_execution_event
from app.orchestration.step_executor import run_supervisor_step

logger = logging.getLogger(__name__)


def _step_number(step_id: str, attempt: int) -> int:
    suffix = step_id.rsplit("-", 1)[-1]
    try:
        return int(suffix)
    except ValueError:
        return attempt


def get_ready_steps(
    planned_steps: list[dict[str, Any]],
    successful_step_ids: set[str],
    terminal_step_ids: set[str],
) -> list[dict[str, Any]]:
    ready_steps: list[dict[str, Any]] = []
    for step in planned_steps:
        step_id = step["id"]
        if step_id in terminal_step_ids:
            continue
        depends_on = step.get("depends_on") or []
        if all(dep in successful_step_ids for dep in depends_on):
            ready_steps.append(step)
    return ready_steps


async def supervisor_plan_node(state: DetectionState) -> DetectionState:
    supervisor = get_supervisor_agent()
    execution_plan = supervisor.plan(state)
    orchestration = state.orchestration_runtime()
    orchestration.execution_plan = execution_plan.model_dump()
    state.apply_orchestration_runtime(orchestration)
    planned_agents = [step.agent for step in execution_plan.steps]
    state.context["planned_agents"] = planned_agents
    state.context["execution_plan"] = orchestration.execution_plan
    if execution_plan.reason:
        state.context["supervisor_reason"] = execution_plan.reason
    append_execution_event(
        state,
        "plan_created",
        planned_agents=planned_agents,
        step_count=len(execution_plan.steps),
        reason=execution_plan.reason,
    )
    orchestration.execution_events = list(state.execution_events)
    state.apply_orchestration_runtime(orchestration)
    state.logs.append(f"[Supervisor] Planned agents: {planned_agents or ['answer']}")
    return state


async def supervisor_execute_node(state: DetectionState) -> DetectionState:
    orchestration = state.orchestration_runtime()
    execution_plan = orchestration.execution_plan or {}
    planned_steps: list[dict[str, Any]] = list(execution_plan.get("steps") or [])
    agents = get_specialist_agents()

    if not planned_steps:
        state.logs.append("[Supervisor] No specialist agents were planned")
        return state

    orchestration.loop_count += 1
    state.apply_orchestration_runtime(orchestration)

    current_step_ids = {step["id"] for step in planned_steps}
    successful_step_ids = {
        step_id
        for step_id, status in orchestration.step_status.items()
        if step_id in current_step_ids and status == "success"
    }
    terminal_step_ids = {
        step_id
        for step_id, status in orchestration.step_status.items()
        if step_id in current_step_ids and status in {"success", "failed"}
    }

    while len(terminal_step_ids) < len(planned_steps):
        ready_steps = get_ready_steps(planned_steps, successful_step_ids, terminal_step_ids)
        if not ready_steps:
            remaining_steps = [step for step in planned_steps if step["id"] not in terminal_step_ids]
            blocked_steps = [
                step
                for step in remaining_steps
                if any(dep in terminal_step_ids and dep not in successful_step_ids for dep in (step.get("depends_on") or []))
            ]
            if blocked_steps:
                for step in blocked_steps:
                    step_id = step["id"]
                    failed_dependencies = [
                        dep for dep in (step.get("depends_on") or []) if dep in terminal_step_ids and dep not in successful_step_ids
                    ]
                    orchestration.step_status[step_id] = "failed"
                    orchestration.last_failed_step = failed_dependencies[-1] if failed_dependencies else step_id
                    append_execution_event(
                        state,
                        "step_failed",
                        step_id=step_id,
                        agent=step["agent"],
                        error=f"dependency_failed:{','.join(failed_dependencies)}",
                    )
                    terminal_step_ids.add(step_id)
                orchestration.execution_events = list(state.execution_events)
                state.apply_orchestration_runtime(orchestration)
                continue
            state.errors.append("supervisor_deadlock: no dependency-ready steps available")
            state.logs.append("[Supervisor] Deadlock detected while resolving execution plan dependencies")
            break

        for step in ready_steps:
            step_id = step["id"]
            agent_name = step["agent"]
            orchestration.active_agent = agent_name
            orchestration.step_status[step_id] = "running"
            attempt = orchestration.step_attempts.get(agent_name, 0) + 1
            append_execution_event(
                state,
                "step_started",
                step_id=step_id,
                agent=agent_name,
                attempt=attempt,
                depends_on=list(step.get("depends_on") or []),
            )
            state.logs.append(f"[Supervisor] Running agent: {agent_name} (step={step_id}, attempt={attempt})")
            orchestration.execution_events = list(state.execution_events)
        state.apply_orchestration_runtime(orchestration)

        batch_results = await asyncio.gather(
            *[run_supervisor_step(state, step, agents=agents) for step in ready_steps],
            return_exceptions=True,
        )

        for step, outcome in zip(ready_steps, batch_results):
            step_id = step["id"]
            agent_name = step["agent"]

            if isinstance(outcome, Exception):
                orchestration.step_status[step_id] = "failed"
                orchestration.last_failed_step = step_id
                state.errors.append(f"{agent_name}_failed: {outcome}")
                append_execution_event(
                    state,
                    "step_failed",
                    step_id=step_id,
                    agent=agent_name,
                    error=str(outcome),
                )
                orchestration.execution_events = list(state.execution_events)
                state.apply_orchestration_runtime(orchestration)
                state.logs.append(f"[Supervisor] Agent failed: {agent_name} (step={step_id})")
                terminal_step_ids.add(step_id)
                continue

            _, _, attempt, envelope, error = outcome
            orchestration.step_attempts[agent_name] = attempt

            if error is not None or envelope is None:
                orchestration.step_status[step_id] = "failed"
                orchestration.last_failed_step = step_id
                state.errors.append(f"{agent_name}_failed: {error}")
                append_execution_event(
                    state,
                    "step_failed",
                    step_id=step_id,
                    agent=agent_name,
                    error=str(error),
                )
                orchestration.execution_events = list(state.execution_events)
                state.apply_orchestration_runtime(orchestration)
                state.logs.append(f"[Supervisor] Agent failed: {agent_name} (step={step_id})")
                terminal_step_ids.add(step_id)
                continue

            orchestration.step_outputs[step_id] = envelope.model_dump()
            memory_manager.add_tool_context(
                ToolContextMemory(
                    task_id=state.task.task_id,
                    step_id=_step_number(step_id, attempt),
                    asset_id=state.task.asset_id,
                    tool_name=f"{agent_name}_agent",
                    tool_input={
                        "goal": step.get("goal"),
                        "depends_on": list(step.get("depends_on") or []),
                        "agent": agent_name,
                        "attempt": attempt,
                    },
                    tool_output={
                        "status": envelope.status,
                        "summary": envelope.summary,
                        "anomaly_count": len((envelope.payload or {}).get("anomalies", []))
                        if isinstance(envelope.payload, dict)
                        else 0,
                        "confidence": envelope.confidence,
                    },
                )
            )
            if envelope.status != "success":
                orchestration.step_status[step_id] = "failed"
                orchestration.last_failed_step = step_id
                append_execution_event(
                    state,
                    "step_failed",
                    step_id=step_id,
                    agent=agent_name,
                    attempt=attempt,
                    error=envelope.summary or "agent returned failed status",
                )
                orchestration.execution_events = list(state.execution_events)
                domain = state.domain_runtime()
                domain.agent_trace.append(
                    {
                        "step_id": step_id,
                        "agent": agent_name,
                        "attempt": attempt,
                        "status": "failed",
                        "summary": envelope.summary,
                        "confidence": envelope.confidence,
                        "requires_human": envelope.requires_human,
                        "next_recommendation": envelope.next_recommendation,
                    }
                )
                state.apply_domain_runtime(domain)
                state.apply_orchestration_runtime(orchestration)
                terminal_step_ids.add(step_id)
                state.logs.append(f"[Supervisor] Agent reported failed status: {agent_name} (step={step_id})")
                continue

            domain = state.domain_runtime()
            domain.agent_outputs[agent_name] = envelope.model_dump()
            state.apply_domain_runtime(domain)
            orchestration.step_status[step_id] = "success"
            failed_step_agent = (
                orchestration.last_failed_step.split("-", 1)[0]
                if orchestration.last_failed_step
                else None
            )
            if orchestration.last_failed_step == step_id or failed_step_agent == agent_name:
                orchestration.last_failed_step = None
                orchestration.retry_target = None
                orchestration.retry_reason = None
                orchestration.retry_strategy = None
                orchestration.reflection_decision = None
            append_execution_event(
                state,
                "step_completed",
                step_id=step_id,
                agent=agent_name,
                attempt=attempt,
                status=envelope.status,
                confidence=envelope.confidence,
                requires_human=envelope.requires_human,
            )
            orchestration.execution_events = list(state.execution_events)
            domain = state.domain_runtime()
            domain.agent_trace.append(
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
            state.apply_domain_runtime(domain)
            state.apply_orchestration_runtime(orchestration)
            successful_step_ids.add(step_id)
            terminal_step_ids.add(step_id)

    orchestration.active_agent = None
    state.apply_orchestration_runtime(orchestration)
    return state
