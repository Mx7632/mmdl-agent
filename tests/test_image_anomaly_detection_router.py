import base64

import pytest
from fastapi.testclient import TestClient

import app.api.main as api_main
from app.exceptions.base import ConfigurationError
from app.schemas.detection import DetectionResult, DetectionTask, ToolResponse
from app.core.tools import VisualAnomalyLocalizationTool
from app.tools.image_anomaly_detection import (
    HttpProfessionalImageAnomalyDetectionTool,
    ImageAnomalyDetectionTool,
    normalize_visual_anomalies,
)


class DummyImageTool:
    def __init__(self, name: str) -> None:
        self.name = name
        self.calls: list[str] = []

    async def run(self, task: DetectionTask) -> ToolResponse:
        self.calls.append(task.task_id)
        return ToolResponse(
            tool_name=self.name,
            success=True,
            result=DetectionResult(
                task_id=task.task_id,
                status="success",
                anomalies=[],
                metadata={"tool": self.name},
            ),
        )


async def test_image_router_uses_qwen_backend_for_qwen_tool_type():
    qwen_tool = DummyImageTool("qwen")
    specialist_tool = DummyImageTool("specialist")
    router = ImageAnomalyDetectionTool(qwen_tool=qwen_tool, specialist_tool=specialist_tool)

    task = DetectionTask(
        task_id="task-qwen",
        asset_id="asset-1",
        start_time="2026-04-22T00:00:00Z",
        end_time="2026-04-22T00:00:00Z",
        parameters={"image_base64": base64.b64encode(b"img").decode("ascii"), "tool_type": "qwen3.5-plus"},
    )

    response = await router.run(task)

    assert qwen_tool.calls == ["task-qwen"]
    assert specialist_tool.calls == []
    assert response.tool_name == "qwen"
    assert response.result is not None
    assert response.result.metadata["selected_backend"] == "qwen"


async def test_image_router_uses_specialist_backend_for_anomalygpt():
    qwen_tool = DummyImageTool("qwen")
    specialist_tool = DummyImageTool("specialist")
    router = ImageAnomalyDetectionTool(qwen_tool=qwen_tool, specialist_tool=specialist_tool)

    task = DetectionTask(
        task_id="task-specialist",
        asset_id="asset-1",
        start_time="2026-04-22T00:00:00Z",
        end_time="2026-04-22T00:00:00Z",
        parameters={"image_base64": base64.b64encode(b"img").decode("ascii"), "tool_type": "anomalygpt"},
    )

    response = await router.run(task)

    assert qwen_tool.calls == []
    assert specialist_tool.calls == ["task-specialist"]
    assert response.tool_name == "specialist"
    assert response.result is not None
    assert response.result.metadata["selected_backend"] == "specialist"


async def test_specialist_detector_requires_service_url(monkeypatch):
    tool = HttpProfessionalImageAnomalyDetectionTool()
    monkeypatch.setattr(
        "app.tools.image_anomaly_detection.settings.professional_vision_detector_url",
        "",
    )

    task = DetectionTask(
        task_id="task-missing-url",
        asset_id="asset-1",
        start_time="2026-04-22T00:00:00Z",
        end_time="2026-04-22T00:00:00Z",
        parameters={"image_base64": base64.b64encode(b"img").decode("ascii"), "tool_type": "anomalygpt"},
    )

    with pytest.raises(ConfigurationError):
        await tool.run(task)


def test_detect_endpoint_uses_configured_default_visual_backend(monkeypatch):
    client = TestClient(api_main.app)
    captured: dict[str, DetectionTask] = {}

    async def fake_run_detection(task: DetectionTask):
        captured["task"] = task
        return {
            "task_id": task.task_id,
            "status": "success",
            "anomalies": [],
            "metadata": {},
        }

    monkeypatch.setattr(api_main, "run_detection", fake_run_detection)
    monkeypatch.setattr(api_main.settings, "vision_detector_backend", "anomalygpt")

    response = client.post(
        "/v1/detect",
        data={
            "task_id": "task-api",
            "asset_id": "asset-api",
            "start_time": "2026-04-22T00:00:00Z",
            "end_time": "2026-04-22T00:00:00Z",
            "parameters": "{}",
        },
        files={"image": ("sample.jpg", b"fake-image", "image/jpeg")},
    )

    assert response.status_code == 200
    assert captured["task"].parameters["tool_type"] == "anomalygpt"
    assert captured["task"].parameters["image_mime"] == "image/jpeg"


def test_normalize_visual_anomalies_adds_location():
    anomalies = normalize_visual_anomalies(
        [{"type": "scratch", "bbox": [10, 20, 50, 80]}],
        image_size=(300, 300),
    )

    assert anomalies[0]["bbox"] == [10, 20, 50, 80]
    assert anomalies[0]["location"] == "top-left"
    assert anomalies[0]["has_localization"] is True


async def test_visual_localization_tool_sets_localization_flag(monkeypatch):
    captured: dict[str, DetectionTask] = {}

    async def fake_run(self, task: DetectionTask) -> ToolResponse:
        captured["task"] = task
        return ToolResponse(
            tool_name="image_anomaly_detection",
            success=True,
            result=DetectionResult(
                task_id=task.task_id,
                status="success",
                anomalies=[],
                metadata={"analysis_mode": "localization"},
            ),
        )

    monkeypatch.setattr(ImageAnomalyDetectionTool, "run", fake_run)
    tool = VisualAnomalyLocalizationTool()

    result = await tool._arun(
        task_id="task-localize",
        asset_id="asset-localize",
        image_base64=base64.b64encode(b"img").decode("ascii"),
        question="异常在哪里？",
        parameters={},
    )

    parsed = __import__("json").loads(result)
    assert captured["task"].parameters["require_localization"] is True
    assert parsed["metadata"]["analysis_mode"] == "localization"
