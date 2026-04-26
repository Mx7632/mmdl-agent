from __future__ import annotations

import logging

from app.agents.factory import get_specialist_agents, get_supervisor_agent
from app.memory.state import DetectionState

logger = logging.getLogger(__name__)


async def supervisor_plan_node(state: DetectionState) -> DetectionState:
    """Supervisor decides which specialist agents to invoke next."""
    supervisor = get_supervisor_agent()
    planned_agents = supervisor.plan(state)
    state.context["planned_agents"] = planned_agents
    state.logs.append(f"[Supervisor] Planned agents: {planned_agents or ['answer']}")
    return state


async def supervisor_execute_node(state: DetectionState) -> DetectionState:
    """Execute planned specialist agents and persist their envelopes into shared state."""
    planned_agents: list[str] = list(state.context.get("planned_agents") or [])
    agents = get_specialist_agents()

    if not planned_agents:
        state.logs.append("[Supervisor] No specialist agents were planned")
        return state

    for agent_name in planned_agents:
        agent = agents.get(agent_name)
        if agent is None:
            state.errors.append(f"Unknown agent: {agent_name}")
            continue

        state.active_agent = agent_name
        state.logs.append(f"[Supervisor] Running agent: {agent_name}")

        if agent_name == "report":
            envelope = await agent.run(state)  # type: ignore[attr-defined]
        elif agent_name == "knowledge":
            anomalies = state.agent_outputs.get("vision", {}).get("payload", {}).get("anomalies", [])
            envelope = await agent.run(state.task, anomalies=anomalies)  # type: ignore[attr-defined]
        else:
            envelope = await agent.run(state.task)  # type: ignore[attr-defined]

        state.agent_outputs[agent_name] = envelope.model_dump()
        state.agent_trace.append(
            {
                "agent": agent_name,
                "status": envelope.status,
                "summary": envelope.summary,
                "confidence": envelope.confidence,
            }
        )

    state.active_agent = None
    return state


async def supervisor_merge_node(state: DetectionState) -> DetectionState:
    """Merge specialist agent outputs back into the existing DetectionState shape."""
    vision_output = state.agent_outputs.get("vision") or {}
    report_output = state.agent_outputs.get("report") or {}
    knowledge_output = state.agent_outputs.get("knowledge") or {}

    if vision_output:
        payload = vision_output.get("payload", {})
        state.tool_outputs.append(
            {
                "tool": "vision_agent",
                "anomalies": payload.get("anomalies", []),
            }
        )
        state.shared_context["vision"] = payload

    if knowledge_output:
        payload = knowledge_output.get("payload", {})
        state.shared_context["knowledge"] = payload
        state.context["rag_context"] = payload.get("prompt_context", state.context.get("rag_context"))

    if report_output and state.result:
        payload = report_output.get("payload", {})
        state.result.summary = payload.get("summary", state.result.summary)
        if payload.get("metadata"):
            state.result.metadata.update(payload["metadata"])

    state.context["agent_trace"] = list(state.agent_trace)
    state.logs.append(f"[Supervisor] Merge complete, agent outputs={list(state.agent_outputs.keys())}")
    return state
