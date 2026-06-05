from __future__ import annotations

from fastapi.testclient import TestClient

import app.api.main as api_main
from app.evaluation.metrics import evaluate_predictions
from app.schemas.detection import DetectionTask
from app.services.industrial_runtime import industrial_store, normalize_industrial_result
from app.tools.patchcore_detection import predict_patchcore_image


def test_normalize_industrial_result_marks_low_confidence_for_review(monkeypatch):
    monkeypatch.setattr("app.services.industrial_runtime.settings.low_confidence_review_threshold", 0.75)
    result = normalize_industrial_result(
        {
            "task_id": "task-1",
            "status": "success",
            "anomalies": [{"type": "scratch", "score": 0.6, "details": "thin scratch"}],
            "metadata": {"result_metadata": {"selected_backend": "qwen"}},
        }
    )

    assert result["is_anomaly"] is True
    assert result["anomalies"][0]["defect_type"] == "scratch"
    assert result["review_status"] == "pending_review"
    assert result["requires_review"] is True
    assert result["metadata"]["industrial"]["model_backend"] == "qwen"


def test_evaluate_predictions_outputs_classification_and_iou_metrics():
    metrics = evaluate_predictions(
        [
            {
                "ground_truth": {"is_anomaly": True, "bbox": [0, 0, 10, 10]},
                "prediction": {"is_anomaly": True, "score": 0.9, "bbox": [0, 0, 10, 10]},
            },
            {
                "ground_truth": {"is_anomaly": False},
                "prediction": {"is_anomaly": False, "score": 0.1},
            },
            {
                "ground_truth": {"is_anomaly": True},
                "prediction": {"is_anomaly": False, "score": 0.2},
            },
        ],
        threshold=0.5,
    )

    assert metrics["tp"] == 1
    assert metrics["tn"] == 1
    assert metrics["fn"] == 1
    assert metrics["accuracy"] == 2 / 3
    assert metrics["mean_iou"] == 1.0


def test_batch_history_review_and_health_endpoints(monkeypatch, tmp_path):
    industrial_store.reset_for_tests(tmp_path / "industrial_state.json")
    client = TestClient(api_main.app)

    async def fake_run_detection(task: DetectionTask):
        return {
            "task_id": task.task_id,
            "status": "success",
            "answer": "done",
            "anomalies": [{"type": "dent", "score": 0.55, "bbox": [1, 2, 3, 4]}],
            "metadata": {"result_metadata": {"selected_backend": "qwen"}},
        }

    monkeypatch.setattr(api_main, "run_detection", fake_run_detection)

    response = client.post(
        "/v1/batches/detect",
        data={"asset_id": "PUMP-001", "question": "inspect", "parameters": "{}"},
        files=[
            ("images", ("a.jpg", b"fake-a", "image/jpeg")),
            ("images", ("b.jpg", b"fake-b", "image/jpeg")),
        ],
    )

    assert response.status_code == 200
    body = response.json()
    assert body["batch"]["item_count"] == 2
    assert body["report"]["anomaly_count"] == 2

    history = client.get("/v1/tasks", params={"asset_id": "PUMP-001"}).json()
    assert len(history["tasks"]) == 2
    assert history["tasks"][0]["review_status"] == "pending_review"

    task_id = history["tasks"][0]["task_id"]
    reviewed = client.post(
        f"/v1/tasks/{task_id}/review",
        json={"decision": "approve", "defect_type": "dent", "notes": "confirmed"},
    )
    assert reviewed.status_code == 200
    assert reviewed.json()["task"]["review_status"] == "approved"

    health = client.get("/v1/system/health")
    assert health.status_code == 200
    assert "components" in health.json()

    feedback = client.post(
        "/v1/rag/feedback/queue",
        json={
            "image_path": "data/uploads/sample.png",
            "category": "bottle",
            "user_description": "operator found missed dent",
            "model_confidence": 0.9,
            "is_anomaly": True,
        },
    )
    assert feedback.status_code == 200
    assert feedback.json()["review_status"] == "pending_review"


def test_memory_session_crud_endpoints(tmp_path):
    industrial_store.reset_for_tests(tmp_path / "industrial_state.json")
    client = TestClient(api_main.app)

    saved = client.post(
        "/v1/memory/sessions",
        json={
            "title": "Pump scratch analysis",
            "task_id": "task-memory-001",
            "asset_id": "PUMP-001",
            "history": [
                {"role": "user", "text": "检查泵体划痕"},
                {"role": "assistant", "text": "发现低置信度异常候选"},
            ],
            "metadata": {"pending": False},
        },
    )
    assert saved.status_code == 200
    session = saved.json()["session"]
    assert session["session_id"]
    assert session["title"] == "Pump scratch analysis"

    listed = client.get("/v1/memory/sessions").json()
    assert listed["sessions"][0]["session_id"] == session["session_id"]
    assert listed["sessions"][0]["turn_count"] == 2

    loaded = client.get(f"/v1/memory/sessions/{session['session_id']}")
    assert loaded.status_code == 200
    assert loaded.json()["session"]["history"][0]["text"] == "检查泵体划痕"

    deleted = client.delete(f"/v1/memory/sessions/{session['session_id']}")
    assert deleted.status_code == 200
    assert client.get(f"/v1/memory/sessions/{session['session_id']}").status_code == 404


def test_patchcore_prediction_uses_category_recommended_threshold(monkeypatch, tmp_path):
    captured = {}

    def fake_extract(heatmap, threshold, image_size):
        captured["threshold"] = threshold
        return []

    monkeypatch.setattr("app.tools.patchcore_detection.get_patchcore_artifacts", lambda category: type("Artifacts", (), {
        "memory_bank_path": tmp_path / "memory_bank.pt",
        "metadata_path": tmp_path / "metadata.json",
    })())
    monkeypatch.setattr("app.tools.patchcore_detection._build_feature_extractor", lambda *args, **kwargs: type("Extractor", (), {"to": lambda self, device: self})())
    monkeypatch.setattr("app.tools.patchcore_detection._load_image", lambda *args, **kwargs: (type("Image", (), {"width": 8, "height": 8, "convert": lambda self, mode: self})(), object()))
    monkeypatch.setattr("app.tools.patchcore_detection._extract_patch_embeddings", lambda *args, **kwargs: __import__("torch").ones(4, 2))
    monkeypatch.setattr("app.tools.patchcore_detection._score_embeddings", lambda *args, **kwargs: __import__("torch").ones(4))
    monkeypatch.setattr("app.tools.patchcore_detection._heatmap_from_scores", lambda *args, **kwargs: __import__("numpy").ones((8, 8)))
    monkeypatch.setattr("app.tools.patchcore_detection._extract_anomalies_from_heatmap", fake_extract)
    monkeypatch.setattr("app.tools.patchcore_detection._save_visualizations", lambda *args, **kwargs: {})
    monkeypatch.setattr("app.tools.patchcore_detection.torch.load", lambda *args, **kwargs: __import__("torch").ones(4, 2))

    (tmp_path / "memory_bank.pt").write_bytes(b"x")
    (tmp_path / "metadata.json").write_text('{"image_size": 8, "recommended_threshold": 0.87}', encoding="utf-8")

    predict_patchcore_image(tmp_path / "input.png", category="bottle", threshold=None, task_id="task")
    assert captured["threshold"] == 0.87
