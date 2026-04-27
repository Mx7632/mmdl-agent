from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.agents.factory import get_specialist_agents, get_supervisor_agent
from app.memory.state import DetectionState
from app.orchestration.events import append_execution_event
from app.orchestration.step_executor import run_supervisor_step

logger = logging.getLogger(__name__)


def get_ready_steps(planned_steps: list[dict[str, Any]], completed_step_ids: set[str]) -> list[dict[str, Any]]:
    ready_steps: list[dict[str, Any]] = []
    for step in planned_steps:
        step_id = step["id"]
        if step_id in completed_step_ids:
            continue
        depends_on = step.get("depends_on") or []
        if all(dep in completed_step_ids for dep in depends_on):
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

    completed_step_ids = {
        step_id for step_id, status in orchestration.step_status.items() if status in {"success", "failed"}
    }

    while len(completed_step_ids) < len(planned_steps):
        ready_steps = get_ready_steps(planned_steps, completed_step_ids)
        if not ready_steps:
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
                completed_step_ids.add(step_id)
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
                completed_step_ids.add(step_id)
                continue

            domain = state.domain_runtime()
            domain.agent_outputs[agent_name] = envelope.model_dump()
            state.apply_domain_runtime(domain)
            orchestration.step_outputs[step_id] = envelope.model_dump()
            orchestration.step_status[step_id] = envelope.status
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
            completed_step_ids.add(step_id)

    orchestration.active_agent = None
    state.apply_orchestration_runtime(orchestration)
    return state
