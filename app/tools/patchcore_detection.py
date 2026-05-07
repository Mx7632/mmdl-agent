from __future__ import annotations

import base64
import io
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image
from torchvision import models, transforms
from torchvision.models.feature_extraction import create_feature_extractor

from app.config.settings import settings
from app.exceptions.base import ConfigurationError, ToolExecutionError
from app.schemas.detection import DetectionResult, DetectionTask, ToolResponse
from app.tools.anomaly_detection import BaseTool

_SUPPORTED_BACKBONES = {"resnet18", "resnet34", "wide_resnet50_2"}


@dataclass
class PatchCoreArtifacts:
    category: str
    model_dir: Path
    memory_bank_path: Path
    metadata_path: Path


def available_mvtec_categories(dataset_root: str | Path) -> list[str]:
    root = Path(dataset_root)
    if not root.exists():
        return []
    return sorted(item.name for item in root.iterdir() if item.is_dir())


def _load_image(image_path: str | Path, image_size: int) -> tuple[Image.Image, torch.Tensor]:
    image = Image.open(image_path).convert("RGB")
    transform = transforms.Compose(
        [
            transforms.Resize((image_size, image_size)),
            transforms.ToTensor(),
            transforms.Normalize(mean=(0.485, 0.456, 0.406), std=(0.229, 0.224, 0.225)),
        ]
    )
    tensor = transform(image).unsqueeze(0)
    return image, tensor


def _build_feature_extractor(backbone_name: str, pretrained: bool) -> torch.nn.Module:
    if backbone_name not in _SUPPORTED_BACKBONES:
        raise ConfigurationError(
            f"Unsupported PatchCore backbone: {backbone_name}",
            config_key="APP_PATCHCORE_BACKBONE",
        )

    weight_map = {
        "resnet18": models.ResNet18_Weights.DEFAULT,
        "resnet34": models.ResNet34_Weights.DEFAULT,
        "wide_resnet50_2": models.Wide_ResNet50_2_Weights.DEFAULT,
    }
    builder = getattr(models, backbone_name)

    try:
        backbone = builder(weights=weight_map[backbone_name] if pretrained else None)
    except Exception:
        backbone = builder(weights=None)

    return_nodes = {"layer2": "layer2", "layer3": "layer3"}
    extractor = create_feature_extractor(backbone.eval(), return_nodes=return_nodes)
    return extractor


def _extract_patch_embeddings(
    extractor: torch.nn.Module,
    tensor: torch.Tensor,
    device: str,
) -> torch.Tensor:
    with torch.no_grad():
        features = extractor(tensor.to(device))
    layer2 = features["layer2"]
    layer3 = features["layer3"]
    layer3 = F.interpolate(layer3, size=layer2.shape[-2:], mode="bilinear", align_corners=False)
    merged = torch.cat([layer2, layer3], dim=1)
    merged = merged.squeeze(0).permute(1, 2, 0).contiguous()
    return merged.view(-1, merged.shape[-1]).cpu()


def _subsample_memory_bank(memory_bank: torch.Tensor, max_items: int) -> torch.Tensor:
    if memory_bank.shape[0] <= max_items:
        return memory_bank
    indices = torch.randperm(memory_bank.shape[0])[:max_items]
    return memory_bank[indices]


def _score_embeddings(query_embeddings: torch.Tensor, memory_bank: torch.Tensor, chunk_size: int = 2048) -> torch.Tensor:
    scores: list[torch.Tensor] = []
    for start in range(0, query_embeddings.shape[0], chunk_size):
        chunk = query_embeddings[start : start + chunk_size]
        distances = torch.cdist(chunk.float(), memory_bank.float())
        scores.append(distances.min(dim=1).values)
    return torch.cat(scores, dim=0)


