from __future__ import annotations

from app.agents.factory import get_supervisor_agent
from app.core.supervisor import supervisor_execute_node, supervisor_merge_node, supervisor_plan_node
from app.memory.state import DetectionState
from app.orchestration.envelope import AgentEnvelope
from app.schemas.detection import DetectionResult, DetectionTask


def build_state(question: str = "请分析图像异常") -> DetectionState:
    task = DetectionTask(
        task_id="phase1-001",
        asset_id="asset-001",
        start_time="2026-04-26T00:00:00Z",
        end_time="2026-04-26T00:01:00Z",
        question=question,
        parameters={"image_base64": "aW1hZ2U="},
    )
    return DetectionState(task=task, result=DetectionResult(task_id=task.task_id, status="success"))


def test_supervisor_plans_vision_by_default():
    supervisor = get_supervisor_agent()
    state = build_state()

    planned = supervisor.plan(state)

    assert planned == ["vision"]


def test_supervisor_adds_knowledge_for_reasoning_questions():
    supervisor = get_supervisor_agent()
    state = build_state("请分析异常原因并给出维修建议")

    planned = supervisor.plan(state)

    assert "vision" in planned
    assert "knowledge" in planned


async def test_supervisor_execute_and_merge(monkeypatch):
    state = build_state("请分析异常原因")

    async def fake_vision_run(self, task):
        return AgentEnvelope(
            agent_name="vision",
            summary="vision done",
            payload={
                "anomalies": [
                    {
                        "type": "scratch",
                        "details": "surface scratch",
                        "bbox": [1, 2, 3, 4],
                    }
                ],
                "metadata": {"selected_backend": "qwen"},
            },
            confidence=0.8,
        )

    async def fake_knowledge_run(self, task, anomalies=None):
        return AgentEnvelope(
            agent_name="knowledge",
            summary="knowledge done",
            payload={
                "rows": [{"id": "case-1"}],
                "prompt_context": "similar case context",
            },
            confidence=0.7,
        )

    monkeypatch.setattr("app.agents.vision.agent.VisionAgent.run", fake_vision_run)
    monkeypatch.setattr("app.agents.knowledge.agent.KnowledgeAgent.run", fake_knowledge_run)

    state = await supervisor_plan_node(state)
    assert state.context["planned_agents"] == ["vision", "knowledge"]

    state = await supervisor_execute_node(state)
    assert "vision" in state.agent_outputs
    assert "knowledge" in state.agent_outputs
    assert len(state.agent_trace) == 2

    state = await supervisor_merge_node(state)
    assert state.tool_outputs[0]["tool"] == "vision_agent"
    assert state.tool_outputs[0]["anomalies"][0]["type"] == "scratch"
    assert state.context["rag_context"] == "similar case context"
