from __future__ import annotations

from typing import Any

from app.memory.state import DetectionState
from app.rag.fewshot import build_fewshot_context
from app.rag.knowledge_pipeline import resolve_knowledge_request
from app.rag.service import get_rag_service


def _build_visual_fewshot(task: Any) -> tuple[dict[str, list[dict[str, Any]]], str]:
    try:
        service = get_rag_service()
        request = resolve_knowledge_request(task)
        if hasattr(service, "query_fewshot_rows"):
            rows = service.query_fewshot_rows(
                query_text=request["query_text"],
                category=request["category"],
                top_k=4,
            )
        else:
            rows = service.query_rows(
                query_text=request["query_text"],
                category=request["category"],
                top_k=4,
            )
        return build_fewshot_context(rows)
    except Exception:
        return {}, ""


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
    elif agent_name == "vision":
        few_shot_examples, few_shot_context = _build_visual_fewshot(task)
        if few_shot_examples or few_shot_context:
            envelope = await agent.run(  # type: ignore[attr-defined]
                task,
                few_shot_examples=few_shot_examples,
                few_shot_context=few_shot_context,
            )
        else:
            envelope = await agent.run(task)  # type: ignore[attr-defined]
    elif agent_name == "knowledge":
        anomalies = (domain.shared_context.vision.anomalies if domain.shared_context.vision else [])
        if not anomalies:
            anomalies = domain.agent_outputs.get("vision", {}).get("payload", {}).get("anomalies", [])
        envelope = await agent.run(task, anomalies=anomalies)  # type: ignore[attr-defined]
    else:
        envelope = await agent.run(task)  # type: ignore[attr-defined]

    return step_id, agent_name, attempt, envelope, None
