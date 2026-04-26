from __future__ import annotations

from fastapi.testclient import TestClient

import app.api.main as api_main
from app.schemas.detection import DetectionTask


def test_main_flow_detect_chat_report(monkeypatch):
    client = TestClient(api_main.app)
    calls: list[tuple[str, str]] = []

    async def fake_run_detection(task: DetectionTask):
        calls.append(("detect", task.task_id))
        assert task.input_type == "image"
        assert task.parameters["image_base64"]
        return {
            "task_id": task.task_id,
            "status": "success",
            "answer": "初始检测完成",
            "anomalies": [
                {
                    "type": "scratch",
                    "bbox": [10, 10, 40, 40],
                    "location": "top-left",
                    "has_localization": True,
                }
            ],
            "metadata": {"result_metadata": {"analysis_mode": "localization"}},
        }

    async def fake_run_chat(task_id: str, question: str):
        calls.append(("chat", task_id))
        assert question == "异常严重吗？"
        return {
            "task_id": task_id,
            "status": "success",
            "answer": "已结合现有结果回答追问",
            "anomalies": [
                {
                    "type": "scratch",
                    "bbox": [10, 10, 40, 40],
                    "location": "top-left",
                    "has_localization": True,
                }
            ],
            "metadata": {"result_metadata": {"analysis_mode": "localization"}},
        }

    async def fake_generate_report(task_id: str):
        calls.append(("report", task_id))
        return {
            "task_id": task_id,
            "status": "success",
            "summary": "报告生成完成",
            "anomalies": [
                {
                    "type": "scratch",
                    "bbox": [10, 10, 40, 40],
                    "location": "top-left",
                    "has_localization": True,
                }
            ],
            "has_report": True,
            "metadata": {"result_metadata": {"analysis_mode": "localization"}},
        }

    monkeypatch.setattr(api_main, "run_detection", fake_run_detection)
    monkeypatch.setattr(api_main, "run_chat", fake_run_chat)
    monkeypatch.setattr(api_main, "generate_report", fake_generate_report)

    task_id = "smoke-main-001"
    detect_res = client.post(
        "/v1/detect",
        data={
            "task_id": task_id,
            "asset_id": "asset-001",
            "start_time": "2026-04-25T00:00:00Z",
            "end_time": "2026-04-25T00:01:00Z",
            "question": "请分析异常",
            "parameters": "{}",
        },
        files={"image": ("sample.jpg", b"fake-image-bytes", "image/jpeg")},
    )
    assert detect_res.status_code == 200
    detect_body = detect_res.json()
    assert detect_body["status"] == "success"
    assert detect_body["anomalies"][0]["bbox"] == [10, 10, 40, 40]

    chat_res = client.post(
        "/v1/chat",
        json={
            "task_id": task_id,
            "question": "异常严重吗？",
        },
    )
    assert chat_res.status_code == 200
    chat_body = chat_res.json()
    assert chat_body["status"] == "success"
    assert "answer" in chat_body

    report_res = client.post(
        "/v1/generate_report",
        json={"task_id": task_id},
    )
    assert report_res.status_code == 200
    report_body = report_res.json()
    assert report_body["status"] == "success"
    assert report_body["has_report"] is True
    assert report_body["summary"] == "报告生成完成"

    assert calls == [
        ("detect", task_id),
        ("chat", task_id),
        ("report", task_id),
    ]


def test_pending_flow_detect_then_continue(monkeypatch):
    client = TestClient(api_main.app)
    calls: list[tuple[str, str]] = []

    async def fake_run_detection(task: DetectionTask):
        calls.append(("detect", task.task_id))
        return {
            "task_id": task.task_id,
            "status": "pending",
            "pending_question": "请确认异常区域是否在左上角？",
            "pending_clarification": "需要人工确认位置",
            "conversation_history": [{"role": "assistant", "content": "需要补充信息"}],
        }

    async def fake_continue_detection(task_id: str, user_reply: str):
        calls.append(("continue", task_id))
        assert user_reply == "确认，在左上角"
        return {
            "task_id": task_id,
            "status": "success",
            "answer": "已根据澄清继续完成检测",
            "anomalies": [
                {
                    "type": "scratch",
                    "bbox": [12, 8, 42, 38],
                    "location": "top-left",
                    "has_localization": True,
                }
            ],
        }

    monkeypatch.setattr(api_main, "run_detection", fake_run_detection)
    monkeypatch.setattr(api_main, "continue_detection", fake_continue_detection)

    task_id = "smoke-pending-001"
    detect_res = client.post(
        "/v1/detect",
        data={
            "task_id": task_id,
            "asset_id": "asset-002",
            "start_time": "2026-04-25T00:00:00Z",
            "end_time": "2026-04-25T00:01:00Z",
            "question": "请定位异常",
            "parameters": "{}",
        },
        files={"image": ("sample.jpg", b"fake-image-bytes", "image/jpeg")},
    )
    assert detect_res.status_code == 200
    detect_body = detect_res.json()
    assert detect_body["status"] == "pending"
    assert detect_body["pending_question"]

    continue_res = client.post(
        "/v1/continue",
        json={
            "task_id": task_id,
            "user_reply": "确认，在左上角",
        },
    )
    assert continue_res.status_code == 200
    continue_body = continue_res.json()
    assert continue_body["status"] == "success"
    assert continue_body["anomalies"][0]["location"] == "top-left"

    assert calls == [
        ("detect", task_id),
        ("continue", task_id),
    ]
