from __future__ import annotations

from fastapi.testclient import TestClient

import app.api.main as api_main


class FakeRetriever:
    def format_for_prompt(self, rows):
        assert rows
        return "RAG similar cases:\n- bottle crack case"


class FakeRagService:
    retriever = FakeRetriever()

    def query_rows(self, query_text: str, category: str | None, top_k: int | None):
        assert query_text == "bottle rim crack"
        assert category == "bottle"
        assert top_k == 2
        return [
            {
                "id": "case-bottle-001",
                "description": "bottle rim crack with jagged edge",
                "distance": 0.17,
                "metadata": {
                    "source": "dataset",
                    "image_path": "data_sets/mvtec/bottle/test/crack/001.png",
                    "category": "bottle",
                    "split": "test",
                    "is_anomaly": True,
                    "anomaly_type": "crack",
                    "severity": "high",
                    "mask_path": "data_sets/mvtec/bottle/ground_truth/crack/001_mask.png",
                    "dataset_version": "mvtec-ad-local",
                },
            }
        ]


def test_rag_query_preserves_structured_source_metadata(monkeypatch):
    monkeypatch.setattr(api_main, "get_rag_service", lambda: FakeRagService())
    client = TestClient(api_main.app)

    response = client.post(
        "/v1/rag/query",
        json={"query_text": "bottle rim crack", "category": "bottle", "top_k": 2},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 1
    item = body["results"][0]
    assert item["id"] == "case-bottle-001"
    assert item["metadata"]["source"] == "dataset"
    assert item["metadata"]["category"] == "bottle"
    assert item["metadata"]["anomaly_type"] == "crack"
    assert item["metadata"]["dataset_version"] == "mvtec-ad-local"
    assert "prompt_context" in body