def _heatmap_from_scores(score_map: np.ndarray, width: int, height: int) -> np.ndarray:
    score_map = score_map.astype(np.float32)
    minimum = float(score_map.min())
    maximum = float(score_map.max())
    if maximum > minimum:
        score_map = (score_map - minimum) / (maximum - minimum)
    else:
        score_map = np.zeros_like(score_map)

    resized = cv2.resize(score_map, (width, height), interpolation=cv2.INTER_CUBIC)
    return np.clip(resized, 0.0, 1.0)


def _save_visualizations(
    image: Image.Image,
    heatmap: np.ndarray,
    category: str,
    task_id: str,
    output_dir: str | Path,
) -> dict[str, str]:
    category_dir = Path(output_dir) / category
    category_dir.mkdir(parents=True, exist_ok=True)

    image_rgb = np.array(image.convert("RGB"))
    heat_uint8 = np.clip(heatmap * 255.0, 0, 255).astype(np.uint8)
    color_map = cv2.applyColorMap(heat_uint8, cv2.COLORMAP_JET)
    color_map_rgb = cv2.cvtColor(color_map, cv2.COLOR_BGR2RGB)
    overlay = cv2.addWeighted(image_rgb, 0.6, color_map_rgb, 0.4, 0.0)
    mask = np.where(heatmap > 0, 255, 0).astype(np.uint8)

    heatmap_path = category_dir / f"{task_id}_heatmap.png"
    overlay_path = category_dir / f"{task_id}_overlay.png"
    mask_path = category_dir / f"{task_id}_mask.png"

    Image.fromarray(color_map_rgb).save(heatmap_path)
    Image.fromarray(overlay).save(overlay_path)
    Image.fromarray(mask).save(mask_path)

    return {
        "heatmap_path": str(heatmap_path).replace("\\", "/"),
        "overlay_path": str(overlay_path).replace("\\", "/"),
        "mask_path": str(mask_path).replace("\\", "/"),
    }


def _derive_location_text(bbox: list[int] | None, image_size: tuple[int, int]) -> str | None:
    if not bbox:
        return None
    width, height = image_size
    x1, y1, x2, y2 = bbox
    center_x = (x1 + x2) / 2
    center_y = (y1 + y2) / 2
    horizontal = "left" if center_x < width / 3 else "right" if center_x > 2 * width / 3 else "center"
    vertical = "top" if center_y < height / 3 else "bottom" if center_y > 2 * height / 3 else "middle"
    return f"{vertical}-{horizontal}"


def _derive_size_label(area_ratio: float) -> str:
    if area_ratio < 0.01:
        return "small"
    if area_ratio < 0.05:
        return "medium"
    return "large"


def _derive_shape_label(width_ratio: float, height_ratio: float) -> str:
    if width_ratio >= 2.2:
        return "elongated-horizontal"
    if height_ratio >= 2.2:
        return "elongated-vertical"
    if 0.8 <= width_ratio / max(height_ratio, 1e-6) <= 1.25:
        return "compact"
    return "irregular"


def _derive_texture_hint(score: float, bbox: list[int]) -> str:
    box_width = max(1, bbox[2] - bbox[0])
    box_height = max(1, bbox[3] - bbox[1])
    aspect_ratio = max(box_width / box_height, box_height / box_width)
    if aspect_ratio >= 3.0:
        return "sharp linear response"
    if score >= 0.75:
        return "dense high-contrast region"
    if score >= 0.45:
        return "localized contrast variation"
    return "faint diffuse response"


def _derive_color_hint(score: float) -> str:
    if score >= 0.75:
        return "strong warm hotspot"
    if score >= 0.45:
        return "moderate warm hotspot"
    return "mild warm hotspot"


def _derive_severity_hint(score: float) -> str:
    if score >= 0.75:
        return "high"
    if score >= 0.45:
        return "medium"
    return "low"


