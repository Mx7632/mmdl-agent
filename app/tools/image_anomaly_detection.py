from __future__ import annotations

import base64
import io
import json
import re
from typing import Any

import httpx
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from PIL import Image
from pydantic import SecretStr

from app.config.settings import settings
from app.exceptions.base import (
    ConfigurationError,
    ExternalServiceError,
    ModelError,
    ResponseParseError,
    ToolExecutionError,
)
from app.schemas.detection import DetectionResult, DetectionTask, ToolResponse
from app.tools.anomaly_detection import BaseTool
from app.tools.patchcore_detection import LocalPatchCoreImageAnomalyDetectionTool

QWEN_BACKEND = "qwen"
SPECIALIST_BACKEND = "specialist"
PATCHCORE_BACKEND = "patchcore"

_JSON_RE = re.compile(r"\{[\s\S]*\}")
_UNCERTAIN_ANOMALY_RE = re.compile(
    r"\b(possible|maybe|uncertain|slight|minor|weak|reflection|shadow|edge|texture|noise)\b"
    r"|可能|疑似|不确定|轻微|较弱|反光|阴影|边缘|纹理|噪声"
)
_QWEN_ALIASES = {"qwen", "qwen_vl", "qwen3_5_plus", "qwen3.5_plus"}
_PATCHCORE_ALIASES = {"patchcore", "patch_core"}
_SPECIALIST_ALIASES = {
    "anomalygpt",
    "anomaly_gpt",
    "specialist",
    "specialist_http",
    "specialisthttp",
    "professional",
}


def _normalize_detector_name(value: str | None) -> str:
    return (value or "").strip().lower().replace("-", "_").replace(" ", "")


def _configured_specialist_aliases() -> set[str]:
    aliases = set(_SPECIALIST_ALIASES)
    configured = (settings.professional_vision_detector_aliases or "").split(",")
    aliases.update(_normalize_detector_name(item) for item in configured if item.strip())
    aliases.add(_normalize_detector_name(settings.professional_vision_detector_type))
    return {alias for alias in aliases if alias}


def resolve_visual_backend(tool_type: str | None) -> str:
    requested = _normalize_detector_name(tool_type)
    default_backend = _normalize_detector_name(settings.vision_detector_backend) or QWEN_BACKEND
    specialist_aliases = _configured_specialist_aliases()
    patchcore_aliases = {
        alias
        for alias in (_normalize_detector_name(item) for item in settings.patchcore_detector_aliases.split(","))
        if alias
    } | _PATCHCORE_ALIASES

    if requested in specialist_aliases or requested.startswith("anomaly"):
        return SPECIALIST_BACKEND
    if requested in patchcore_aliases or requested.startswith("patchcore"):
        return PATCHCORE_BACKEND
    if requested in _QWEN_ALIASES or requested.startswith("qwen"):
        return QWEN_BACKEND

    if default_backend in specialist_aliases or default_backend in {
        SPECIALIST_BACKEND,
        "specialist_http",
        "professional",
    }:
        return SPECIALIST_BACKEND
    if default_backend in patchcore_aliases or default_backend == PATCHCORE_BACKEND:
        return PATCHCORE_BACKEND
    return QWEN_BACKEND


def _decode_image_size(image_b64: str) -> tuple[int, int] | None:
    try:
        image_bytes = base64.b64decode(image_b64, validate=True)
        with Image.open(io.BytesIO(image_bytes)) as image:
            return int(image.width), int(image.height)
    except Exception:
        return None


def _normalize_bbox(raw_bbox: Any, image_size: tuple[int, int] | None) -> list[int] | None:
    values: list[float]
    if isinstance(raw_bbox, dict):
        ordered = [raw_bbox.get("x1"), raw_bbox.get("y1"), raw_bbox.get("x2"), raw_bbox.get("y2")]
        if any(value is None for value in ordered):
            return None
        values = [float(value) for value in ordered]
    elif isinstance(raw_bbox, (list, tuple)) and len(raw_bbox) == 4:
        try:
            values = [float(value) for value in raw_bbox]
        except Exception:
            return None
    else:
        return None

    x1, y1, x2, y2 = values
    if image_size:
        width, height = image_size
        x1 = min(max(x1, 0.0), width)
        x2 = min(max(x2, 0.0), width)
        y1 = min(max(y1, 0.0), height)
        y2 = min(max(y2, 0.0), height)

    if x2 < x1:
        x1, x2 = x2, x1
    if y2 < y1:
        y1, y2 = y2, y1

    if x1 == x2 or y1 == y2:
        return None
    return [int(round(x1)), int(round(y1)), int(round(x2)), int(round(y2))]


