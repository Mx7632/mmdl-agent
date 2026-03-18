# API 路由、中间件与异常转换测试。
"""
API 路由测试
测试 app/api/main.py 中的 HTTP 端点、中间件与异常转换
"""

import pytest
from fastapi.testclient import TestClient
from app.api.main import app
from app.exceptions.base import AppError


@pytest.fixture
def client():
    """FastAPI 测试客户端"""
    return TestClient(app)


class TestRootEndpoint:
    """测试根路由 GET /"""

    def test_root_returns_welcome_info(self, client):
        """GET / 返回欢迎信息"""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        
        # 验证返回字段
        assert "app" in data
        assert "version" in data
        assert "message" in data
        assert "docs" in data
        assert "openapi_schema" in data
        
        # 验证具体值
        assert data["app"] == "industrial-anomaly-agent"
        assert data["version"] == "0.1.0"
        assert data["message"] == "Welcome to MMDL-Agent"
        assert data["docs"] == "/docs"

    def test_root_content_type(self, client):
        """验证响应内容类型"""
        response = client.get("/")
        assert response.headers["content-type"] == "application/json"


class TestMiddleware:
    """测试中间件功能"""

    def test_trace_id_header_added_to_response(self, client):
        """验证 trace_id 被添加到响应头"""
        response = client.get("/")
        assert response.status_code == 200
        assert "X-Trace-Id" in response.headers

    def test_trace_id_is_unique_per_request(self, client):
        """未提供 trace_id 时应为每次请求生成新的值"""
        response_1 = client.get("/")
        response_2 = client.get("/")

        assert response_1.status_code == 200
        assert response_2.status_code == 200
        assert response_1.headers.get("X-Trace-Id")
        assert response_2.headers.get("X-Trace-Id")
        assert response_1.headers["X-Trace-Id"] != response_2.headers["X-Trace-Id"]

    def test_trace_id_echoes_request_header(self, client):
        """客户端提供 trace_id 时应原样回传"""
        response = client.get("/", headers={"X-Trace-Id": "trace-test-001"})
        assert response.status_code == 200
        assert response.headers.get("X-Trace-Id") == "trace-test-001"


class TestDetectionEndpoint:
    """测试异常检测端点 POST /v1/detect"""

    def test_detection_request_validation_missing_fields(self, client):
        """缺少必需字段导致验证失败"""
        response = client.post("/v1/detect", json={})
        assert response.status_code == 422

    def test_detection_request_validation_invalid_type(self, client):
        """字段类型不匹配"""
        payload = {
            "task_id": "test-001",
            "asset_id": "asset-001",
            "start_time": "2025-01-01T00:00:00Z",
            "end_time": "2025-01-01T01:00:00Z",
            "parameters": "not-a-dict",
        }
        response = client.post("/v1/detect", json=payload)
        assert response.status_code == 422

    def test_detection_request_with_valid_payload(self, client):
        """发送有效的检测请求"""
        payload = {
            "task_id": "test-001",
            "asset_id": "asset-001",
            "start_time": "2025-01-01T00:00:00Z",
            "end_time": "2025-01-01T01:00:00Z",
            "data_source": "mock",
            "parameters": {"threshold": 0.5, "data": [1.0, 2.0, 3.0]},
        }
        response = client.post("/v1/detect", json=payload)
        assert response.status_code == 200

    def test_detection_response_contains_required_fields(self, client):
        """验证响应包含必需字段"""
        payload = {
            "task_id": "test-002",
            "asset_id": "asset-002",
            "start_time": "2025-01-01T00:00:00Z",
            "end_time": "2025-01-01T01:00:00Z",
            "parameters": {"threshold": 0.5, "data": [1.0, 2.0]},
        }
        response = client.post("/v1/detect", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "task_id" in data
        assert "status" in data
        assert data["status"] in ["success", "failed"]


class TestExceptionHandling:
    """测试全局异常处理"""

    def test_app_error_conversion_to_json_response(self, client):
        """AppError 被转换为 JSON 响应"""
        app.add_api_route("/test-error", lambda: (_ for _ in ()).throw(AppError("Test error")), methods=["GET"])

        response = client.get("/test-error")
        assert response.status_code == 500
        data = response.json()
        assert data["code"] == "app_error"
        assert data["message"] == "Test error"
        assert "trace_id" in data


class TestContentNegotiation:
    """测试内容协商"""

    def test_response_json_format(self, client):
        """验证响应是 JSON 格式"""
        response = client.get("/")
        # 如果响应是有效的 JSON，这不会抛出异常
        data = response.json()
        assert isinstance(data, dict)


class TestRouteNotFound:
    """测试不存在的路由"""

    def test_404_for_undefined_route(self, client):
        """访问未定义的路由返回 404"""
        response = client.get("/undefined-route")
        assert response.status_code == 404


class TestHttpMethods:
    """测试 HTTP 方法"""

    def test_put_to_root_endpoint_not_allowed(self, client):
        """根路由不支持 PUT"""
        response = client.put("/")
        assert response.status_code == 405  # Method Not Allowed

