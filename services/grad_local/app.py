from __future__ import annotations

import base64
import io
import json
import os
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np
import torch
import torch.nn.functional as F
import yaml
from easydict import EasyDict
from fastapi import FastAPI, HTTPException
from PIL import Image
from pydantic import BaseModel, Field
from torchvision import transforms


REPO_DIR = Path(os.getenv("GRAD_SERVICE_REPO_DIR", "/root/autodl-tmp/gradcn")).resolve()
CONFIG_PATH = Path(
    os.getenv("GRAD_SERVICE_CONFIG", str(REPO_DIR / "experiments" / "config.yaml"))
).resolve()
CHECKPOINT_PATH = Path(
    os.getenv(
        "GRAD_SERVICE_CHECKPOINT",
        str(REPO_DIR / "experiments" / "exp" / "GRAD" / "MVTecAD" / "checkpoints" / "ckpt_best.pth.tar"),
    )
).resolve()
OUTPUT_DIR = Path(os.getenv("GRAD_SERVICE_OUTPUT_DIR", "data/heatmaps/grad")).resolve()
DEFAULT_THRESHOLD = float(os.getenv("GRAD_SERVICE_THRESHOLD", "0.5"))

if str(REPO_DIR) not in sys.path:
    sys.path.insert(0, str(REPO_DIR))

from models.model_helper import ModelHelper  # noqa: E402
from utils.misc_helper import load_state, update_config  # noqa: E402


app = FastAPI(title="grad-local-detector")


class DetectRequest(BaseModel):
    task_id: str
    asset_id: Optional[str] = None
    question: Optional[str] = None
    image_base64: str
    image_mime: str = "image/jpeg"
    detector_type: str = "grad"
    detector_params: Dict[str, Any] = Field(default_factory=dict)
    parameters: Dict[str, Any] = Field(default_factory=dict)


def _load_config() -> EasyDict:
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"GRAD config not found: {CONFIG_PATH}")
    with CONFIG_PATH.open("r", encoding="utf-8") as handle:
        config = EasyDict(yaml.load(handle, Loader=yaml.FullLoader))

    exp_path = Path(config.saver.exp_path)
    if not exp_path.is_absolute():
        exp_path = (CONFIG_PATH.parent / exp_path).resolve()
    config.exp_path = str(exp_path.parent)
    config.save_path = str(Path(config.exp_path) / config.saver.save_dir)
    config.log_path = str(Path(config.exp_path) / config.saver.log_dir)
    config.feat_path = str(Path(config.exp_path) / config.saver.feat_dir)
    config.evaluator.eval_dir = str(Path(config.exp_path) / config.evaluator.save_dir)
    config.evaluator.vis_compound.save_dir = str(Path(config.exp_path) / config.evaluator.vis_compound.save_dir)
    return update_config(config)


@lru_cache(maxsize=1)
def _load_model() -> Tuple[ModelHelper, EasyDict]:
    if not torch.cuda.is_available():
        raise RuntimeError("GRAD service requires CUDA because the upstream implementation calls .cuda().")
    if not CHECKPOINT_PATH.exists():
        raise FileNotFoundError(f"GRAD checkpoint not found: {CHECKPOINT_PATH}")

    config = _load_config()
    model = ModelHelper(config.net)
    model.cuda()
    load_state(str(CHECKPOINT_PATH), model)
    model.eval()
    return model, config


def _decode_image(image_base64: str) -> Image.Image:
    try:
        image_bytes = base64.b64decode(image_base64, validate=True)
        return Image.open(io.BytesIO(image_bytes)).convert("RGB")
    except Exception as exc:
        raise ValueError("image_base64 is not a valid image") from exc


def _preprocess(image: Image.Image, config: EasyDict) -> torch.Tensor:
    size = tuple(config.dataset.input_size)
    transform = transforms.Compose(
        [
            transforms.Resize(size),
            transforms.ToTensor(),
            transforms.Normalize(mean=config.dataset.pixel_mean, std=config.dataset.pixel_std),
        ]
    )
    return transform(image).unsqueeze(0)


def _normalize_heatmap(pred: torch.Tensor, width: int, height: int) -> np.ndarray:
    pred = pred.detach().float().cpu()
    if pred.ndim == 4:
        pred = pred[0, 0]
    elif pred.ndim == 3:
        pred = pred[0]

    pred = F.avg_pool2d(pred[None, None, ...], 21, stride=1, padding=10)[0, 0].numpy()
    pred = cv2.resize(pred, (width, height), interpolation=cv2.INTER_CUBIC).astype(np.float32)
    minimum = float(pred.min())
    maximum = float(pred.max())
    if maximum > minimum:
        pred = (pred - minimum) / (maximum - minimum)
    else:
        pred = np.zeros_like(pred, dtype=np.float32)
    return np.clip(pred, 0.0, 1.0)


