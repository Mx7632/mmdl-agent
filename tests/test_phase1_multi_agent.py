from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager

import pytest

from app.agents.factory import get_supervisor_agent
from app.agents.report.service import generate_report_state
from app.core.answer_node import answer_node
from app.core.agent import get_pending_task, stream_detection
from app.core.self_reflect import self_reflect_node
from app.core.supervisor import supervisor_execute_node, supervisor_merge_node, supervisor_plan_node
from app.core.wait_user import wait_user_node
from app.memory.state import DetectionState
from app.orchestration.envelope import AgentEnvelope
from app.schemas.detection import DetectionResult, DetectionTask


def build_state(question: str = "Please analyze the anomaly in this image.") -> DetectionState:
    task = DetectionTask(
        task_id="phase4-001",
        asset_id="asset-001",
        start_time="2026-04-26T00:00:00Z",
        end_time="2026-04-26T00:01:00Z",
        question=question,
        parameters={"image_base64": "aW1hZ2U="},
    )
    return DetectionState(task=task, result=DetectionResult(task_id=task.task_id, status="success"))


def test_supervisor_fallback_returns_structured_vision_plan(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("app.agents.supervisor.agent.settings.openai_api_key", "")
    supervisor = get_supervisor_agent()
    state = build_state()

    plan = supervisor.plan(state)

    assert len(plan.steps) == 1
    assert plan.steps[0].agent == "vision"
    assert plan.steps[0].goal
    assert plan.reason == "fallback routing"


def test_supervisor_fallback_adds_knowledge_for_reasoning_questions(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("app.agents.supervisor.agent.settings.openai_api_key", "")
    supervisor = get_supervisor_agent()
    state = build_state("Please explain the reason and repair suggestion for the anomaly.")

    plan = supervisor.plan(state)

    assert [step.agent for step in plan.steps] == ["vision", "knowledge"]
    assert plan.steps[1].depends_on == [plan.steps[0].id]


def test_supervisor_prefers_clarification_when_waiting_for_user(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("app.agents.supervisor.agent.settings.openai_api_key", "")
    supervisor = get_supervisor_agent()
    state = build_state()
    state.needs_user_input = True
    state.unknown_anomaly_types = ["unclear boundary"]

    plan = supervisor.plan(state)

    assert [step.agent for step in plan.steps] == ["clarification"]


def test_supervisor_retry_plan_allows_rerun(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("app.agents.supervisor.agent.settings.openai_api_key", "")
    supervisor = get_supervisor_agent()
    state = build_state()
    state.agent_outputs["vision"] = {"payload": {"anomalies": [{"type": "scratch"}]}}
    state.reflection_decision = "retry"
    state.retry_target = "vision"
    state.retry_reason = "low confidence on anomaly boundary"
    state.retry_strategy = "rerun_with_focus"
    state.step_attempts["vision"] = 1

    plan = supervisor.plan(state)

    assert [step.agent for step in plan.steps] == ["vision"]
    assert plan.steps[0].id == "vision-2"
    assert "retry" in plan.steps[0].goal


def test_supervisor_prefers_llm_structured_plan(monkeypatch: pytest.MonkeyPatch):
    class FakeResponse:
        content = '{"planned_agents":["vision","knowledge"],"reason":"need retrieval"}'

    class FakeChatOpenAI:
        def invoke(self, messages):
            return FakeResponse()

    monkeypatch.setattr("app.agents.supervisor.agent.ChatOpenAI", lambda *args, **kwargs: FakeChatOpenAI())
    monkeypatch.setattr("app.agents.supervisor.agent.settings.openai_api_key", "fake-key")

    supervisor = get_supervisor_agent()
    state = build_state("Please combine similar cases and explain the root cause.")

    plan = supervisor.plan(state)

    assert [step.agent for step in plan.steps] == ["vision", "knowledge"]
    assert state.context["supervisor_reason"] == "need retrieval"


def test_supervisor_execute_and_merge(monkeypatch: pytest.MonkeyPatch):
    state = build_state("Please explain the reason and repair suggestion for the anomaly.")

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
        assert [step["agent"] for step in planned_state.execution_plan["steps"]] == ["vision", "knowledge"]

        executed_state = await supervisor_execute_node(planned_state)
        assert "vision" in executed_state.agent_outputs
        assert "knowledge" in executed_state.agent_outputs
        assert len(executed_state.agent_trace) == 2
        assert executed_state.loop_count == 1
        assert executed_state.step_status["vision-1"] == "success"
        assert executed_state.step_attempts["vision"] == 1

        merged_state = await supervisor_merge_node(executed_state)
        assert merged_state.tool_outputs[0]["tool"] == "vision_agent"
        assert merged_state.tool_outputs[0]["anomalies"][0]["type"] == "scratch"
        assert merged_state.context["rag_context"] == "similar case context"
        assert merged_state.result.anomalies[0]["type"] == "scratch"
        assert merged_state.result.answer == "vision answer"

    asyncio.run(runner())


def test_supervisor_execute_runs_independent_steps_in_parallel(monkeypatch: pytest.MonkeyPatch):
    state = build_state()
    state.execution_plan = {
        "steps": [
            {
                "id": "clarification-1",
                "agent": "clarification",
                "goal": "prepare clarification",
                "depends_on": [],
                "retryable": True,
            },
            {
                "id": "report-1",
                "agent": "report",
                "goal": "generate report",
                "depends_on": [],
                "retryable": False,
            },
        ],
        "reason": "parallel smoke",
        "stop_when_confident": True,
    }

    running = 0
    max_running = 0

    async def fake_clarification_run(self, current_state):
        nonlocal running, max_running
        running += 1
        max_running = max(max_running, running)
        await asyncio.sleep(0.02)
        running -= 1
        return AgentEnvelope(agent_name="clarification", summary="clarification done", payload={"requires_human": True})

    async def fake_report_run(self, current_state):
        nonlocal running, max_running
        running += 1
        max_running = max(max_running, running)
        await asyncio.sleep(0.02)
        running -= 1
        return AgentEnvelope(agent_name="report", summary="report done", payload={"summary": "report"})

    monkeypatch.setattr("app.agents.clarification.agent.ClarificationAgent.run", fake_clarification_run)
    monkeypatch.setattr("app.agents.report.agent.ReportAgent.run", fake_report_run)

    updated = asyncio.run(supervisor_execute_node(state))

    assert updated.step_status["clarification-1"] == "success"
    assert updated.step_status["report-1"] == "success"
    assert max_running == 2


def test_supervisor_merge_applies_all_registered_adapters():
    state = build_state()
    state.agent_outputs = {
        "vision": {
            "payload": {
                "anomalies": [{"type": "scratch", "details": "surface scratch"}],
                "metadata": {"confidence": 0.81},
                "answer": "vision answer",
            }
        },
        "knowledge": {
            "payload": {
                "rows": [{"id": "case-1"}],
                "prompt_context": "retrieved context",
            }
        },
        "clarification": {
            "payload": {
                "pending_clarification": "Need operator confirmation",
                "pending_question": "Is the defect near the upper edge?",
                "unknown_anomaly_types": ["edge defect"],
                "requires_human": True,
            }
        },
        "report": {
            "payload": {
                "summary": "final report summary",
                "metadata": {"report_version": "v1"},
            }
        },
    }

    updated = asyncio.run(supervisor_merge_node(state))

    assert updated.shared_context.vision is not None
    assert updated.shared_context.knowledge is not None
    assert updated.shared_context.clarification is not None
    assert updated.shared_context.report is not None
    assert updated.context["rag_context"] == "retrieved context"
    assert updated.context["pending_question"] == "Is the defect near the upper edge?"
    assert updated.needs_user_input is True
    assert updated.result.answer == "vision answer"
    assert updated.result.summary == "final report summary"
    assert updated.result.metadata["confidence"] == 0.81
    assert updated.result.metadata["report_version"] == "v1"


def test_self_reflect_sets_retry_target(monkeypatch: pytest.MonkeyPatch):
    class FakeResponse:
        content = (
            '{"confidence":0.32,"unknown_anomaly_types":[],"can_proceed":false,'
            '"reason":"need another visual pass","retry_target":"vision",'
            '"retry_strategy":"rerun_with_focus"}'
        )

    class FakeChatOpenAI:
        async def ainvoke(self, messages, config=None):
            return FakeResponse()

    monkeypatch.setattr("app.core.self_reflect.ChatOpenAI", lambda *args, **kwargs: FakeChatOpenAI())
    monkeypatch.setattr("app.core.self_reflect.settings.openai_api_key", "fake-key")
    monkeypatch.setattr("app.core.self_reflect.memory_manager.get_long_term_memory", lambda user_id: [])

    state = build_state()
    state.shared_context["vision"] = {"anomalies": [{"type": "dent", "details": "metal dent"}]}

    updated = asyncio.run(self_reflect_node(state))

    assert updated.reflection_decision == "retry"
    assert updated.retry_target == "vision"
    assert updated.retry_strategy == "rerun_with_focus"
    assert updated.retry_reason == "need another visual pass"


def test_answer_node_prefers_shared_context(monkeypatch: pytest.MonkeyPatch):
    class FakeResponse:
        content = "Structured diagnosis answer"

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

    assert updated.context["answer"] == "Structured diagnosis answer"
    assert updated.result.anomalies[0]["type"] == "dent"
    assert updated.result.metadata["confidence"] == 0.88
    assert updated.current_step == 2


def test_generate_report_state_prefers_shared_context(monkeypatch: pytest.MonkeyPatch):
    class FakeResponse:
        content = "Complete report content"

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
    state.conversation_history.append({"role": "user", "content": "Please generate a full report."})

    updated = asyncio.run(generate_report_state(state))

    assert updated.result.summary == "Complete report content"
    assert updated.result.anomalies[0]["type"] == "crack"
    assert updated.result.metadata["selected_backend"] == "anomalygpt"
    assert updated.shared_context.report.summary == "Complete report content"


def test_clarification_merge_and_pending_lookup(monkeypatch: pytest.MonkeyPatch):
    state = build_state()
    state.needs_user_input = True
    state.unknown_anomaly_types = ["unclear boundary", "unclear location"]
    monkeypatch.setattr("app.agents.supervisor.agent.settings.openai_api_key", "")

    async def runner():
        planned_state = await supervisor_plan_node(state)
        assert [step["agent"] for step in planned_state.execution_plan["steps"]] == ["clarification"]

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


def test_wait_user_records_suspend_and_resume_events():
    state = build_state()
    state.shared_context["clarification"] = {
        "pending_clarification": "Need operator confirmation",
        "pending_question": "Is the defect near the upper edge?",
        "unknown_anomaly_types": ["edge defect"],
        "requires_human": True,
    }

    suspended = asyncio.run(wait_user_node(state))
    assert suspended.execution_events[-1]["type"] == "task_suspended"
    assert suspended.execution_events[-1]["pending_question"] == "Is the defect near the upper edge?"

    suspended.user_reply = "Confirmed, it is near the upper edge."
    resumed = asyncio.run(wait_user_node(suspended))
    assert resumed.execution_events[-1]["type"] == "task_resumed"


def test_stream_detection_emits_execution_events_and_final_metadata(monkeypatch: pytest.MonkeyPatch):
    task = DetectionTask(
        task_id="stream-001",
        asset_id="asset-001",
        start_time="2026-04-26T00:00:00Z",
        end_time="2026-04-26T00:01:00Z",
        question="stream please",
        parameters={},
    )
    final_output = {
        "execution_events": [
            {"type": "plan_created", "planned_agents": ["vision"], "step_count": 1},
            {"type": "step_started", "step_id": "vision-1", "agent": "vision", "attempt": 1},
            {"type": "step_completed", "step_id": "vision-1", "agent": "vision", "status": "success"},
        ],
        "agent_trace": [{"step_id": "vision-1", "agent": "vision", "status": "success"}],
        "execution_plan": {"steps": [{"id": "vision-1", "agent": "vision"}]},
        "step_status": {"vision-1": "success"},
        "step_attempts": {"vision": 1},
    }

    class FakeGraph:
        async def astream_events(self, invoke_input, config=None, version="v2"):
            yield {"event": "on_chain_start", "name": "supervisor_execute", "data": {}}
            yield {"event": "on_chain_end", "name": "supervisor_execute", "data": {"output": final_output}}
            yield {"event": "on_chain_end", "name": "LangGraph", "data": {"output": final_output}}

    @asynccontextmanager
    async def fake_graph_session(task_id: str):
        yield FakeGraph(), {"configurable": {"thread_id": task_id}}, "memory"

    async def fake_load_state_values(task_id: str):
        return None, "memory"

    monkeypatch.setattr("app.core.agent.graph_session", fake_graph_session)
    monkeypatch.setattr("app.core.agent.load_state_values", fake_load_state_values)
    monkeypatch.setattr("app.core.agent.persist_runtime_state", lambda task_id, state, backend: None)

    async def collect():
        chunks: list[str] = []
        async for chunk in stream_detection(task):
            chunks.append(chunk)
        return chunks

    chunks = asyncio.run(collect())

    execution_payloads = [
        json.loads(chunk.removeprefix("data: ").strip())
        for chunk in chunks
        if chunk.startswith("data: ") and '"type": "execution_event"' in chunk
    ]
    final_payloads = [
        json.loads(chunk.removeprefix("data: ").strip())
        for chunk in chunks
        if chunk.startswith("data: ") and '"type": "final_result"' in chunk
    ]

    assert len(execution_payloads) == 3
    assert execution_payloads[0]["event"]["type"] == "plan_created"
    assert final_payloads[0]["metadata"]["step_status"]["vision-1"] == "success"
    assert final_payloads[0]["metadata"]["execution_events"][-1]["type"] == "step_completed"
