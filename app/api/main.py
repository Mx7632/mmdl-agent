from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.datastructures import UploadFile as StarletteUploadFile

from app.config.settings import settings
from app.core.agent import build_graph
from app.core.qa_agent import build_qa_graph
from app.exceptions.base import AppError, DataMissingError, ResponseParseError
from app.memory.state import DetectionState
from app.rag.service import get_rag_service
from app.schemas.chat import ChatRequest, ChatResponse
from app.schemas.detection import (
    DetectionResult,
    DetectionTask,
    RagBuildRequest,
    RagBuildResponse,
    RagBuildStartResponse,
    RagBuildStatusResponse,
    RagGenerateDescriptionsRequest,
    RagGenerateDescriptionsResponse,
    RagImageQueryRequest,
    RagIngestFeedbackRequest,
    RagIngestFeedbackResponse,
    RagQueryItem,
    RagQueryRequest,
    RagQueryResponse,
)
from app.utils.logging import TRACE_ID_HEADER, new_trace_id, set_trace_id, setup_logger

app = FastAPI(
    title=settings.app_name,
    docs_url=None,
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logger = setup_logger(level=settings.log_level)


_SWAGGER_STATIC_ROUTE = "/_swagger_static"
_swagger_local_assets_ok = False


def _mount_local_swagger_assets() -> None:
    """Mount local swagger UI static assets if available."""
    global _swagger_local_assets_ok

    try:
        import swagger_ui_bundle  # type: ignore

        swagger_pkg_dir = Path(swagger_ui_bundle.__file__).resolve().parent
        swagger_vendor_candidates = sorted((swagger_pkg_dir / "vendor").glob("swagger-ui-*"))
        if not swagger_vendor_candidates:
            raise FileNotFoundError(f"No swagger-ui vendor assets found under {swagger_pkg_dir / 'vendor'}")
        swagger_assets_dir = swagger_vendor_candidates[-1]
        app.mount(_SWAGGER_STATIC_ROUTE, StaticFiles(directory=str(swagger_assets_dir)), name="swagger_static")
        _swagger_local_assets_ok = True
        logger.info("Mounted local Swagger assets from %s", swagger_assets_dir)
    except Exception as exc:  # pragma: no cover
        _swagger_local_assets_ok = False
        logger.warning("Local Swagger assets unavailable, fallback to default CDN docs: %s", exc)


_mount_local_swagger_assets()


def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(
        title=settings.app_name,
        version="0.1.0",
        description="Industrial anomaly detection API",
        routes=app.routes,
    )
    schema["openapi"] = "3.0.3"
    app.openapi_schema = schema
    return app.openapi_schema


app.openapi = custom_openapi


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


@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    if _swagger_local_assets_ok:
        return get_swagger_ui_html(
            openapi_url=app.openapi_url,
            title=f"{settings.app_name} - Swagger UI",
            swagger_js_url=f"{_SWAGGER_STATIC_ROUTE}/swagger-ui-bundle.js",
            swagger_css_url=f"{_SWAGGER_STATIC_ROUTE}/swagger-ui.css",
            swagger_favicon_url=f"{_SWAGGER_STATIC_ROUTE}/favicon-32x32.png",
        )

    return get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title=f"{settings.app_name} - Swagger UI",
    )


@app.post("/v1/rag/build", response_model=RagBuildResponse)
async def rag_build(payload: RagBuildRequest) -> RagBuildResponse:
    service = get_rag_service()
    result = service.build_from_dataset(
        dataset_root=payload.dataset_root,
        include_normal=payload.include_normal,
    )
    return RagBuildResponse(status="success", **result)


@app.post("/v1/rag/generate-descriptions", response_model=RagGenerateDescriptionsResponse)
async def rag_generate_descriptions(payload: RagGenerateDescriptionsRequest) -> RagGenerateDescriptionsResponse:
    service = get_rag_service()
    result = service.generate_anomaly_descriptions(
        dataset_root=payload.dataset_root,
        output_path=payload.output_path,
        incremental=payload.incremental,
    )
    return RagGenerateDescriptionsResponse(status="success", **result)


@app.post("/v1/rag/build/start", response_model=RagBuildStartResponse)
async def rag_build_start(payload: RagBuildRequest) -> RagBuildStartResponse:
    service = get_rag_service()
    task_id = service.start_build_job(
        dataset_root=payload.dataset_root,
        include_normal=payload.include_normal,
    )
    return RagBuildStartResponse(status="success", task_id=task_id, message="建库任务已启动")


@app.get("/v1/rag/build/status/{task_id}", response_model=RagBuildStatusResponse)
async def rag_build_status(task_id: str) -> RagBuildStatusResponse:
    service = get_rag_service()
    status = service.get_build_job_status(task_id)
    if not status:
        return RagBuildStatusResponse(
            status="not_found",
            task_id=task_id,
            phase="unknown",
            percent=0,
            message="任务不存在",
        )

    return RagBuildStatusResponse(**status)


@app.post("/v1/rag/query", response_model=RagQueryResponse)
async def rag_query(payload: RagQueryRequest) -> RagQueryResponse:
    service = get_rag_service()
    rows = service.query_rows(
        query_text=payload.query_text,
        category=payload.category,
        top_k=payload.top_k,
    )
    prompt_context = service.retriever.format_for_prompt(rows)
    items = [RagQueryItem(**row) for row in rows]
    return RagQueryResponse(
        status="success",
        count=len(items),
        results=items,
        prompt_context=prompt_context,
    )