def _build_patchcore_description(
    *,
    location: str | None,
    size_label: str,
    shape_label: str,
    texture_hint: str,
    severity_hint: str,
) -> str:
    zh_size = {"small": "小型", "medium": "中等大小", "large": "较大"}
    zh_shape = {
        "elongated-horizontal": "横向细长",
        "elongated-vertical": "纵向细长",
        "compact": "紧凑块状",
        "irregular": "不规则",
    }
    zh_severity = {"low": "较弱", "medium": "中等", "high": "较强"}
    texture_map = {
        "sharp linear response": "线性边缘较明显",
        "dense high-contrast region": "局部对比度高",
        "localized contrast variation": "局部存在对比变化",
        "faint diffuse response": "响应较弱且略分散",
    }
    prefix = f"在{location}区域" if location else "在图像中"
    return (
        f"{prefix}发现一处{zh_size.get(size_label, '局部')}{zh_shape.get(shape_label, '异常')}异常热区，"
        f"整体响应{zh_severity.get(severity_hint, '中等')}，{texture_map.get(texture_hint, texture_hint)}。"
    )


def _extract_anomalies_from_heatmap(
    heatmap: np.ndarray,
    threshold: float,
    image_size: tuple[int, int],
) -> list[dict[str, Any]]:
    width, height = image_size
    mask = (heatmap >= threshold).astype(np.uint8)
    num_labels, _, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    anomalies: list[dict[str, Any]] = []
    min_area = max(16, int(0.0005 * width * height))

    for index in range(1, num_labels):
        x, y, w, h, area = stats[index]
        if int(area) < min_area:
            continue

        component = heatmap[y : y + h, x : x + w]
        score = float(component.max()) if component.size else 0.0
        bbox = [int(x), int(y), int(x + w), int(y + h)]
        area_ratio = float(area) / float(max(1, width * height))
        box_width = max(1, w)
        box_height = max(1, h)
        location = _derive_location_text(bbox, image_size)
        size_label = _derive_size_label(area_ratio)
        shape_label = _derive_shape_label(box_width / max(width, 1), box_height / max(height, 1))
        texture_hint = _derive_texture_hint(score, bbox)
        color_hint = _derive_color_hint(score)
        severity_hint = _derive_severity_hint(score)
        anomalies.append(
            {
                "type": "surface_anomaly",
                "score": round(score, 4),
                "details": "PatchCore anomaly region",
                "bbox": bbox,
                "location": location,
                "has_localization": True,
                "appearance": {
                    "shape": shape_label,
                    "size": size_label,
                    "texture": texture_hint,
                    "color_hint": color_hint,
                },
                "severity_hint": severity_hint,
                "description": _build_patchcore_description(
                    location=location,
                    size_label=size_label,
                    shape_label=shape_label,
                    texture_hint=texture_hint,
                    severity_hint=severity_hint,
                ),
            }
        )

    anomalies.sort(key=lambda item: float(item.get("score", 0.0)), reverse=True)
    return anomalies


def resolve_patchcore_category(task: DetectionTask) -> str:
    detector_params = (task.parameters or {}).get("detector_params") or {}
    category = (
        detector_params.get("category")
        or (task.parameters or {}).get("patchcore_category")
        or settings.patchcore_default_category
    )
    return str(category).strip().lower()


def get_patchcore_artifacts(category: str) -> PatchCoreArtifacts:
    model_dir = Path(settings.patchcore_model_root) / category
    return PatchCoreArtifacts(
        category=category,
        model_dir=model_dir,
        memory_bank_path=model_dir / "memory_bank.pt",
        metadata_path=model_dir / "metadata.json",
    )


def trained_patchcore_categories(model_root: str | Path | None = None) -> list[str]:
    root = Path(model_root or settings.patchcore_model_root)
    if not root.exists():
        return []
    categories: list[str] = []
    for item in root.iterdir():
        if not item.is_dir():
            continue
        if (item / "memory_bank.pt").exists() and (item / "metadata.json").exists():
            categories.append(item.name)
    return sorted(categories)


