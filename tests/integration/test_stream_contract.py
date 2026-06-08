from __future__ import annotations

from collections.abc import AsyncGenerator

from fastapi.testclient import TestClient

import app.api.main as api_main
from app.schemas.detection import DetectionTask


def test_stream_endpoint_dispatches_initial_image_detection(monkeypatch) -> None:
    client = TestClient(api_main.app)
    captured_tasks: list[DetectionTask] = []

    async def fake_stream_detection(task: DetectionTask) -> AsyncGenerator[str, None]:
        captured_tasks.append(task)
        assert task.task_id == "stream-detect-001"
        assert task.asset_id == "asset-stream-001"
        assert task.question == "inspect this sample"
        assert task.input_type == "image"
        assert task.parameters["image_base64"]
        assert task.parameters["image_mime"] == "image/png"
        yield 'data: {"type":"execution_event","event":{"type":"task_started"}}\n\n'
        yield (
            'data: {"type":"final_result","task_id":"stream-detect-001","status":"success",'
            '"answer":"streamed detection answer","anomalies":[],"metadata":{"execution_events":[{"type":"task_started"}]}}\n\n'
        )
        yield "event: close\ndata: close\n\n"

    monkeypatch.setattr("app.services.stream_detection", fake_stream_detection)

    response = client.post(
        "/v1/stream",
        data={
            "task_id": "stream-detect-001",
            "asset_id": "asset-stream-001",
            "question": "inspect this sample",
            "parameters": '{"tool_type":"qwen"}',
        },
        files={"image": ("sample.png", b"fake-png-bytes", "image/png")},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    text = response.text
    assert '"type":"execution_event"' in text
    assert '"type":"final_result"' in text
    assert '"answer":"streamed detection answer"' in text
    assert len(captured_tasks) == 1