def _derive_location_text(bbox: list[int] | None, image_size: tuple[int, int] | None) -> str | None:
    if not bbox or not image_size:
        return None

    width, height = image_size
    if width <= 0 or height <= 0:
        return None

    x1, y1, x2, y2 = bbox
    center_x = (x1 + x2) / 2
    center_y = (y1 + y2) / 2

    horizontal = "left" if center_x < width / 3 else "right" if center_x > (2 * width / 3) else "center"
    vertical = "top" if center_y < height / 3 else "bottom" if center_y > (2 * height / 3) else "middle"
    return f"{vertical}-{horizontal}"


def normalize_visual_anomalies(
    anomalies: list[Any],
    image_size: tuple[int, int] | None = None,
) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(anomalies):
        anomaly = dict(item) if isinstance(item, dict) else {"details": str(item)}
        bbox = _normalize_bbox(anomaly.get("bbox"), image_size)
        location = anomaly.get("location") or anomaly.get("region") or _derive_location_text(bbox, image_size)
        anomaly["bbox"] = bbox
        anomaly["location"] = location
        anomaly["has_localization"] = bool(bbox or location)
        anomaly.setdefault("type", f"anomaly_{index + 1}")
        normalized.append(anomaly)
    return normalized


def _coerce_score(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except Exception:
        return None


def filter_qwen_anomalies(
    anomalies: list[dict[str, Any]],
    *,
    min_score: float,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    kept: list[dict[str, Any]] = []
    filtered: list[dict[str, Any]] = []
    for anomaly in anomalies:
        score = _coerce_score(anomaly.get("score"))
        text = " ".join(
            str(anomaly.get(key, ""))
            for key in ("type", "details", "description", "appearance", "location")
        )
        reason = ""
        if score is None:
            reason = "missing_score"
        elif score < min_score:
            reason = f"score_below_{min_score:.2f}"
        elif _UNCERTAIN_ANOMALY_RE.search(text.lower()):
            reason = "uncertain_or_normal_texture"

        if reason:
            filtered.append({**anomaly, "filter_reason": reason})
        else:
            kept.append(anomaly)
    return kept, filtered


def _build_visual_prompt(task: DetectionTask, detector_params: dict[str, Any], image_size: tuple[int, int] | None) -> dict[str, Any]:
    localization_mode = bool((task.parameters or {}).get("require_localization"))
    width, height = image_size or (None, None)
    output_schema = {
        "status": "success|failed",
        "anomalies": [
            {
                "type": "string",
                "score": "0..1",
                "details": "string",
                "bbox": [0, 0, 100, 100],
                "location": "top-left|top-center|top-right|middle-left|middle-center|middle-right|bottom-left|bottom-center|bottom-right",
            }
        ],
        "observations": "string optional",
    }
    prompt = {
        "task_id": task.task_id,
        "asset_id": task.asset_id,
        "time_range": {"start": task.start_time, "end": task.end_time},
        "question": task.question,
        "detector_params": detector_params,
        "analysis_mode": "localization" if localization_mode else "detection",
        "image_size": {"width": width, "height": height},
        "requirements": [
            "Return JSON only.",
            "If the image appears normal, return anomalies as an empty list [].",
            "Do not force an anomaly. Normal product texture, expected edges, regular reflections, shadows, and imaging noise are not anomalies.",
            "Only include an anomaly when there is clear localized evidence that differs from normal reference appearance.",
            "For each anomaly, provide details and score. Use score >= 0.65 only for clear defects; use a lower score for weak or uncertain candidates.",
            "If location can be inferred, provide pixel bbox [x1,y1,x2,y2] based on original image size.",
            "Also provide a coarse location string such as top-left or middle-right.",
        ],
        "normal_decision_policy": {
            "normal_output": {"status": "success", "anomalies": [], "observations": "no obvious visual anomaly"},
            "false_positive_controls": [
                "expected object boundaries",
                "regular texture",
                "specular reflection",
                "illumination shadow",
                "background contrast",
                "compression noise",
            ],
        },
        "output_schema": output_schema,
    }
    few_shot_context = (task.parameters or {}).get("few_shot_context")
    few_shot_examples = (task.parameters or {}).get("few_shot_examples")
    if few_shot_context:
        prompt["few_shot_context"] = few_shot_context
        prompt["requirements"].append(
            "Use few-shot normal/anomaly references as calibration evidence. "
            "If the current image is closer to normal references than anomaly references, return anomalies: []."
        )
    if few_shot_examples:
        prompt["few_shot_examples"] = few_shot_examples
    return prompt


class QwenImageAnomalyDetectionTool(BaseTool):
    name = "qwen_image_anomaly_detection"

    async def run(self, task: DetectionTask) -> ToolResponse:
        image_b64 = (task.parameters or {}).get("image_base64")
        if not image_b64:
            raise ToolExecutionError(self.name, {"task_id": task.task_id}, ValueError("image_base64 missing"))

        if not settings.openai_api_key:
            raise ConfigurationError("openai_api_key not configured", config_key="APP_OPENAI_API_KEY")

        mime = (task.parameters or {}).get("image_mime") or "image/jpeg"
        detector_params = (task.parameters or {}).get("detector_params") or {}
        require_localization = bool((task.parameters or {}).get("require_localization"))

        try:
            base64.b64decode(image_b64, validate=True)
        except Exception as exc:
            raise ToolExecutionError(self.name, {"task_id": task.task_id}, exc) from exc

        data_url = f"data:{mime};base64,{image_b64}"
        image_size = _decode_image_size(image_b64)
        system_hint = (
            "You are an industrial visual anomaly inspector. "
            "Review the image carefully and return strict JSON only. "
            "When possible, locate each anomaly precisely."
        )
        if require_localization:
            system_hint += " The user specifically needs anomaly localization with approximate bounding boxes."
        user_prompt = _build_visual_prompt(task, detector_params, image_size)

        llm = ChatOpenAI(
            model=settings.llm_vision_model,
            temperature=0.1,
            api_key=SecretStr(settings.openai_api_key),
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
        except Exception as exc:
            raise ModelError(
                message=f"Vision model invocation failed: {str(exc)}",
                model_name=settings.llm_vision_model,
                original_error=exc,
            ) from exc

        raw = getattr(response, "content", None) or str(response)
        parsed = _extract_json(raw)
        if not isinstance(parsed, dict):
            raise ResponseParseError("Vision model response is not JSON object", raw_response=raw)

        anomalies = parsed.get("anomalies") or []
        if not isinstance(anomalies, list):
            raise ResponseParseError("Vision model anomalies is not a list", raw_response=raw)
        anomalies = normalize_visual_anomalies(anomalies, image_size=image_size)
        min_score = float(detector_params.get("qwen_min_anomaly_score", settings.qwen_min_anomaly_score))
        raw_anomaly_count = len(anomalies)
        anomalies, filtered_anomalies = filter_qwen_anomalies(anomalies, min_score=min_score)

        result = DetectionResult(
            task_id=task.task_id,
            status=parsed.get("status", "success"),
            anomalies=anomalies,
            summary=None,
            metadata={
                "tool": self.name,
                "vision_model": settings.llm_vision_model,
                "observations": parsed.get("observations"),
                "image_size": image_size,
                "raw_anomaly_count": raw_anomaly_count,
                "filtered_anomaly_count": len(filtered_anomalies),
                "qwen_min_anomaly_score": min_score,
                "filtered_anomalies": filtered_anomalies[:5],
                "localization_available": any(item.get("has_localization") for item in anomalies),
                "analysis_mode": "localization" if require_localization else "detection",
                "few_shot_examples": (task.parameters or {}).get("few_shot_examples") or {},
                "few_shot_context": (task.parameters or {}).get("few_shot_context") or "",
            },
        )
        return ToolResponse(tool_name=self.name, success=True, result=result)


class HttpProfessionalImageAnomalyDetectionTool(BaseTool):
    name = "professional_image_anomaly_detection"

    async def run(self, task: DetectionTask) -> ToolResponse:
        image_b64 = (task.parameters or {}).get("image_base64")
        if not image_b64:
            raise ToolExecutionError(self.name, {"task_id": task.task_id}, ValueError("image_base64 missing"))

        service_url = (settings.professional_vision_detector_url or "").strip()
        if not service_url:
            raise ConfigurationError(
                "professional vision detector url not configured",
                config_key="APP_PROFESSIONAL_VISION_DETECTOR_URL",
            )

        mime = (task.parameters or {}).get("image_mime") or "image/jpeg"
        detector_type = (
            (task.parameters or {}).get("tool_type")
            or settings.professional_vision_detector_type
            or "anomalygpt"
        )
        detector_params = (task.parameters or {}).get("detector_params") or {}

        try:
            base64.b64decode(image_b64, validate=True)
        except Exception as exc:
            raise ToolExecutionError(self.name, {"task_id": task.task_id}, exc) from exc

        payload = {
            "task_id": task.task_id,
            "asset_id": task.asset_id,
            "start_time": task.start_time,
            "end_time": task.end_time,
            "question": task.question,
            "image_base64": image_b64,
            "image_mime": mime,
            "detector_type": detector_type,
            "detector_params": detector_params,
            "parameters": task.parameters,
        }

        try:
            async with httpx.AsyncClient(timeout=settings.professional_vision_detector_timeout) as client:
                response = await client.post(
                    service_url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                )
                response.raise_for_status()
                result_data = response.json()
        except httpx.HTTPStatusError as exc:
            raise ExternalServiceError(
                message=f"Professional detector returned {exc.response.status_code}",
                details={"url": service_url, "status_code": exc.response.status_code},
                original_error=exc,
            ) from exc
        except httpx.RequestError as exc:
            raise ExternalServiceError(
                message="Failed to connect to professional vision detector",
                details={"url": service_url},
                original_error=exc,
            ) from exc
        except Exception as exc:
            raise ToolExecutionError(self.name, {"task_id": task.task_id}, exc) from exc

        parsed = result_data.get("result") if isinstance(result_data, dict) else None
        if parsed is None:
            parsed = result_data

        if not isinstance(parsed, dict):
            raise ResponseParseError(
                "Professional detector response is not JSON object",
                raw_response=result_data,
            )

        anomalies = parsed.get("anomalies") or parsed.get("predictions") or []
        if not isinstance(anomalies, list):
            raise ResponseParseError(
                "Professional detector anomalies is not a list",
                raw_response=result_data,
            )
        image_size = _decode_image_size(image_b64)
        anomalies = normalize_visual_anomalies(anomalies, image_size=image_size)

        metadata = dict(parsed.get("metadata") or {})
        metadata.update(
            {
                "tool": self.name,
                "detector_type": detector_type,
                "service_url": service_url,
                "image_size": image_size,
                "localization_available": any(item.get("has_localization") for item in anomalies),
                "analysis_mode": "localization" if (task.parameters or {}).get("require_localization") else "detection",
            }
        )

        result = DetectionResult(
            task_id=parsed.get("task_id", task.task_id),
            status=parsed.get("status", "success"),
            answer=parsed.get("answer"),
            anomalies=anomalies,
            summary=parsed.get("summary"),
            metadata=metadata,
        )
        return ToolResponse(tool_name=self.name, success=True, result=result)


class ImageAnomalyDetectionTool(BaseTool):
    name = "image_anomaly_detection"

    def __init__(
        self,
        qwen_tool: BaseTool | None = None,
        specialist_tool: BaseTool | None = None,
        patchcore_tool: BaseTool | None = None,
    ) -> None:
        self.qwen_tool = qwen_tool or QwenImageAnomalyDetectionTool()
        self.specialist_tool = specialist_tool or HttpProfessionalImageAnomalyDetectionTool()
        self.patchcore_tool = patchcore_tool or LocalPatchCoreImageAnomalyDetectionTool()

    async def run(self, task: DetectionTask) -> ToolResponse:
        tool_type = (task.parameters or {}).get("tool_type")
        backend = resolve_visual_backend(tool_type)
        if backend == SPECIALIST_BACKEND:
            selected_tool = self.specialist_tool
        elif backend == PATCHCORE_BACKEND:
            selected_tool = self.patchcore_tool
        else:
            selected_tool = self.qwen_tool
        response = await selected_tool.run(task)

        if response.result:
            response.result.metadata.setdefault("requested_tool_type", tool_type or settings.vision_detector_backend)
            response.result.metadata.setdefault("selected_backend", backend)
        response.tool_name = selected_tool.name
        return response


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