def get_patchcore_category_status(category: str) -> dict[str, Any]:
    normalized = str(category or "").strip().lower()
    artifacts = get_patchcore_artifacts(normalized)
    dataset_categories = available_mvtec_categories(settings.rag_dataset_root)
    metadata: dict[str, Any] = {}
    if artifacts.metadata_path.exists():
        try:
            metadata = json.loads(artifacts.metadata_path.read_text(encoding="utf-8"))
        except Exception:
            metadata = {}

    return {
        "category": normalized,
        "dataset_available": normalized in dataset_categories,
        "trained": artifacts.memory_bank_path.exists() and artifacts.metadata_path.exists(),
        "model_dir": str(artifacts.model_dir).replace("\\", "/"),
        "memory_bank_path": str(artifacts.memory_bank_path).replace("\\", "/"),
        "metadata_path": str(artifacts.metadata_path).replace("\\", "/"),
        "metadata": metadata,
    }


def train_patchcore_category(
    category: str,
    dataset_root: str | Path,
    model_root: str | Path,
    image_size: int,
    backbone_name: str,
    pretrained_backbone: bool,
    device: str,
    max_memory_bank: int,
) -> dict[str, Any]:
    dataset_root = Path(dataset_root)
    train_dir = dataset_root / category / "train" / "good"
    if not train_dir.exists():
        raise FileNotFoundError(f"Missing MVTec train/good directory: {train_dir}")

    model_dir = Path(model_root) / category
    model_dir.mkdir(parents=True, exist_ok=True)

    extractor = _build_feature_extractor(backbone_name, pretrained_backbone).to(device)
    image_paths = sorted(path for path in train_dir.iterdir() if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".bmp"})
    if not image_paths:
        raise FileNotFoundError(f"No training images found in {train_dir}")

    memory_parts: list[torch.Tensor] = []
    for image_path in image_paths:
        _, tensor = _load_image(image_path, image_size)
        memory_parts.append(_extract_patch_embeddings(extractor, tensor, device))

    memory_bank = torch.cat(memory_parts, dim=0)
    memory_bank = _subsample_memory_bank(memory_bank, max_memory_bank)

    train_scores: list[float] = []
    for image_path in image_paths[: min(len(image_paths), 16)]:
        _, tensor = _load_image(image_path, image_size)
        embeddings = _extract_patch_embeddings(extractor, tensor, device)
        patch_scores = _score_embeddings(embeddings, memory_bank)
        train_scores.append(float(patch_scores.max().item()))

    score_mean = float(np.mean(train_scores)) if train_scores else 0.0
    score_std = float(np.std(train_scores)) if train_scores else 0.0
    recommended_threshold = score_mean + 3.0 * score_std

    torch.save(memory_bank, model_dir / "memory_bank.pt")
    metadata = {
        "category": category,
        "dataset_root": str(dataset_root).replace("\\", "/"),
        "image_size": image_size,
        "backbone": backbone_name,
        "pretrained_backbone": pretrained_backbone,
        "device": device,
        "memory_bank_size": int(memory_bank.shape[0]),
        "feature_dim": int(memory_bank.shape[1]),
        "recommended_threshold": recommended_threshold,
    }
    (model_dir / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return metadata


def predict_patchcore_image(
    image_path: str | Path,
    category: str,
    threshold: float,
    task_id: str,
) -> dict[str, Any]:
    artifacts = get_patchcore_artifacts(category)
    if not artifacts.memory_bank_path.exists():
        raise FileNotFoundError(
            f"PatchCore memory bank not found for category '{category}'. "
            f"Expected {artifacts.memory_bank_path}"
        )
    if not artifacts.metadata_path.exists():
        raise FileNotFoundError(
            f"PatchCore metadata not found for category '{category}'. "
            f"Expected {artifacts.metadata_path}"
        )

    metadata = json.loads(artifacts.metadata_path.read_text(encoding="utf-8"))
    image_size = int(metadata.get("image_size") or settings.patchcore_image_size)
    backbone_name = str(metadata.get("backbone") or settings.patchcore_backbone)
    pretrained_backbone = bool(metadata.get("pretrained_backbone", settings.patchcore_pretrained_backbone))
    device = str(metadata.get("device") or settings.patchcore_device)
    effective_threshold = float(threshold or metadata.get("recommended_threshold") or settings.patchcore_threshold)

    extractor = _build_feature_extractor(backbone_name, pretrained_backbone).to(device)
    try:
        memory_bank = torch.load(artifacts.memory_bank_path, map_location="cpu", weights_only=True)
    except TypeError:
        memory_bank = torch.load(artifacts.memory_bank_path, map_location="cpu")

    image, tensor = _load_image(image_path, image_size)
    embeddings = _extract_patch_embeddings(extractor, tensor, device)
    patch_scores = _score_embeddings(embeddings, memory_bank)

    fmap_side = int(np.sqrt(patch_scores.shape[0]))
    score_map = patch_scores.view(fmap_side, fmap_side).numpy()
    heatmap = _heatmap_from_scores(score_map, image.width, image.height)

    image_score = float(heatmap.max())
    anomalies = _extract_anomalies_from_heatmap(heatmap, effective_threshold, (image.width, image.height))
    saved_paths = _save_visualizations(image, heatmap, category, task_id, settings.patchcore_heatmap_dir)

    output_metadata = {
        "selected_backend": "patchcore",
        "category": category,
        "confidence": image_score,
        "anomaly_score": image_score,
        "threshold": effective_threshold,
        "localization_available": bool(anomalies),
        "image_size": [image.width, image.height],
        "memory_bank_size": int(memory_bank.shape[0]),
        **saved_paths,
    }
    summary = (
        f"PatchCore detected {len(anomalies)} anomalous region(s) for category '{category}'."
        if anomalies
        else f"PatchCore found no strong anomaly for category '{category}'."
    )
    return {
        "status": "success",
        "anomalies": anomalies,
        "summary": summary,
        "answer": summary,
        "metadata": output_metadata,
    }


class LocalPatchCoreImageAnomalyDetectionTool(BaseTool):
    name = "patchcore_image_anomaly_detection"

    async def run(self, task: DetectionTask) -> ToolResponse:
        image_b64 = (task.parameters or {}).get("image_base64")
        if not image_b64:
            raise ToolExecutionError(self.name, {"task_id": task.task_id}, ValueError("image_base64 missing"))

        category = resolve_patchcore_category(task)
        if category not in available_mvtec_categories(settings.rag_dataset_root):
            raise ConfigurationError(
                f"Unknown PatchCore category '{category}'",
                config_key="APP_PATCHCORE_DEFAULT_CATEGORY",
                details={"available_categories": available_mvtec_categories(settings.rag_dataset_root)},
            )

        artifacts = get_patchcore_artifacts(category)
        if not artifacts.memory_bank_path.exists() or not artifacts.metadata_path.exists():
            raise ConfigurationError(
                (
                    f"PatchCore category '{category}' is not trained. "
                    "Run scripts/patchcore_train.py for this category first or switch to the Qwen vision backend."
                ),
                config_key="APP_PATCHCORE_MODEL_ROOT",
                details={
                    "category": category,
                    "trained": False,
                    "expected_model_dir": str(artifacts.model_dir),
                    "expected_memory_bank": str(artifacts.memory_bank_path),
                    "expected_metadata": str(artifacts.metadata_path),
                    "trained_categories": trained_patchcore_categories(),
                    "fallback_backend": "qwen",
                },
            )

        detector_params = (task.parameters or {}).get("detector_params") or {}
        threshold = float(detector_params.get("threshold") or settings.patchcore_threshold)
        image_dir = Path(settings.patchcore_heatmap_dir) / category
        image_dir.mkdir(parents=True, exist_ok=True)
        image_path = image_dir / f"{task.task_id}_input.png"

        try:
            image_bytes = base64.b64decode(image_b64, validate=True)
            Image.open(io.BytesIO(image_bytes)).convert("RGB").save(image_path)
            payload = predict_patchcore_image(
                image_path=image_path,
                category=category,
                threshold=threshold,
                task_id=task.task_id,
            )
        except Exception as exc:
            raise ToolExecutionError(self.name, {"task_id": task.task_id, "category": category}, exc) from exc

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
