from __future__ import annotations

from typing import Any

from app.memory.state import DetectionState


async def run_supervisor_step(
    state: DetectionState,
    step: dict[str, Any],
    *,
    agents: dict[str, object],
) -> tuple[str, str, int, object | None, Exception | None]:
    step_id = step["id"]
    agent_name = step["agent"]
    orchestration = state.orchestration_runtime()
    domain = state.domain_runtime()
    task = state.task_runtime().task
    agent = agents.get(agent_name)
    if agent is None:
        return step_id, agent_name, 0, None, RuntimeError(f"Unknown agent: {agent_name}")

    attempt = orchestration.step_attempts.get(agent_name, 0) + 1

    if agent_name in {"report", "clarification"}:
        envelope = await agent.run(state)  # type: ignore[attr-defined]
    elif agent_name == "knowledge":
        anomalies = (domain.shared_context.vision.anomalies if domain.shared_context.vision else [])
        if not anomalies:
            anomalies = domain.agent_outputs.get("vision", {}).get("payload", {}).get("anomalies", [])
        envelope = await agent.run(task, anomalies=anomalies)  # type: ignore[attr-defined]
    else:
        envelope = await agent.run(task)  # type: ignore[attr-defined]

    return step_id, agent_name, attempt, envelope, None
