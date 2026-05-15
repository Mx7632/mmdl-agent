from __future__ import annotations

import base64
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request, File, UploadFile, BackgroundTasks, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from starlette.datastructures import UploadFile as StarletteUploadFile

from app.config.settings import settings
from app.exceptions.base import AppError, DataMissingError, ResponseParseError
from app.rag.service import get_rag_service
from app.services import continue_detection, generate_report, get_pending_task, run_chat, run_detection
from app.services.industrial_runtime import REVIEW_APPROVED, industrial_store, normalize_industrial_result
from app.schemas.detection import DetectionResult, DetectionTask
from app.schemas.detection import (
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
    allow_origins=[
        origin.strip()
        for origin in (settings.allowed_origins or "").split(",")
        if origin.strip()
    ] or ["http://127.0.0.1:8000"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

Path("data/uploads").mkdir(parents=True, exist_ok=True)
Path("data/heatmaps").mkdir(parents=True, exist_ok=True)

# 挂载前端静态文件
app.mount("/web", StaticFiles(directory="web"), name="web")
# 也可以挂载数据文件（如图片预览）
app.mount("/data/uploads", StaticFiles(directory="data/uploads"), name="uploads")
app.mount("/data/heatmaps", StaticFiles(directory="data/heatmaps"), name="heatmaps")

logger = setup_logger(level=settings.log_level)


def _is_allowed_origin(origin: str | None) -> bool:
    allowed = [item.strip() for item in (settings.allowed_origins or "").split(",") if item.strip()]
    return bool(origin and ("*" in allowed or origin in allowed))


def _check_api_token(request: Request) -> None:
    if not settings.require_api_token:
        return
    token = request.headers.get("x-api-token") or ""
    auth = request.headers.get("authorization") or ""
    if auth.lower().startswith("bearer "):
        token = auth[7:].strip()
    if not settings.api_token or token != settings.api_token:
        raise HTTPException(status_code=401, detail="Valid API token is required")


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
    trace_id = "-"
    try:
        trace_id = request.headers.get(TRACE_ID_HEADER) or new_trace_id()
        setattr(request.state, "trace_id", trace_id)
        set_trace_id(trace_id)
    except HTTPException as e:
        response = JSONResponse(status_code=e.status_code, content={"code": "unauthorized", "message": e.detail, "trace_id": trace_id})
        origin = request.headers.get("origin")
        if _is_allowed_origin(origin):
            response.headers["Access-Control-Allow-Origin"] = origin
        return response
    except HTTPException as e:
        response = JSONResponse(status_code=e.status_code, content={"code": "unauthorized", "message": e.detail, "trace_id": trace_id})
        origin = request.headers.get("origin")
        if _is_allowed_origin(origin):
            response.headers["Access-Control-Allow-Origin"] = origin
        return response
    except Exception as e:
        logger.error(f"Middleware trace_id setup error: {e}")

    try:
        _check_api_token(request)
        response = await call_next(request)
        response.headers[TRACE_ID_HEADER] = trace_id
        
        # 强制补充 CORS 头（防止 500 时 CORSMiddleware 失效）
        origin = request.headers.get("origin")
        if _is_allowed_origin(origin):
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Methods"] = "*"
            response.headers["Access-Control-Allow-Headers"] = "*"
            
        return response
    except Exception as e:
        import traceback
        logger.error(f"Middleware execution error: {e}\n{traceback.format_exc()}")
        
        content = {"code": "internal_error", "message": str(e), "trace_id": trace_id}
        response = JSONResponse(status_code=500, content=content)
        
        # 错误响应也必须带上 CORS 头
        origin = request.headers.get("origin")
        if _is_allowed_origin(origin):
            response.headers["Access-Control-Allow-Origin"] = origin
            
        return response


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    logger.error(f"{exc.code}: {exc.message}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": exc.code, "message": exc.message, "trace_id": getattr(request.state, "trace_id", "-")},
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    import traceback
    logger.error(f"Unhandled Exception: {exc}\n{traceback.format_exc()}")
    return JSONResponse(
        status_code=500,
        content={"code": "internal_error", "message": str(exc), "trace_id": getattr(request.state, "trace_id", "-")},
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


@app.get("/health")
async def health_check():
    """健康检查端点，供前端轮询状态"""
    return {"status": "ok", "timestamp": __import__("time").time()}


@app.get("/v1/system/health")
async def system_health():
    from app.tools.patchcore_detection import trained_patchcore_categories

    trained_categories = trained_patchcore_categories()
    allowed_origins = [origin.strip() for origin in (settings.allowed_origins or "").split(",") if origin.strip()]
    return {
        "status": "ok",
        "timestamp": time.time(),
        "components": {
            "api": {"status": "ok"},
            "rag": {
                "status": "ok" if Path(settings.rag_vector_dir).exists() else "missing",
                "vector_dir": settings.rag_vector_dir,
            },
            "postgres": {
                "status": "configured" if settings.database_url else "not_configured",
                "backend": settings.checkpoint_backend,
            },
            "patchcore": {
                "status": "trained" if trained_categories else "not_trained",
                "model_root": settings.patchcore_model_root,
                "trained_categories": trained_categories,
            },
            "anomalygpt_sidecar": {
                "status": "configured" if settings.professional_vision_detector_url else "not_configured",
                "url": settings.professional_vision_detector_url,
            },
            "security": {
                "api_token_required": settings.require_api_token,
                "allowed_origins": allowed_origins,
            },
        },
        "metrics": industrial_store.metrics(),
    }


@app.get("/v1/metrics")
async def runtime_metrics():
    return {"status": "success", "metrics": industrial_store.metrics()}


@app.get("/v1/patchcore/categories")
async def patchcore_categories():
    from app.tools.patchcore_detection import (
        available_mvtec_categories,
        get_patchcore_category_status,
        trained_patchcore_categories,
    )

    dataset_categories = available_mvtec_categories(settings.rag_dataset_root)
    trained_categories = trained_patchcore_categories()
    all_categories = sorted(set(dataset_categories) | set(trained_categories))
    return {
        "status": "success",
        "dataset_root": settings.rag_dataset_root,
        "model_root": settings.patchcore_model_root,
        "default_category": settings.patchcore_default_category,
        "default_threshold": settings.patchcore_threshold,
        "dataset_categories": dataset_categories,
        "trained_categories": trained_categories,
        "categories": [get_patchcore_category_status(category) for category in all_categories],
    }


# ── RAG 端点（来自 origin/main）───────────────────────────────────────────────


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


# ── 检测端点（合并本地 + 远程逻辑）─────────────────────────────────────────────


@app.post("/v1/detect")
async def detect(request: Request):
    """
    创建检测任务并执行循环工作流。

    首次调用返回结果；若置信度不足或需要用户澄清，
    返回 status=pending，前端需调用 /v1/continue 续传。
    支持图片上传（多模态）或纯文本模式。
    """
    content_type = (request.headers.get("content-type") or "").lower()

    if "multipart/form-data" not in content_type:
        raise DataMissingError("Only multipart/form-data is supported for /v1/detect")

    form = await request.form()

    task_id = get_form_text(form, "task_id").strip()
    asset_id = get_form_text(form, "asset_id").strip()
    start_time = get_form_text(form, "start_time").strip()
    end_time = get_form_text(form, "end_time").strip()
    data_source = get_form_text(form, "data_source").strip() or None
    question = get_form_text(form, "question").strip() or None

    if not task_id or not asset_id or not start_time or not end_time:
        raise DataMissingError("task_id/asset_id/start_time/end_time are required")

    raw_parameters = form.get("parameters")
    try:
        parameters: dict[str, Any]
        if raw_parameters is None:
            parameters = {}
        elif isinstance(raw_parameters, str):
            parameters = json.loads(raw_parameters) if raw_parameters else {}
        elif isinstance(raw_parameters, dict):
            parameters = dict(raw_parameters)
        else:
            parameters = {}
    except Exception as e:
        raise ResponseParseError(
            "parameters must be valid JSON string",
            raw_response=raw_parameters,
            original_error=e,
        )

    # 图片上传（可选，不传则为纯文本模式）
    upload = form.get("image")
    if isinstance(upload, StarletteUploadFile) and getattr(upload, "filename", None):
        image_bytes = await upload.read()
        image_b64 = base64.b64encode(image_bytes).decode("ascii")
        parameters.setdefault("tool_type", settings.vision_detector_backend)
        parameters["image_base64"] = image_b64
        parameters["image_mime"] = getattr(upload, "content_type", None) or "image/jpeg"
        input_type = "image"
    else:
        input_type = "text"

    task = DetectionTask(
        task_id=task_id,
        asset_id=asset_id,
        start_time=start_time,
        end_time=end_time,
        data_source=data_source,
        input_type=input_type,
        question=question,
        parameters=parameters,
    )

    try:
        result = await run_detection(task)
        return normalize_industrial_result(result)
    except Exception as e:
        import traceback
        logger.error(f"[detect] run_detection failed: {e}\n{traceback.format_exc()}")
        raise


def now_iso_or(value: str) -> str:
    cleaned = (value or "").strip()
    return cleaned or datetime.now().isoformat()


@app.post("/v1/batches/detect")
async def batch_detect(request: Request):
    content_type = (request.headers.get("content-type") or "").lower()
    if "multipart/form-data" not in content_type:
        raise DataMissingError("Only multipart/form-data is supported for /v1/batches/detect")

    form = await request.form()
    asset_id = get_form_text(form, "asset_id").strip()
    question = get_form_text(form, "question").strip() or None
    if not asset_id:
        raise DataMissingError("asset_id is required")

    raw_parameters = form.get("parameters")
    try:
        parameters = json.loads(raw_parameters) if isinstance(raw_parameters, str) and raw_parameters else {}
    except Exception as exc:
        raise ResponseParseError("parameters must be valid JSON string", raw_response=raw_parameters, original_error=exc)

    uploads = [
        item
        for item in [*form.getlist("images"), *form.getlist("image")]
        if isinstance(item, StarletteUploadFile) and getattr(item, "filename", None)
    ]
    if not uploads:
        raise DataMissingError("At least one image is required")

    batch = industrial_store.create_batch(asset_id=asset_id, question=question, item_count=len(uploads))
    task_ids: list[str] = []
    results: list[dict[str, Any]] = []
    for index, upload in enumerate(uploads, start=1):
        image_bytes = await upload.read()
        task_parameters = dict(parameters)
        task_parameters.setdefault("tool_type", settings.vision_detector_backend)
        task_parameters["image_base64"] = base64.b64encode(image_bytes).decode("ascii")
        task_parameters["image_mime"] = getattr(upload, "content_type", None) or "image/jpeg"
        task_parameters["source_filename"] = upload.filename
        task_id = f"{batch['batch_id']}-{index:03d}"
        task = DetectionTask(
            task_id=task_id,
            asset_id=asset_id,
            start_time=now_iso_or(get_form_text(form, "start_time")),
            end_time=now_iso_or(get_form_text(form, "end_time")),
            data_source=get_form_text(form, "data_source").strip() or "batch_upload",
            input_type="image",
            question=question,
            parameters=task_parameters,
        )
        result = normalize_industrial_result(await run_detection(task))
        industrial_store.record_task(task, result, batch_id=batch["batch_id"])
        task_ids.append(task_id)
        results.append(result)

    batch = industrial_store.finish_batch(batch["batch_id"], task_ids)
    return {
        "status": "success",
        "batch": batch,
        "results": results,
        "report": industrial_store.batch_report(batch["batch_id"]),
    }


@app.get("/v1/tasks")
async def list_task_history(
    asset_id: str | None = None,
    status: str | None = None,
    defect_type: str | None = None,
    review_status: str | None = None,
    limit: int = 50,
):
    return {
        "status": "success",
        "tasks": industrial_store.list_tasks(
            asset_id=asset_id,
            status=status,
            defect_type=defect_type,
            review_status=review_status,
            limit=limit,
        ),
    }


@app.get("/v1/reviews/pending")
async def pending_reviews(limit: int = 50):
    return {"status": "success", "tasks": industrial_store.pending_reviews(limit=limit)}


@app.post("/v1/tasks/{task_id}/review")
async def review_task(task_id: str, request: Request):
    body = await request.json()
    decision = str(body.get("decision", "")).strip().lower()
    if decision not in {"approve", "approved", "confirm", "confirmed", "reject", "rejected"}:
        raise DataMissingError("decision must be approve/confirm or reject")
    try:
        task = industrial_store.review_task(
            task_id,
            decision=decision,
            defect_type=(body.get("defect_type") or None),
            notes=(body.get("notes") or None),
            reviewer=(body.get("reviewer") or None),
        )
    except KeyError:
        return JSONResponse(status_code=404, content={"code": "not_found", "message": f"Task {task_id} not found"})
    return {"status": "success", "task": task}


@app.post("/v1/batches/{batch_id}/report")
async def batch_report(batch_id: str):
    try:
        return {"status": "success", **industrial_store.batch_report(batch_id)}
    except KeyError:
        return JSONResponse(status_code=404, content={"code": "not_found", "message": f"Batch {batch_id} not found"})


@app.post("/v1/rag/feedback/{feedback_id}/review")
async def review_rag_feedback(feedback_id: str, request: Request):
    body = await request.json()
    decision = str(body.get("decision", "")).strip().lower()
    if decision not in {"approve", "approved", "reject", "rejected"}:
        raise DataMissingError("decision must be approve or reject")
    try:
        feedback = industrial_store.review_feedback(feedback_id, decision)
    except KeyError:
        return JSONResponse(status_code=404, content={"code": "not_found", "message": "feedback not found"})
    return {"status": "success", "feedback": feedback}


@app.post("/v1/rag/feedback/queue", response_model=RagIngestFeedbackResponse)
async def queue_rag_feedback(payload: RagIngestFeedbackRequest) -> RagIngestFeedbackResponse:
    feedback = industrial_store.create_feedback(payload.model_dump())
    return RagIngestFeedbackResponse(
        status="success",
        accepted=False,
        learning_threshold=settings.rag_learning_threshold,
        message="Feedback is queued for human review before it can enter the RAG store.",
        feedback_id=feedback["feedback_id"],
        review_status=feedback["review_status"],
    )


@app.post("/v1/continue")
async def continue_req(request: Request):
    """
    续传检测任务（用户澄清后调用）。
    将用户回复注入当前挂起任务，继续执行工作流。
    """
    body = await request.json()
    task_id = str(body.get("task_id", "")).strip()
    user_reply = str(body.get("user_reply", "")).strip()

    if not task_id:
        raise DataMissingError("task_id is required")
    if not user_reply:
        raise DataMissingError("user_reply cannot be empty")

    result = await continue_detection(task_id, user_reply)
    return result


@app.get("/v1/pending/{task_id}")
async def pending(task_id: str):
    """
    查询挂起任务的澄清内容。
    前端轮询此接口展示"等待用户输入"界面。
    """
    info = await get_pending_task(task_id)
    if info is None:
        return JSONResponse(
            status_code=404,
            content={"code": "not_found", "message": f"未找到挂起任务: {task_id}"},
        )
    return info


@app.post("/v1/chat")
async def chat(request: Request):
    """
    多轮对话接口。
    基于已有检测任务，回答用户的新问题。
    """
    body = await request.json()
    task_id = str(body.get("task_id", "")).strip()
    question = str(body.get("question", "")).strip()

    if not task_id:
        raise DataMissingError("task_id is required")
    if not question:
        raise DataMissingError("question cannot be empty")

    result = await run_chat(task_id, question)
    return result


@app.post("/v1/generate_report")
async def generate_report_endpoint(request: Request):
    """
    生成完整报告接口。
    用户点击"生成报告"按钮后调用，返回完整检测报告。
    """
    body = await request.json()
    task_id = str(body.get("task_id", "")).strip()

    if not task_id:
        raise DataMissingError("task_id is required")

    result = await generate_report(task_id)
    return result


def get_form_text(form: Any, key: str) -> str:
    """从 FormData 中安全提取文本内容。"""
    value = form.get(key)
    return value if isinstance(value, str) else ""


@app.post("/v1/stream")
async def stream_chat(request: Request):
    """
    流式对话接口 (SSE)。
    支持实时输出规划过程和最终回答。
    """
    try:
        form = await request.form()
        task_id = get_form_text(form, "task_id") or f"chat-{int(time.time())}"
        asset_id = get_form_text(form, "asset_id") or "EQUIP-001"
        question = get_form_text(form, "question")
        user_reply = get_form_text(form, "user_reply").strip()
        
        logger.info(f"[stream_chat] Received request: task_id={task_id}, asset_id={asset_id}, question={question}")
        
        # 构造任务
        parameters = {}
        raw_params = form.get("parameters")
        if raw_params and isinstance(raw_params, str):
            try:
                parameters = json.loads(raw_params)
            except Exception as e:
                logger.warning(f"Failed to parse parameters JSON: {e}")

        # 处理图片
        upload = form.get("image")
        input_type = "text"
        if isinstance(upload, StarletteUploadFile) and getattr(upload, "filename", None):
            logger.info(f"[stream_chat] Image upload detected: {upload.filename}")
            image_bytes = await upload.read()
            image_b64 = base64.b64encode(image_bytes).decode("ascii")
            parameters.setdefault("tool_type", settings.vision_detector_backend)
            parameters["image_base64"] = image_b64
            parameters["image_mime"] = getattr(upload, "content_type", None) or "image/jpeg"
            input_type = "image"
            logger.info(f"[stream_chat] Image processed, base64 length: {len(image_b64)}")
        else:
            logger.info("[stream_chat] No image upload detected in current request")

        from app.services import stream_continue_detection, stream_detection
        
        async def wrapped_stream():
            try:
                if user_reply:
                    async for chunk in stream_continue_detection(task_id, user_reply):
                        yield chunk
                else:
                    task = DetectionTask(
                        task_id=task_id,
                        asset_id=asset_id,
                        question=question,
                        input_type=input_type,
                        parameters=parameters,
                        start_time=datetime.now().isoformat(),
                        end_time=datetime.now().isoformat()
                    )
                    async for chunk in stream_detection(task):
                        yield chunk
            except Exception as e:
                import traceback
                logger.error(f"[stream_chat] Error during streaming: {e}\n{traceback.format_exc()}")
                yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

        return StreamingResponse(
            wrapped_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Content-Type": "text/event-stream",
            }
        )
    except Exception as e:
        import traceback
        logger.error(f"[stream_chat] Setup Error: {e}\n{traceback.format_exc()}")
        return JSONResponse(
            status_code=500,
            content={"code": "stream_setup_error", "message": str(e)}
        )


@app.post("/v1/detect_with_report")
async def detect_with_report(request: Request):
    """
    检测+报告一次性接口。
    首次上传图片时返回：答案 + 完整报告（前端以卡片形式嵌入）。
    """
    content_type = (request.headers.get("content-type") or "").lower()

    if "multipart/form-data" not in content_type:
        raise DataMissingError("Only multipart/form-data is supported for /v1/detect_with_report")

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
        raise DataMissingError("task_id/asset_id/start_time/end_time are required")

    raw_parameters = form.get("parameters")
    try:
        parameters: dict[str, Any]
        if raw_parameters is None:
            parameters = {}
        elif isinstance(raw_parameters, str):
            parameters = json.loads(raw_parameters) if raw_parameters else {}
        elif isinstance(raw_parameters, dict):
            parameters = dict(raw_parameters)
        else:
            parameters = {}
    except Exception as e:
        raise ResponseParseError(
            "parameters must be valid JSON string",
            raw_response=raw_parameters,
            original_error=e,
        )

    # 图片上传
    upload = form.get("image")
    if isinstance(upload, StarletteUploadFile) and getattr(upload, "filename", None):
        image_bytes = await upload.read()
        image_b64 = base64.b64encode(image_bytes).decode("ascii")
        parameters.setdefault("tool_type", settings.vision_detector_backend)
        parameters["image_base64"] = image_b64
        parameters["image_mime"] = getattr(upload, "content_type", None) or "image/jpeg"
        input_type = "image"
    else:
        input_type = "text"

    task = DetectionTask(
        task_id=task_id,
        asset_id=asset_id,
        start_time=start_time,
        end_time=end_time,
        data_source=data_source,
        input_type=input_type,
        question=question,
        parameters=parameters,
    )

    try:
        # 执行检测（不走 report 流程）
        detection_result = await run_detection(task)

        if detection_result.get("status") == "pending":
            return detection_result

        # 已有检测结果，直接生成报告
        if detection_result.get("status") == "success":
            report_result = await generate_report(task_id)
            # 合并：检测答案 + 完整报告
            return {
                **detection_result,
                "summary": report_result.get("summary"),
                "has_report": True,
            }

        return detection_result
    except Exception as e:
        import traceback
        logger.error(f"[detect_with_report] failed: {e}\n{traceback.format_exc()}")
        raise
