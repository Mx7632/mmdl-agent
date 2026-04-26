from __future__ import annotations

import base64
import importlib
import io
import sys
import tempfile
from pathlib import Path
from typing import Any

import numpy as np
from fastapi import FastAPI
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from PIL import Image

try:
    import cv2  # type: ignore
except Exception:  # pragma: no cover
    cv2 = None


class ServiceSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ANOMALYGPT_SERVICE_", extra="ignore")

    repo_dir: str = ""
    host: str = "127.0.0.1"
    port: int = 9001
    device: str = "cuda"
    precision: str = "fp16"
    imagebind_ckpt_path: str = "../pretrained_ckpt/imagebind_ckpt/imagebind_huge.pth"
    vicuna_ckpt_path: str = "../pretrained_ckpt/vicuna_ckpt/7b_v0"
    anomalygpt_ckpt_path: str = "./ckpt/train_supervised/pytorch_model.pt"
    delta_ckpt_path: str = "../pretrained_ckpt/pandagpt_ckpt/7b/pytorch_model.pt"
    stage: int = 2
    max_tgt_len: int = 128
    top_p: float = 0.01
    temperature: float = 1.0
    lora_r: int = 32
    lora_alpha: int = 32
    lora_dropout: float = 0.1
    mask_threshold: float = 0.5


settings = ServiceSettings()


class DetectRequest(BaseModel):
    task_id: str
    asset_id: str
    question: str | None = None
    image_base64: str
    image_mime: str = "image/jpeg"
    normal_image_base64: str | None = None
    normal_image_mime: str = "image/jpeg"
    detector_type: str = "anomalygpt"
    detector_params: dict[str, Any] = Field(default_factory=dict)
    parameters: dict[str, Any] = Field(default_factory=dict)


