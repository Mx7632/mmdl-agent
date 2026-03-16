from __future__ import annotations

import base64
import json
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config.settings import settings
from app.core.agent import build_graph
from app.exceptions.base import AppError, DataMissingError, ResponseParseError
from app.memory.state import DetectionState
from app.schemas.detection import DetectionResult, DetectionTask
from app.utils.logging import TRACE_ID_HEADER, new_trace_id, set_trace_id, setup_logger

app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logger = setup_logger(level=settings.log_level)


@app.middleware("http")
async def add_trace_id(request: Request, call_next):
    trace_id = request.headers.get(TRACE_ID_HEADER) or new_trace_id()
    request.state.trace_id = trace_id
    set_trace_id(trace_id)

    response = await call_next(request)
    response.headers[TRACE_ID_HEADER] = trace_id
    return response


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    logger.error(f"{exc.code}: {exc.message}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": exc.code, "message": exc.message, "trace_id": request.state.trace_id},
    )


@app.get("/")
async def root():
    return {
        "app": settings.app_name,
        "version": "0.1.0",
        "message": "后端服务器已经启动成功",
        "docs": "/docs",
        "openapi_schema": "/openapi.json",
    }


@app.post("/v1/detect", response_model=DetectionResult)
async def detect(request: Request):
    """
    Create a detection task and run the workflow.

    Image-only:
    - multipart/form-data: image upload + question + params
    """
    content_type = (request.headers.get("content-type") or "").lower()

    if "multipart/form-data" not in content_type:
        raise DataMissingError("Only multipart/form-data is supported for /v1/detect (image mode)")

    form = await request.form()

    task_id = (form.get("task_id") or "").strip()
    asset_id = (form.get("asset_id") or "").strip()
    start_time = (form.get("start_time") or "").strip()
    end_time = (form.get("end_time") or "").strip()
    data_source = (form.get("data_source") or None)
    question = (form.get("question") or None)

    if not task_id or not asset_id or not start_time or not end_time:
        raise DataMissingError("task_id/asset_id/start_time/end_time are required for image detection")

    raw_parameters = form.get("parameters") or "{}"
    try:
        parameters: dict[str, Any]
        if isinstance(raw_parameters, str):
            parameters = json.loads(raw_parameters) if raw_parameters else {}
        elif isinstance(raw_parameters, dict):
            parameters = raw_parameters
        else:
            parameters = {}
    except Exception as e:
        raise ResponseParseError(
            "parameters must be valid JSON string",
            raw_response=raw_parameters,
            original_error=e,
        )

    upload = form.get("image")
    if upload is None:
        raise DataMissingError("image file is required for image detection")

    image_bytes = await upload.read()
    image_b64 = base64.b64encode(image_bytes).decode("ascii")

    parameters = dict(parameters or {})
    parameters.setdefault("tool_type", "qwen3.5-plus")
    parameters["image_base64"] = image_b64
    parameters["image_mime"] = getattr(upload, "content_type", None) or "image/jpeg"

    task = DetectionTask(
        task_id=task_id,
        asset_id=asset_id,
        start_time=start_time,
        end_time=end_time,
        data_source=data_source,
        input_type="image",
        question=question,
        parameters=parameters,
    )

    graph = build_graph()
    state = DetectionState(task=task)
    result_state = await graph.ainvoke(state)

    if isinstance(result_state, dict):
        result = result_state.get("result")
    else:
        result = getattr(result_state, "result", None)

    if result:
        return result

    return DetectionResult(task_id=task.task_id, status="failed", anomalies=[])
