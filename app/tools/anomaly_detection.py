# TODO 异常检测工具接口，需补充真实工具接口
from __future__ import annotations

import httpx
from app.config.settings import settings
from app.exceptions.base import ExternalServiceError, ToolExecutionError
from app.schemas.detection import DetectionResult, DetectionTask, ToolResponse

# 抽象基类，所有的工具都必须有一个name和一个run方法
class BaseTool:
    name: str = "base_tool"

    async def run(self, task: DetectionTask) -> ToolResponse:
        """执行工具逻辑并返回标签 ToolResponse"""
        raise NotImplementedError


class HttpAnomalyDetectionTool(BaseTool):
    name = "http_anomaly_detection"
    
    async def run(self, task: DetectionTask) -> ToolResponse:
        """
        通过 HTTP 调用外部异常检测服务。

        """
        service_url = getattr(settings, "anomaly_detection_url", "") or ""

        timeout = getattr(settings, "anomaly_detection_timeout", 30.0)

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                payload = {
                    "task_id": task.task_id,
                    "asset_id": task.asset_id,
                    "start_time": task.start_time,
                    "end_time": task.end_time,
                    "data_source": task.data_source,
                    # 约定：前端已将数据放入 parameters.data
                    "data": task.parameters.get("data", []),
                    "parameters": task.parameters,
                }

                response = await client.post(
                    f"{service_url}/detect",
                    json=payload,
                    headers={"Content-Type": "application/json"},
                )
                response.raise_for_status()

                result_data = response.json()
                result = DetectionResult(
                    task_id=result_data.get("task_id", task.task_id),
                    status=result_data.get("status", "success"),
                    anomalies=result_data.get("anomalies", []),
                    summary=result_data.get("summary"),
                    metadata=result_data.get("metadata", {}),
                )

                return ToolResponse(tool_name=self.name, success=True, result=result)

        except httpx.HTTPStatusError as e:
            raise ExternalServiceError(
                message=f"HTTP service returned {e.response.status_code}",
                details={"url": service_url, "status_code": e.response.status_code},
                original_error=e,
            )
        except httpx.RequestError as e:
            raise ExternalServiceError(
                message="Failed to connect to anomaly detection service",
                details={"url": service_url},
                original_error=e,
            )
        except Exception as e:
            raise ToolExecutionError(
                tool_name=self.name,
                arguments={"task_id": task.task_id},
                error=e,
            )