class DetectResponse(BaseModel):
    task_id: str
    status: str
    answer: str | None = None
    summary: str | None = None
    anomalies: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AnomalyGPTService:
    def __init__(self) -> None:
        self._model = None
        self._torch = None

    def _repo_code_dir(self) -> Path:
        if not settings.repo_dir:
            raise RuntimeError("ANOMALYGPT_SERVICE_REPO_DIR is not configured")
        repo_dir = Path(settings.repo_dir).expanduser().resolve()
        code_dir = repo_dir / "code"
        if not code_dir.exists():
            raise RuntimeError(f"AnomalyGPT code directory not found: {code_dir}")
        return code_dir

    def _model_args(self) -> dict[str, Any]:
        code_dir = self._repo_code_dir()
        return {
            "model": "openllama_peft",
            "imagebind_ckpt_path": str((code_dir / settings.imagebind_ckpt_path).resolve()),
            "vicuna_ckpt_path": str((code_dir / settings.vicuna_ckpt_path).resolve()),
            "anomalygpt_ckpt_path": str((code_dir / settings.anomalygpt_ckpt_path).resolve()),
            "delta_ckpt_path": str((code_dir / settings.delta_ckpt_path).resolve()),
            "stage": settings.stage,
            "max_tgt_len": settings.max_tgt_len,
            "lora_r": settings.lora_r,
            "lora_alpha": settings.lora_alpha,
            "lora_dropout": settings.lora_dropout,
        }

    def load(self) -> None:
        if self._model is not None:
            return

        code_dir = self._repo_code_dir()
        if str(code_dir) not in sys.path:
            sys.path.insert(0, str(code_dir))

        torch = importlib.import_module("torch")
        openllama_module = importlib.import_module("model.openllama")
        model_cls = getattr(openllama_module, "OpenLLAMAPEFTModel")
        args = self._model_args()

        model = model_cls(**args)
        delta_ckpt = torch.load(args["delta_ckpt_path"], map_location=torch.device("cpu"))
        model.load_state_dict(delta_ckpt, strict=False)
        anomaly_ckpt = torch.load(args["anomalygpt_ckpt_path"], map_location=torch.device("cpu"))
        model.load_state_dict(anomaly_ckpt, strict=False)
        model = model.eval()

        if settings.precision.lower() == "fp16":
            model = model.half()
        if settings.device.startswith("cuda"):
            model = model.cuda()
        else:
            model = model.to(settings.device)

        self._torch = torch
        self._model = model

    def predict(self, request: DetectRequest) -> DetectResponse:
        self.load()
        assert self._model is not None
        assert self._torch is not None

        question = (request.question or "请判断图像是否存在工业异常，并指出异常区域。").strip()
        top_p = float(request.detector_params.get("top_p", settings.top_p))
        temperature = float(request.detector_params.get("temperature", settings.temperature))
        max_tgt_len = int(request.detector_params.get("max_tgt_len", settings.max_tgt_len))

        image_bytes = base64.b64decode(request.image_base64)
        normal_bytes = (
            base64.b64decode(request.normal_image_base64) if request.normal_image_base64 else None
        )

        with tempfile.TemporaryDirectory(prefix="anomalygpt-") as tmpdir:
            tmpdir_path = Path(tmpdir)
            image_path = tmpdir_path / "query.png"
            image_path.write_bytes(image_bytes)

            normal_path: Path | None = None
            if normal_bytes:
                normal_path = tmpdir_path / "normal.png"
                normal_path.write_bytes(normal_bytes)

            with self._torch.inference_mode():
                response_text, pixel_output = self._model.generate(
                    {
                        "prompt": question,
                        "image_paths": [str(image_path)],
                        "normal_img_paths": [str(normal_path)] if normal_path else [],
                        "audio_paths": [],
                        "video_paths": [],
                        "thermal_paths": [],
                        "top_p": top_p,
                        "temperature": temperature,
                        "max_tgt_len": max_tgt_len,
                        "modality_embeds": [],
                    },
                    web_demo=True,
                )

        mask_array = self._to_mask_array(pixel_output)
        anomalies = self._mask_to_anomalies(mask_array, response_text, request.detector_params)
        mask_base64 = self._mask_to_base64(mask_array)

        return DetectResponse(
            task_id=request.task_id,
            status="success",
            answer=response_text,
            summary=response_text,
            anomalies=anomalies,
            metadata={
                "tool": "anomalygpt_local_service",
                "detector_type": request.detector_type,
                "device": settings.device,
                "precision": settings.precision,
                "localization_mask_base64": mask_base64,
            },
        )

    def _to_mask_array(self, pixel_output: Any) -> np.ndarray:
        tensor = pixel_output.detach().float().reshape(224, 224).cpu().numpy()
        tensor = tensor - tensor.min()
        max_value = float(tensor.max())
        if max_value > 0:
            tensor = tensor / max_value
        return tensor.astype(np.float32)

    def _mask_to_anomalies(
        self,
        mask_array: np.ndarray,
        response_text: str,
        detector_params: dict[str, Any],
    ) -> list[dict[str, Any]]:
        threshold = float(detector_params.get("mask_threshold", settings.mask_threshold))
        binary = (mask_array >= threshold).astype(np.uint8)
        if binary.max() == 0:
            return []

        if cv2 is not None:
            count, labels, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
            anomalies: list[dict[str, Any]] = []
            for component_id in range(1, count):
                x, y, w, h, area = stats[component_id]
                component_mask = labels == component_id
                score = float(mask_array[component_mask].max())
                anomalies.append(
                    {
                        "type": "visual_anomaly",
                        "score": round(score, 4),
                        "details": response_text,
                        "bbox": [int(x), int(y), int(x + w), int(y + h)],
                        "area": int(area),
                    }
                )
            if anomalies:
                return anomalies

        ys, xs = np.where(binary > 0)
        return [
            {
                "type": "visual_anomaly",
                "score": round(float(mask_array.max()), 4),
                "details": response_text,
                "bbox": [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())],
                "area": int(binary.sum()),
            }
        ]

    def _mask_to_base64(self, mask_array: np.ndarray) -> str:
        image = Image.fromarray((mask_array * 255).astype(np.uint8), mode="L")
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        return base64.b64encode(buffer.getvalue()).decode("ascii")


service = AnomalyGPTService()
app = FastAPI(title="AnomalyGPT Local Service", version="0.1.0")


@app.get("/health")
def health() -> dict[str, Any]:
    loaded = service._model is not None
    return {
        "status": "ok",
        "service": "anomalygpt_local",
        "model_loaded": loaded,
        "repo_dir": settings.repo_dir,
        "device": settings.device,
    }


@app.post("/detect", response_model=DetectResponse)
def detect(request: DetectRequest) -> DetectResponse:
    return service.predict(request)
