from __future__ import annotations

from fastapi.testclient import TestClient

import app.api.main as api_main
from app.services.industrial_runtime import industrial_store


def test_system_health_exposes_product_runtime_components(tmp_path):
    industrial_store.reset_for_tests(tmp_path / "industrial_state.json")
    client = TestClient(api_main.app)

    response = client.get("/v1/system/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["components"]["api"]["status"] == "ok"
    assert "rag" in payload["components"]
    assert "patchcore" in payload["components"]
    assert "grad_sidecar" in payload["components"]
    assert "security" in payload["components"]
    assert payload["metrics"]["task_count"] == 0
    assert "X-Trace-Id" in response.headers


def test_system_health_openapi_uses_structured_schema():
    client = TestClient(api_main.app)

    response = client.get("/openapi.json")

    assert response.status_code == 200
    schema = response.json()
    health_response = schema["paths"]["/v1/system/health"]["get"]["responses"]["200"]
    assert (
        health_response["content"]["application/json"]["schema"]["$ref"]
        == "#/components/schemas/SystemHealthResponse"
    )
    assert "RuntimeMetrics" in schema["components"]["schemas"]
