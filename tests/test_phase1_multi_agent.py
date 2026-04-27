from __future__ import annotations

import asyncio

import pytest

from app.agents.factory import get_supervisor_agent
from app.agents.report.service import generate_report_state
from app.core.answer_node import answer_node
from app.core.agent import get_pending_task
from app.core.supervisor import supervisor_execute_node, supervisor_merge_node, supervisor_plan_node
from app.memory.state import DetectionState
from app.orchestration.envelope import AgentEnvelope
from app.schemas.detection import DetectionResult, DetectionTask


def build_state(question: str = "请分析图像异常") -> DetectionState:
    task = DetectionTask(
        task_id="phase3-001",
        asset_id="asset-001",
        start_time="2026-04-26T00:00:00Z",
        end_time="2026-04-26T00:01:00Z",
        question=question,
        parameters={"image_base64": "aW1hZ2U="},
    )
    return DetectionState(task=task, result=DetectionResult(task_id=task.task_id, status="success"))


def test_supervisor_fallback_plans_vision_by_default(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("app.agents.supervisor.agent.settings.openai_api_key", "")
    supervisor = get_supervisor_agent()
    state = build_state()

    planned = supervisor.plan(state)

    assert planned == ["vision"]


def test_supervisor_fallback_adds_knowledge_for_reasoning_questions(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("app.agents.supervisor.agent.settings.openai_api_key", "")
    supervisor = get_supervisor_agent()
    state = build_state("请分析异常原因并给出维修建议")

    planned = supervisor.plan(state)

    assert "vision" in planned
    assert "knowledge" in planned


def test_supervisor_prefers_clarification_when_waiting_for_user(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("app.agents.supervisor.agent.settings.openai_api_key", "")
    supervisor = get_supervisor_agent()
    state = build_state()
    state.needs_user_input = True
    state.unknown_anomaly_types = ["裂纹边界不清晰"]

    planned = supervisor.plan(state)

    assert planned == ["clarification"]


def test_supervisor_prefers_llm_structured_plan(monkeypatch: pytest.MonkeyPatch):
    class FakeResponse:
        content = '{"planned_agents":["vision","knowledge"],"reason":"need retrieval"}'

    class FakeChatOpenAI:
        def invoke(self, messages):
            return FakeResponse()

    monkeypatch.setattr("app.agents.supervisor.agent.ChatOpenAI", lambda *args, **kwargs: FakeChatOpenAI())
    monkeypatch.setattr("app.agents.supervisor.agent.settings.openai_api_key", "fake-key")

    supervisor = get_supervisor_agent()
    state = build_state("请结合案例说明异常原因")

    planned = supervisor.plan(state)

    assert planned == ["vision", "knowledge"]
    assert state.context["supervisor_reason"] == "need retrieval"


def test_supervisor_execute_and_merge(monkeypatch: pytest.MonkeyPatch):
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
                "metadata": {"selected_backend": "qwen", "confidence": 0.8},
                "answer": "vision answer",
            },
            confidence=0.8,
        )

    async def fake_knowledge_run(self, task, anomalies=None):
        assert anomalies and anomalies[0]["type"] == "scratch"
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
    monkeypatch.setattr("app.agents.supervisor.agent.settings.openai_api_key", "")

    async def runner():
        planned_state = await supervisor_plan_node(state)
        assert planned_state.context["planned_agents"] == ["vision", "knowledge"]

        executed_state = await supervisor_execute_node(planned_state)
        assert "vision" in executed_state.agent_outputs
        assert "knowledge" in executed_state.agent_outputs
        assert len(executed_state.agent_trace) == 2
        assert executed_state.loop_count == 1

        merged_state = await supervisor_merge_node(executed_state)
        assert merged_state.tool_outputs[0]["tool"] == "vision_agent"
        assert merged_state.tool_outputs[0]["anomalies"][0]["type"] == "scratch"
        assert merged_state.context["rag_context"] == "similar case context"
        assert merged_state.result.anomalies[0]["type"] == "scratch"
        assert merged_state.result.answer == "vision answer"

    asyncio.run(runner())


def test_answer_node_prefers_shared_context(monkeypatch: pytest.MonkeyPatch):
    class FakeResponse:
        content = "结构化诊断回答"

    class FakeChatOpenAI:
        async def ainvoke(self, messages, config=None):
            return FakeResponse()

    monkeypatch.setattr("app.core.answer_node.ChatOpenAI", lambda *args, **kwargs: FakeChatOpenAI())
    monkeypatch.setattr("app.core.answer_node.settings.openai_api_key", "fake-key")

    state = build_state()
    state.shared_context["vision"] = {
        "anomalies": [{"type": "dent", "details": "metal dent"}],
        "metadata": {"confidence": 0.88},
        "answer": "vision shortcut",
    }
    state.shared_context["knowledge"] = {"prompt_context": "retrieved knowledge"}

    updated = asyncio.run(answer_node(state))

    assert updated.context["answer"] == "结构化诊断回答"
    assert updated.result.anomalies[0]["type"] == "dent"
    assert updated.result.metadata["confidence"] == 0.88
    assert updated.current_step == 2


def test_generate_report_state_prefers_shared_context(monkeypatch: pytest.MonkeyPatch):
    class FakeResponse:
        content = "完整报告内容"

    class FakeChatOpenAI:
        async def ainvoke(self, messages):
            return FakeResponse()

    monkeypatch.setattr("app.agents.report.service.ChatOpenAI", lambda *args, **kwargs: FakeChatOpenAI())
    monkeypatch.setattr("app.agents.report.service.settings.openai_api_key", "fake-key")

    state = build_state()
    state.shared_context["vision"] = {
        "anomalies": [{"type": "crack", "details": "surface crack"}],
        "metadata": {"selected_backend": "anomalygpt"},
    }
    state.shared_context["knowledge"] = {"prompt_context": "case context"}
    state.conversation_history.append({"role": "user", "content": "请给出完整报告"})

    updated = asyncio.run(generate_report_state(state))

    assert updated.result.summary == "完整报告内容"
    assert updated.result.anomalies[0]["type"] == "crack"
    assert updated.result.metadata["selected_backend"] == "anomalygpt"
    assert updated.shared_context.report.summary == "完整报告内容"


def test_clarification_merge_and_pending_lookup(monkeypatch: pytest.MonkeyPatch):
    state = build_state()
    state.needs_user_input = True
    state.unknown_anomaly_types = ["边界不清晰", "位置不确定"]
    monkeypatch.setattr("app.agents.supervisor.agent.settings.openai_api_key", "")

    async def runner():
        planned_state = await supervisor_plan_node(state)
        assert planned_state.context["planned_agents"] == ["clarification"]

        executed_state = await supervisor_execute_node(planned_state)
        merged_state = await supervisor_merge_node(executed_state)
        assert merged_state.shared_context.clarification is not None
        assert merged_state.shared_context.clarification.pending_question
        assert merged_state.context["pending_question"]

        async def fake_load_state_values(task_id: str):
            return merged_state.model_dump(), "memory"

        monkeypatch.setattr("app.core.agent.load_state_values", fake_load_state_values)
        pending = await get_pending_task(merged_state.task.task_id)
        assert pending is not None
        assert pending["pending_question"] == merged_state.context["pending_question"]
        assert pending["agent_trace"][0]["agent"] == "clarification"

        async def fake_missing_state_values(task_id: str):
            return None, "memory"

        monkeypatch.setattr("app.core.agent.load_state_values", fake_missing_state_values)
        pending = await get_pending_task("missing-task")
        assert pending is None

    asyncio.run(runner())
