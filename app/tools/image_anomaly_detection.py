from __future__ import annotations

import base64
import json
import re
from typing import Any

from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI

from app.config.settings import settings
from app.exceptions.base import ConfigurationError, ModelError, ResponseParseError, ToolExecutionError
from app.schemas.detection import DetectionResult, DetectionTask, ToolResponse
from app.tools.anomaly_detection import BaseTool


class ImageAnomalyDetectionTool(BaseTool):
    name = "qwen3.5-plus_image_anomaly_detection"

    async def run(self, task: DetectionTask) -> ToolResponse:
        """
        qwen3.5-plus based image anomaly detection.

        Expected inputs (in task / task.parameters):
        - task.question: optional user question
        - task.parameters.image_base64: base64-encoded image bytes
        - task.parameters.image_mime: optional mime type (default: image/jpeg)
        - task.parameters.detector_params: optional dict (thresholds, labels, etc.)

        TODO: Replace this tool with a local CV pipeline:
        - decode image bytes -> run local model -> return structured anomalies
        - keep the same output schema (anomalies list) to avoid downstream changes
        """
        image_b64 = (task.parameters or {}).get("image_base64")
        if not image_b64:
            raise ToolExecutionError(self.name, {"task_id": task.task_id}, ValueError("image_base64 missing"))

        if not settings.openai_api_key:
            raise ConfigurationError("openai_api_key not configured", config_key="APP_OPENAI_API_KEY")

        mime = (task.parameters or {}).get("image_mime") or "image/jpeg"
        detector_params = (task.parameters or {}).get("detector_params") or {}

        try:
            # Best-effort validation: ensure base64 decodes.
            _ = base64.b64decode(image_b64, validate=True)
        except Exception as e:
            raise ToolExecutionError(self.name, {"task_id": task.task_id}, e)

        data_url = f"data:{mime};base64,{image_b64}"

        system_hint = (
            "你是工业设备图像异常检测专家。"
            "你需要从图片中识别可能的异常现象，并以严格 JSON 返回。"
            "只输出 JSON，不要输出任何额外文本。"
        )
        user_prompt = {
            "task_id": task.task_id,
            "asset_id": task.asset_id,
            "time_range": {"start": task.start_time, "end": task.end_time},
            "question": task.question,
            "detector_params": detector_params,
            "output_schema": {
                "status": "success|failed",
                "anomalies": [
                    {
                        "type": "string",
                        "score": "0..1",
                        "details": "string",
                        "bbox": "[x1,y1,x2,y2] optional",
                    }
                ],
                "observations": "string optional",
            },
        }

        llm = ChatOpenAI(
            model=settings.llm_vision_model,
            temperature=0.1,
            api_key=settings.openai_api_key,
            timeout=settings.llm_timeout,
            max_tokens=settings.llm_max_tokens,
            base_url=settings.llm_base_url,
            extra_body={"enable_thinking": False},
        )

        message = HumanMessage(
            content=[
                {"type": "text", "text": system_hint + "\n" + json.dumps(user_prompt, ensure_ascii=False)},
                {"type": "image_url", "image_url": {"url": data_url}},
            ]
        )

        try:
            response = await llm.ainvoke([message])
        except Exception as e:
            raise ModelError(
                message=f"Vision model invocation failed: {str(e)}",
                model_name=settings.llm_vision_model,
                original_error=e,
            )

        raw = getattr(response, "content", None) or str(response)
        parsed = _extract_json(raw)

        if not isinstance(parsed, dict):
            raise ResponseParseError("Vision model response is not JSON object", raw_response=raw)

        anomalies = parsed.get("anomalies") or []
        if not isinstance(anomalies, list):
            raise ResponseParseError("Vision model anomalies is not a list", raw_response=raw)

        result = DetectionResult(
            task_id=task.task_id,
            status=parsed.get("status", "success"),
            anomalies=anomalies,
            summary=None,
            metadata={
                "tool": self.name,
                "vision_model": settings.llm_vision_model,
                "observations": parsed.get("observations"),
            },
        )
        return ToolResponse(tool_name=self.name, success=True, result=result)


_JSON_RE = re.compile(r"\{[\s\S]*\}")


def _extract_json(text: str) -> Any:
    text = text.strip()
    try:
        return json.loads(text)
    except Exception:
        pass

    match = _JSON_RE.search(text)
    if not match:
        return None

    try:
        return json.loads(match.group(0))
    except Exception:
        return None

