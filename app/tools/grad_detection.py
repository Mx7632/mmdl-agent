"""GRAD anomaly detection tool for MMDL-Agent.

Provides LocalGRADImageAnomalyDetectionTool, following the same pattern as
LocalPatchCoreImageAnomalyDetectionTool (patchcore_detection.py).
"""

from __future__ import annotations

import base64
import io
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import torch
from PIL import Image
from torchvision import transforms

from app.config.settings import settings
from app.exceptions.base import ConfigurationError, ToolExecutionError
from app.schemas.detection import DetectionResult, DetectionTask, ToolResponse
from app.tools.anomaly_detection import BaseTool
from app.tools.grad_vendor.grad_model import load_grad_model
from app.tools.patchcore_detection import (
    _extract_anomalies_from_heatmap,
    _save_visualizations,
)

# ---------------------------------------------------------------------------
# Image preprocessing (matches GRAD training pipeline)
# ---------------------------------------------------------------------------

GRAD_TRANSFORM = transforms.Compose(
    [
        transforms.Resize((256, 256)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ]
)

# ---------------------------------------------------------------------------
# Model cache (keyed by resolved checkpoint path)
# ---------------------------------------------------------------------------

_model_cache: dict[str, Any] = {}


# ---------------------------------------------------------------------------
# Artifacts
# ---------------------------------------------------------------------------


@dataclass
class GRADArtifacts:
    category: str
    model_dir: Path
    checkpoint_path: Path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def resolve_grad_category(task: DetectionTask) -> str:
    detector_params = (task.parameters or {}).get("detector_params") or {}
    category = (
        detector_params.get("category")
        or (task.parameters or {}).get("grad_category")
        or settings.grad_default_category
    )
    return str(category).strip().lower()


def get_grad_artifacts(category: str) -> GRADArtifacts:
    model_dir = Path(settings.grad_checkpoint_dir) / category
    return GRADArtifacts(
        category=category,
        model_dir=model_dir,
        checkpoint_path=model_dir / "best.pth.tar",
    )


def trained_grad_categories(model_root: str | None = None) -> list[str]:
    root = Path(model_root or settings.grad_checkpoint_dir)
    if not root.is_dir():
        return []
    categories: list[str] = []
    for entry in sorted(root.iterdir()):
        if entry.is_dir() and (entry / "best.pth.tar").is_file():
            categories.append(entry.name)
    return categories


def _grad_heatmap_from_scores(anomaly_map: np.ndarray, width: int, height: int) -> np.ndarray:
    import cv2

    amin, amax = anomaly_map.min().item(), anomaly_map.max().item()
    if amax - amin > 1e-8:
        anomaly_map = (anomaly_map - amin) / (amax - amin)
    else:
        anomaly_map = np.zeros_like(anomaly_map)
    heatmap = cv2.resize(anomaly_map, (width, height), interpolation=cv2.INTER_CUBIC)
    return heatmap


def _extract_grad_anomalies(
    heatmap: np.ndarray, threshold: float, image_size: tuple[int, int]
) -> list[dict[str, Any]]:
    """Thin wrapper that fixes the 'details' field after PatchCore's extractor."""
    anomalies = _extract_anomalies_from_heatmap(heatmap, threshold, image_size)
    for anomaly in anomalies:
        anomaly["details"] = "GRAD anomaly region"
    return anomalies


# ---------------------------------------------------------------------------
# Core prediction
# ---------------------------------------------------------------------------


def predict_grad_image(
    image_path: str | Path,
    category: str,
    threshold: float | None,
    task_id: str,
) -> dict[str, Any]:
    artifacts = get_grad_artifacts(category)
    if not artifacts.checkpoint_path.exists():
        raise FileNotFoundError(
            f"GRAD checkpoint not found for category '{category}'. "
            f"Expected {artifacts.checkpoint_path}"
        )

    device = settings.grad_device
    effective_threshold = threshold if threshold is not None else settings.grad_threshold
    image = Image.open(image_path).convert("RGB")

    # Load or retrieve model
    cache_key = str(artifacts.checkpoint_path.resolve())
    if cache_key not in _model_cache:
        _model_cache[cache_key] = load_grad_model(str(artifacts.checkpoint_path), device)
    model = _model_cache[cache_key]

    # Preprocess
    tensor = GRAD_TRANSFORM(image).unsqueeze(0).to(device)  # [1, 3, 256, 256]

    # Inference
    with torch.no_grad():
        pred = model(tensor)  # [1, 1, 256, 256]
    anomaly_map = pred.squeeze().cpu().numpy()  # [256, 256]

    # Post-process
    heatmap = _grad_heatmap_from_scores(anomaly_map, image.width, image.height)
    image_score = float(heatmap.max())
    anomalies = _extract_grad_anomalies(heatmap, effective_threshold, (image.width, image.height))
    saved_paths = _save_visualizations(image, heatmap, category, task_id, settings.grad_heatmap_dir)

    output_metadata = {
        "selected_backend": "grad",
        "category": category,
        "confidence": image_score,
        "anomaly_score": image_score,
        "threshold": effective_threshold,
        "localization_available": bool(anomalies),
        "image_size": [image.width, image.height],
        **saved_paths,
    }
    summary = (
        f"GRAD detected {len(anomalies)} anomalous region(s) for category '{category}'."
        if anomalies
        else f"GRAD found no strong anomaly for category '{category}'."
    )
    return {
        "status": "success",
        "anomalies": anomalies,
        "summary": summary,
        "answer": summary,
        "metadata": output_metadata,
    }


# ---------------------------------------------------------------------------
# Tool class
# ---------------------------------------------------------------------------


class LocalGRADImageAnomalyDetectionTool(BaseTool):
    name = "grad_image_anomaly_detection"

    async def run(self, task: DetectionTask) -> ToolResponse:
        image_b64 = (task.parameters or {}).get("image_base64")
        if not image_b64:
            raise ToolExecutionError(
                self.name,
                {"task_id": task.task_id},
                ValueError("image_base64 missing"),
            )

        category = resolve_grad_category(task)
        artifacts = get_grad_artifacts(category)

        if not artifacts.checkpoint_path.exists():
            raise ConfigurationError(
                f"GRAD category '{category}' has no trained checkpoint. "
                f"Expected {artifacts.checkpoint_path}. "
                "Place a best.pth.tar checkpoint or switch backend.",
                config_key="APP_GRAD_CHECKPOINT_DIR",
                details={
                    "category": category,
                    "trained": False,
                    "expected_checkpoint": str(artifacts.checkpoint_path),
                    "trained_categories": trained_grad_categories(),
                    "fallback_backend": "qwen",
                },
            )

        detector_params = (task.parameters or {}).get("detector_params") or {}
        threshold = (
            float(detector_params["threshold"])
            if detector_params.get("threshold") not in (None, "")
            else None
        )

        image_dir = Path(settings.grad_heatmap_dir) / category
        image_dir.mkdir(parents=True, exist_ok=True)
        image_path = image_dir / f"{task.task_id}_input.png"

        try:
            image_bytes = base64.b64decode(image_b64, validate=True)
            Image.open(io.BytesIO(image_bytes)).convert("RGB").save(image_path)
            payload = predict_grad_image(
                image_path=image_path,
                category=category,
                threshold=threshold,
                task_id=task.task_id,
            )
        except Exception as exc:
            raise ToolExecutionError(
                self.name,
                {"task_id": task.task_id, "category": category},
                exc,
            ) from exc

        metadata = dict(payload.get("metadata") or {})
        result = DetectionResult(
            task_id=task.task_id,
            status=payload.get("status", "success"),
            answer=payload.get("answer"),
            anomalies=payload.get("anomalies") or [],
            summary=payload.get("summary"),
            metadata=metadata,
        )
        return ToolResponse(tool_name=self.name, success=True, result=result)