@app.post("/v1/rag/query-image", response_model=RagQueryResponse)
async def rag_query_image(payload: RagImageQueryRequest) -> RagQueryResponse:
    service = get_rag_service()
    rows = service.query_rows_by_image(
        image_path=payload.image_path,
        category=payload.category,
        top_k=payload.top_k,
    )
    prompt_context = service.retriever.format_for_prompt(rows)
    items = [RagQueryItem(**row) for row in rows]
    return RagQueryResponse(
        status="success",
        count=len(items),
        results=items,
        prompt_context=prompt_context,
    )


@app.post("/v1/rag/ingest-feedback", response_model=RagIngestFeedbackResponse)
async def rag_ingest_feedback(payload: RagIngestFeedbackRequest) -> RagIngestFeedbackResponse:
    service = get_rag_service()
    accepted = service.add_online_case(
        image_path=payload.image_path,
        category=payload.category,
        user_description=payload.user_description,
        model_confidence=payload.model_confidence,
        is_anomaly=payload.is_anomaly,
        anomaly_type=payload.anomaly_type,
        severity=payload.severity,
    )

    return RagIngestFeedbackResponse(
        status="success",
        accepted=accepted,
        learning_threshold=settings.rag_learning_threshold,
        message=("样本已写入向量库" if accepted else "置信度低于阈值，已跳过写入"),
    )


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

    def get_form_text(key: str) -> str:
        value = form.get(key)
        return value if isinstance(value, str) else ""

    task_id = get_form_text("task_id").strip()
    asset_id = get_form_text("asset_id").strip()
    start_time = get_form_text("start_time").strip()
    end_time = get_form_text("end_time").strip()
    data_source = get_form_text("data_source").strip() or None
    question = get_form_text("question").strip() or None

    if not task_id or not asset_id or not start_time or not end_time:
        raise DataMissingError("task_id/asset_id/start_time/end_time are required for image detection")

    raw_parameters = form.get("parameters")
    try:
        parameters: dict[str, Any]
        if raw_parameters is None:
            parameters = {}
        elif isinstance(raw_parameters, str):
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
    if not isinstance(upload, StarletteUploadFile) or not getattr(upload, "filename", None):
        raise DataMissingError("image file is required for image detection")

    image_bytes = await upload.read()
    image_b64 = base64.b64encode(image_bytes).decode("ascii")

    suffix = Path(upload.filename or "uploaded_image.jpg").suffix or ".jpg"
    upload_cache_dir = Path("data/uploads")
    upload_cache_dir.mkdir(parents=True, exist_ok=True)
    cached_image_path = upload_cache_dir / f"{task_id}{suffix}"
    cached_image_path.write_bytes(image_bytes)

    parameters = dict(parameters or {})
    parameters.setdefault("tool_type", "qwen3.5-plus")
    parameters["image_base64"] = image_b64
    parameters["image_mime"] = getattr(upload, "content_type", None) or "image/jpeg"
    parameters.setdefault("image_path", str(cached_image_path))
    form_category = get_form_text("category").strip()
    if form_category:
        parameters.setdefault("category", form_category)

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


@app.post("/v1/chat", response_model=ChatResponse)
async def chat(request: Request):
    """
    Autonomous Q&A endpoint with automatic planning and RAG.
    Supports multipart/form-data with 'image' and 'question'.
    """
    content_type = (request.headers.get("content-type") or "").lower()
    if "multipart/form-data" not in content_type:
        # Also support JSON if no image is provided
        try:
            body = await request.json()
            chat_req = ChatRequest(**body)
        except Exception:
            raise DataMissingError("Only multipart/form-data or valid JSON is supported for /v1/chat")
    else:
        form = await request.form()
        
        def get_form_text(key: str) -> str:
            value = form.get(key)
            return value if isinstance(value, str) else ""

        task_id = get_form_text("task_id").strip() or f"chat-{new_trace_id()}"
        question = get_form_text("question").strip()
        category = get_form_text("category").strip() or None
        
        if not question:
            raise DataMissingError("question is required")

        image_b64 = None
        image_mime = None
        upload = form.get("image")
        
        parameters = {}
        raw_params = form.get("parameters")
        if raw_params:
            try:
                parameters = json.loads(raw_params) if isinstance(raw_params, str) else raw_params
            except Exception:
                pass

        if isinstance(upload, StarletteUploadFile) and getattr(upload, "filename", None):
            image_bytes = await upload.read()
            image_b64 = base64.b64encode(image_bytes).decode("ascii")
            image_mime = getattr(upload, "content_type", "image/jpeg")
            
            # 缓存图片供 RAG 使用
            upload_cache_dir = Path("data/uploads")
            upload_cache_dir.mkdir(parents=True, exist_ok=True)
            cached_path = upload_cache_dir / f"{task_id}{Path(upload.filename).suffix or '.jpg'}"
            cached_path.write_bytes(image_bytes)
            parameters["image_path"] = str(cached_path)

        chat_req = ChatRequest(
            task_id=task_id,
            question=question,
            image_base64=image_b64,
            image_mime=image_mime,
            category=category,
            parameters=parameters
        )

    graph = build_qa_graph()
    initial_state = {
        "request": chat_req,
        "steps": [],
        "rag_context": "",
        "cv_result": None,
        "final_answer": "",
        "metadata": {}
    }
    
    result_state = await graph.ainvoke(initial_state)
    
    return ChatResponse(
        task_id=chat_req.task_id,
        status="success",
        steps=result_state["steps"],
        answer=result_state["final_answer"],
        rag_context=result_state["rag_context"],
        metadata=result_state["metadata"]
    )