def _save_visualizations(image: Image.Image, heatmap: np.ndarray, task_id: str, category: str) -> Dict[str, str]:
    output_dir = OUTPUT_DIR / category
    output_dir.mkdir(parents=True, exist_ok=True)

    image_rgb = np.array(image.convert("RGB"))
    heat_uint8 = np.clip(heatmap * 255, 0, 255).astype(np.uint8)
    color_map = cv2.applyColorMap(heat_uint8, cv2.COLORMAP_JET)
    color_map_rgb = cv2.cvtColor(color_map, cv2.COLOR_BGR2RGB)
    overlay = cv2.addWeighted(image_rgb, 0.6, color_map_rgb, 0.4, 0)
    mask = np.where(heatmap >= DEFAULT_THRESHOLD, 255, 0).astype(np.uint8)

    heatmap_path = output_dir / f"{task_id}_heatmap.png"
    overlay_path = output_dir / f"{task_id}_overlay.png"
    mask_path = output_dir / f"{task_id}_mask.png"
    Image.fromarray(color_map_rgb).save(heatmap_path)
    Image.fromarray(overlay).save(overlay_path)
    Image.fromarray(mask).save(mask_path)
    return {
        "heatmap_path": str(heatmap_path),
        "overlay_path": str(overlay_path),
        "mask_path": str(mask_path),
    }


def _location_from_bbox(bbox: List[int], image_size: Tuple[int, int]) -> str:
    width, height = image_size
    x1, y1, x2, y2 = bbox
    center_x = (x1 + x2) / 2
    center_y = (y1 + y2) / 2
    horizontal = "left" if center_x < width / 3 else "right" if center_x > 2 * width / 3 else "center"
    vertical = "top" if center_y < height / 3 else "bottom" if center_y > 2 * height / 3 else "middle"
    return f"{vertical}-{horizontal}"


def _extract_anomalies(heatmap: np.ndarray, threshold: float, image_size: Tuple[int, int]) -> List[Dict[str, Any]]:
    width, height = image_size
    mask = (heatmap >= threshold).astype(np.uint8)
    num_labels, _, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    min_area = max(16, int(0.0005 * width * height))
    anomalies: List[Dict[str, Any]] = []

    for index in range(1, num_labels):
        x, y, w, h, area = stats[index]
        if int(area) < min_area:
            continue
        component = heatmap[y : y + h, x : x + w]
        bbox = [int(x), int(y), int(x + w), int(y + h)]
        score = float(component.max()) if component.size else 0.0
        anomalies.append(
            {
                "type": "surface_anomaly",
                "score": round(score, 4),
                "details": "GRAD reconstruction anomaly region",
                "bbox": bbox,
                "location": _location_from_bbox(bbox, image_size),
                "has_localization": True,
            }
        )

    anomalies.sort(key=lambda item: float(item.get("score", 0.0)), reverse=True)
    return anomalies


@app.get("/health")
def health() -> Dict[str, Any]:
    return {
        "status": "ok",
        "repo_dir": str(REPO_DIR),
        "config": str(CONFIG_PATH),
        "checkpoint": str(CHECKPOINT_PATH),
        "checkpoint_exists": CHECKPOINT_PATH.exists(),
        "cuda_available": torch.cuda.is_available(),
    }


@app.post("/detect")
def detect(payload: DetectRequest) -> Dict[str, Any]:
    try:
        model, config = _load_model()
        image = _decode_image(payload.image_base64)
        category = str(
            payload.detector_params.get("category")
            or payload.parameters.get("category")
            or payload.parameters.get("patchcore_category")
            or "unknown"
        ).strip().lower()
        threshold = float(payload.detector_params.get("threshold", DEFAULT_THRESHOLD))

        tensor = _preprocess(image, config)
        input_batch = {
            "image": tensor,
            "mode": "test",
        }
        with torch.no_grad():
            outputs = model(input_batch)

        heatmap = _normalize_heatmap(outputs["pred"], image.width, image.height)
        anomalies = _extract_anomalies(heatmap, threshold, (image.width, image.height))
        paths = _save_visualizations(image, heatmap, payload.task_id, category)
        anomaly_score = float(heatmap.max())
        summary = (
            f"GRAD detected {len(anomalies)} anomalous region(s)."
            if anomalies
            else "GRAD found no strong anomaly."
        )
        return {
            "task_id": payload.task_id,
            "status": "success",
            "answer": summary,
            "summary": summary,
            "anomalies": anomalies,
            "metadata": {
                "selected_backend": "grad",
                "category": category,
                "anomaly_score": anomaly_score,
                "confidence": anomaly_score,
                "threshold": threshold,
                "image_size": [image.width, image.height],
                "checkpoint": str(CHECKPOINT_PATH),
                **paths,
            },
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


if __name__ == "__main__":
    print(json.dumps(health(), indent=2))
