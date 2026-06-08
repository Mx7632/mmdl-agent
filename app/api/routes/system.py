from __future__ import annotations

import time
from pathlib import Path

from fastapi import APIRouter

from app.config.settings import settings
from app.schemas.runtime import RuntimeMetricsResponse, SystemHealthResponse
from app.services.industrial_runtime import industrial_store
from app.tools.patchcore_detection import trained_patchcore_categories

router = APIRouter()


@router.get("/v1/system/health", response_model=SystemHealthResponse)
async def system_health() -> SystemHealthResponse:
    trained_categories = trained_patchcore_categories()
    allowed_origins = [
        origin.strip() for origin in (settings.allowed_origins or "").split(",") if origin.strip()
    ]
    return SystemHealthResponse(
        status="ok",
        timestamp=time.time(),
        components={
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
                "status": "configured"
                if settings.professional_vision_detector_url
                else "not_configured",
                "url": settings.professional_vision_detector_url,
            },
            "grad_sidecar": {
                "status": "configured" if settings.grad_detector_url else "not_configured",
                "url": settings.grad_detector_url,
            },
            "security": {
                "api_token_required": settings.require_api_token,
                "allowed_origins": allowed_origins,
            },
        },
        metrics=industrial_store.metrics(),
    )


@router.get("/v1/metrics", response_model=RuntimeMetricsResponse)
async def runtime_metrics() -> RuntimeMetricsResponse:
    return RuntimeMetricsResponse(status="success", metrics=industrial_store.metrics())
