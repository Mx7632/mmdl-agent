from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager

import pytest

from app.agents.factory import get_supervisor_agent
from app.agents.vision.agent import VisionAgent
from app.agents.report.service import generate_report_state
from app.core.answer_node import answer_node
from app.core.agent import get_pending_task, stream_detection
from app.core.self_reflect import self_reflect_node
from app.core.supervisor import supervisor_execute_node, supervisor_merge_node, supervisor_plan_node
from app.core.wait_user import wait_user_node
from app.memory.conversation import compact_state_conversation
from app.memory.state import DetectionState
from app.orchestration.envelope import AgentEnvelope
from app.schemas.detection import DetectionResult, DetectionTask, ToolResponse
from app.tools.image_anomaly_detection import ImageAnomalyDetectionTool, resolve_visual_backend
from app.orchestration.context_store import get_pending_context_from_mapping
from app.tools.patchcore_detection import resolve_patchcore_category


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
    assert plan.reason == "规则回退路由"


def test_patchcore_backend_resolution(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("app.tools.image_anomaly_detection.settings.vision_detector_backend", "patchcore")
    assert resolve_visual_backend("patchcore") == "patchcore"
    assert resolve_visual_backend(None) == "patchcore"


def test_patchcore_category_resolution_prefers_detector_params():
    task = DetectionTask(
        task_id="patchcore-001",
        asset_id="asset-001",
        start_time="2026-04-27T00:00:00Z",
        end_time="2026-04-27T00:01:00Z",
        parameters={
            "image_base64": "aW1hZ2U=",
            "patchcore_category": "wood",
            "detector_params": {"category": "bottle"},
        },
    )

    assert resolve_patchcore_category(task) == "bottle"


def test_pending_context_mapping_handles_null_clarification():
    state_dict = {
        "context": {
            "pending_clarification": "Need operator confirmation",
            "pending_question": "Please confirm whether the mark is acceptable.",
        },
        "shared_context": {
            "clarification": None,
        },
    }

    pending_clarification, pending_question = get_pending_context_from_mapping(state_dict)

    assert pending_clarification == "Need operator confirmation"
    assert pending_question == "Please confirm whether the mark is acceptable."


@pytest.mark.asyncio
async def test_image_tool_routes_to_patchcore_backend():
    class FakePatchCoreTool:
        name = "patchcore_image_anomaly_detection"

        async def run(self, task):
            return ToolResponse(
                tool_name=self.name,
                success=True,
                result=DetectionResult(
                    task_id=task.task_id,
                    status="success",
                    anomalies=[{"type": "surface_anomaly", "bbox": [1, 2, 3, 4]}],
                    summary="patchcore ok",
                    metadata={"confidence": 0.9, "heatmap_path": "data/heatmaps/demo.png"},
                ),
            )

    task = DetectionTask(
        task_id="patchcore-route",
        asset_id="asset-001",
        start_time="2026-04-27T00:00:00Z",
        end_time="2026-04-27T00:01:00Z",
        parameters={"image_base64": "aW1hZ2U=", "tool_type": "patchcore"},
    )
    tool = ImageAnomalyDetectionTool(
        qwen_tool=FakePatchCoreTool(),
        specialist_tool=FakePatchCoreTool(),
        patchcore_tool=FakePatchCoreTool(),
    )

    response = await tool.run(task)

    assert response.tool_name == "patchcore_image_anomaly_detection"
    assert response.result is not None
    assert response.result.metadata["selected_backend"] == "patchcore"


@pytest.mark.asyncio
async def test_vision_agent_exposes_patchcore_heatmap_fields():
    class FakeVisionTool:
        async def run(self, task):
            return ToolResponse(
                tool_name="patchcore_image_anomaly_detection",
                success=True,
                result=DetectionResult(
                    task_id=task.task_id,
                    status="success",
                    anomalies=[{"type": "surface_anomaly"}],
                    summary="done",
                    metadata={
                        "confidence": 0.88,
                        "category": "bottle",
                        "heatmap_path": "data/heatmaps/bottle/task_heatmap.png",
                        "overlay_path": "data/heatmaps/bottle/task_overlay.png",
                        "mask_path": "data/heatmaps/bottle/task_mask.png",
                    },
                ),
            )

    task = DetectionTask(
        task_id="vision-patchcore",
        asset_id="asset-001",
        start_time="2026-04-27T00:00:00Z",
        end_time="2026-04-27T00:01:00Z",
        parameters={"image_base64": "aW1hZ2U="},
    )
    agent = VisionAgent(tool=FakeVisionTool())

    envelope = await agent.run(task)

    assert envelope.payload["category"] == "bottle"
    assert envelope.payload["heatmap_path"].endswith("task_heatmap.png")
    assert envelope.payload["overlay_path"].endswith("task_overlay.png")
    assert envelope.payload["mask_path"].endswith("task_mask.png")


def test_detection_state_runtime_views_group_fields():
    state = build_state()
    state.conversation_history.append({"role": "user", "content": "Need a second pass."})
    state.conversation_summary = "Earlier user asked for a baseline check."
    state.conversation_compacted_turns = 2
    state.user_reply = "Operator confirmed the defect."
    state.current_step = 3
    state.report_requested = True
    state.stage = "report"
    state.active_agent = "vision"
    state.execution_plan = {"steps": [{"id": "vision-1", "agent": "vision"}]}
    state.step_status["vision-1"] = "success"
    state.step_attempts["vision"] = 1
    state.execution_events.append({"type": "step_completed", "step_id": "vision-1"})
    state.loop_count = 2
    state.needs_user_input = True
    state.retry_target = "vision"
    state.shared_context["knowledge"] = {"prompt_context": "retrieved context"}
    state.agent_outputs["vision"] = {"payload": {"anomalies": [{"type": "scratch"}]}}

    task_runtime = state.task_runtime()
    orchestration_runtime = state.orchestration_runtime()
    domain_runtime = state.domain_runtime()

    assert task_runtime.task.task_id == state.task.task_id
    assert task_runtime.user_reply == "Operator confirmed the defect."
    assert task_runtime.current_step == 3
    assert task_runtime.conversation_summary == "Earlier user asked for a baseline check."
    assert task_runtime.conversation_compacted_turns == 2
    assert task_runtime.report_requested is True
    assert orchestration_runtime.active_agent == "vision"
    assert orchestration_runtime.execution_plan["steps"][0]["agent"] == "vision"
    assert orchestration_runtime.step_status["vision-1"] == "success"
    assert orchestration_runtime.needs_user_input is True
    assert orchestration_runtime.retry_target == "vision"
    assert domain_runtime.shared_context.knowledge is not None
    assert domain_runtime.shared_context.knowledge.prompt_context == "retrieved context"
    assert "vision" in domain_runtime.agent_outputs


def test_detection_state_runtime_apply_helpers():
    state = build_state()

    task_runtime = state.task_runtime()
    task_runtime.current_step = 5
    task_runtime.report_requested = True
    task_runtime.user_reply = "confirmed"
    task_runtime.conversation_history.append({"role": "user", "content": "please continue"})
    state.apply_task_runtime(task_runtime)

    orchestration_runtime = state.orchestration_runtime()
    orchestration_runtime.loop_count = 4
    orchestration_runtime.needs_user_input = True
    orchestration_runtime.retry_target = "knowledge"
    orchestration_runtime.execution_plan = {"steps": [{"id": "knowledge-1", "agent": "knowledge"}]}
    state.apply_orchestration_runtime(orchestration_runtime)

    domain_runtime = state.domain_runtime()
    domain_runtime.shared_context["knowledge"] = {"prompt_context": "cases"}
    domain_runtime.agent_outputs["knowledge"] = {"payload": {"rows": [{"id": "case-1"}]}}
    state.apply_domain_runtime(domain_runtime)

    assert state.current_step == 5
    assert state.report_requested is True
    assert state.user_reply == "confirmed"
    assert state.conversation_history[-1]["content"] == "please continue"
    assert state.loop_count == 4
    assert state.needs_user_input is True
    assert state.retry_target == "knowledge"
    assert state.execution_plan["steps"][0]["agent"] == "knowledge"
    assert state.shared_context.knowledge is not None
    assert state.shared_context.knowledge.prompt_context == "cases"
    assert "knowledge" in state.agent_outputs


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
    assert "重新执行" in plan.steps[0].goal


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
    assert updated.shared_context.knowledge.prompt_context == "retrieved context"
    assert updated.context["pending_question"] == "Is the defect near the upper edge?"
    assert updated.shared_context.clarification.pending_question == "Is the defect near the upper edge?"
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
    monkeypatch.setattr(
        "app.core.self_reflect.memory_manager.get_long_term_memory",
        lambda user_id, asset_id=None: [],
    )

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
    short_term_calls: list[object] = []
    working_calls: list[object] = []
    monkeypatch.setattr("app.core.answer_node.memory_manager.add_short_term_memory", lambda memory: short_term_calls.append(memory))
    monkeypatch.setattr("app.core.answer_node.memory_manager.add_working_memory", lambda memory: working_calls.append(memory))

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
    assert len(short_term_calls) == 1
    assert short_term_calls[0].asset_id == "asset-001"
    assert working_calls[0].task_id == state.task.task_id


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

        monkeypatch.setattr("app.services.task_runner.load_state_values", fake_load_state_values)
        pending = await get_pending_task(merged_state.task.task_id)
        assert pending is not None
        assert pending["pending_question"] == merged_state.context["pending_question"]
        assert pending["agent_trace"][0]["agent"] == "clarification"

        async def fake_missing_state_values(task_id: str):
            return None, "memory"

        monkeypatch.setattr("app.services.task_runner.load_state_values", fake_missing_state_values)
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


def test_compact_state_conversation_keeps_recent_turns():
    state = build_state()
    state.conversation_history = [
        {"role": "user", "content": f"user-{index}"}
        if index % 2 == 0
        else {"role": "assistant", "content": f"assistant-{index}"}
        for index in range(8)
    ]

    compacted = compact_state_conversation(state)

    assert compacted == 2
    assert len(state.conversation_history) == 6
    assert "user-0" in state.context["conversation_summary"]
    assert state.context["conversation_compacted_turns"] == 2


def test_prepare_followup_state_compacts_history():
    previous_state = build_state().model_dump()
    previous_state["conversation_history"] = [
        {"role": "user", "content": f"turn-{index}"}
        for index in range(6)
    ]

    from app.services.state_rehydration import prepare_followup_state

    updated = prepare_followup_state(previous_state, question="latest question")

    assert len(updated.conversation_history) == 6
    assert updated.conversation_history[-1]["content"] == "latest question"
    assert updated.conversation_summary is not None
    assert updated.context["conversation_compacted_turns"] == 1


def test_prepare_followup_state_preserves_existing_vision_context_without_new_image():
    previous = build_state()
    previous.result = DetectionResult(
        task_id=previous.task.task_id,
        status="success",
        anomalies=[{"type": "scratch", "details": "surface scratch"}],
        summary="initial summary",
    )
    previous.shared_context["vision"] = {
        "anomalies": [{"type": "scratch", "details": "surface scratch"}],
        "metadata": {"selected_backend": "qwen", "confidence": 0.82},
        "answer": "initial answer",
    }
    previous.agent_outputs["vision"] = {
        "payload": {
            "anomalies": [{"type": "scratch", "details": "surface scratch"}],
            "metadata": {"selected_backend": "qwen", "confidence": 0.82},
            "answer": "initial answer",
        }
    }

    from app.services.state_rehydration import prepare_followup_state

    updated = prepare_followup_state(previous.model_dump(), question="有没有使用rag")

    assert updated.result is not None
    assert updated.result.anomalies[0]["type"] == "scratch"
    assert updated.shared_context.vision is not None
    assert updated.shared_context.vision.metadata["selected_backend"] == "qwen"
    assert "vision" in updated.agent_outputs


def test_supervisor_fallback_adds_knowledge_for_rag_question(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("app.agents.supervisor.agent.settings.openai_api_key", "")
    supervisor = get_supervisor_agent()
    state = build_state("有没有使用rag")
    state.agent_outputs["vision"] = {"payload": {"anomalies": [{"type": "scratch"}]}}
    state.shared_context["vision"] = {
        "anomalies": [{"type": "scratch"}],
        "metadata": {"selected_backend": "qwen"},
    }

    plan = supervisor.plan(state)

    assert [step.agent for step in plan.steps] == ["knowledge"]


def test_restore_state_promotes_legacy_conversation_summary():
    from app.services.state_rehydration import restore_state

    previous_state = build_state().model_dump()
    previous_state["context"]["conversation_summary"] = "legacy summary"
    previous_state["context"]["conversation_compacted_turns"] = 3

    restored = restore_state(previous_state)

    assert restored.conversation_summary == "legacy summary"
    assert restored.conversation_compacted_turns == 3


def test_supervisor_execute_records_tool_context(monkeypatch: pytest.MonkeyPatch):
    state = build_state()
    state.execution_plan = {
        "steps": [
            {
                "id": "vision-1",
                "agent": "vision",
                "goal": "detect anomalies",
                "depends_on": [],
                "retryable": True,
            }
        ]
    }
    tool_context_calls: list[object] = []

    async def fake_vision_run(self, task):
        return AgentEnvelope(
            agent_name="vision",
            summary="vision done",
            payload={"anomalies": [{"type": "scratch"}]},
            confidence=0.8,
        )

    monkeypatch.setattr("app.agents.vision.agent.VisionAgent.run", fake_vision_run)
    monkeypatch.setattr("app.orchestration.planner_runtime.memory_manager.add_tool_context", lambda memory: tool_context_calls.append(memory))

    updated = asyncio.run(supervisor_execute_node(state))

    assert updated.step_status["vision-1"] == "success"
    assert len(tool_context_calls) == 1
    assert tool_context_calls[0].tool_name == "vision_agent"
    assert tool_context_calls[0].tool_output["anomaly_count"] == 1


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

    monkeypatch.setattr("app.services.streaming.graph_session", fake_graph_session)
    monkeypatch.setattr("app.services.streaming.load_state_values", fake_load_state_values)
    monkeypatch.setattr("app.services.streaming.persist_runtime_state", lambda task_id, state, backend: None)

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
    snapshot_payloads = [
        json.loads(chunk.removeprefix("data: ").strip())
        for chunk in chunks
        if chunk.startswith("data: ") and '"type": "execution_snapshot"' in chunk
    ]
    final_payloads = [
        json.loads(chunk.removeprefix("data: ").strip())
        for chunk in chunks
        if chunk.startswith("data: ") and '"type": "final_result"' in chunk
    ]

    assert len(execution_payloads) == 3
    assert snapshot_payloads[0]["execution_plan"]["steps"][0]["id"] == "vision-1"
    assert snapshot_payloads[0]["step_status"]["vision-1"] == "success"
    assert execution_payloads[0]["event"]["type"] == "plan_created"
    assert final_payloads[0]["metadata"]["step_status"]["vision-1"] == "success"
    assert final_payloads[0]["metadata"]["execution_events"][-1]["type"] == "step_completed"
