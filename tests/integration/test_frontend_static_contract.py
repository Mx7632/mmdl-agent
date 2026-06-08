from __future__ import annotations

from fastapi.testclient import TestClient

import app.api.main as api_main


def test_frontend_workspace_is_mounted_with_product_workflow_markers() -> None:
    client = TestClient(api_main.app)

    response = client.get("/web/index.html")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    html = response.text
    assert "<title>MMDL-Agent</title>" in html
    assert "/v1/system/health" in html
    assert "/v1/stream" in html
    assert "/v1/generate_report" in html
    assert 'data-report-action="copy"' in html
    assert 'data-report-action="download"' in html
    assert 'id="timeline-steps"' in html
    assert 'id="rag-results"' in html
    assert 'id="industrial-summary"' in html


def test_frontend_workspace_exposes_detector_and_failure_state_controls() -> None:
    client = TestClient(api_main.app)

    response = client.get("/web/index.html")

    assert response.status_code == 200
    html = response.text
    assert 'id="visual-backend"' in html
    assert 'value="qwen"' in html
    assert 'value="patchcore"' in html
    assert 'id="patchcore-status"' in html
    assert "PatchCore 类别" in html
    assert "检测失败" in html
    assert "报告生成失败" in html
