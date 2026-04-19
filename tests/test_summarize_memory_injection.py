# Runtime-evidence test: summarize_node should read long-term memory and inject it into the prompt.

from __future__ import annotations

import asyncio
import uuid

import pytest

import app.core.graph as graph_module
from app.memory.config import DEFAULT_USER_ID
from app.memory.memory_manager import memory_manager
from app.memory.models import LongTermMemory
from app.memory.state import DetectionState
from app.schemas.detection import DetectionResult, DetectionTask


def test_summarize_node_injects_history_and_writes_memory(monkeypatch: pytest.MonkeyPatch):
    user_id = DEFAULT_USER_ID
    marker = f"TEST_HISTORY_MARKER_SUMMARY_{uuid.uuid4().hex}"
    fake_summary = f"FAKE_SUMMARY_{uuid.uuid4().hex}"

    memory_manager.add_long_term_memory(
        LongTermMemory(
            user_id=user_id,
            memory_summary=marker,
            related_tasks=["test-task-summarize-injection"],
        )
    )

    class FakeResponse:
        def __init__(self, content: str):
            self.content = content

    class FakeChatOpenAI:
        captured_messages = None

        async def ainvoke(self, messages):
            FakeChatOpenAI.captured_messages = messages
            return FakeResponse(fake_summary)

    # Monkeypatch LLM to avoid real network calls.
    monkeypatch.setattr(graph_module, "ChatOpenAI", lambda *args, **kwargs: FakeChatOpenAI())

    task = DetectionTask(
        task_id="task-summary-injection",
        asset_id="asset-1",
        start_time="2025-01-01T00:00:00Z",
        end_time="2025-01-01T01:00:00Z",
        parameters={},
    )
    result = DetectionResult(
        task_id=task.task_id,
        status="success",
        anomalies=[],
        summary=None,
        metadata={},
    )
    state = DetectionState(task=task, result=result)

    asyncio.run(graph_module.summarize_node(state))

    assert FakeChatOpenAI.captured_messages is not None
    assert marker in str(FakeChatOpenAI.captured_messages)

    histories = memory_manager.get_long_term_memory(user_id)
    assert any(h.memory_summary == fake_summary for h in histories)

