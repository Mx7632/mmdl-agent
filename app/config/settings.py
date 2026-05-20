from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", env_prefix="APP_", extra="ignore")

    app_name: str = "industrial-anomaly-agent"
    log_level: str = "INFO"
    enable_tracing: bool = False
    checkpoint_backend: str = "postgres"
    database_url: str = ""
    database_schema: str = "public"

    anomaly_detection_url: str = "http://localhost:8080/"
    anomaly_detection_timeout: float = 30.0

    openai_api_key: str = ""
    llm_model: str = "qwen3.5-plus"
    llm_temperature: float = 0.3
    llm_timeout: float = 60.0
    llm_max_tokens: int = 500
    llm_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"

    llm_vision_model: str = "qwen3.5-plus"
    vision_detector_backend: str = "qwen"
    qwen_min_anomaly_score: float = 0.65
    professional_vision_detector_type: str = "anomalygpt"
    professional_vision_detector_url: str = ""
    professional_vision_detector_timeout: float = 30.0
    professional_vision_detector_aliases: str = (
        "anomalygpt,anomaly_gpt,specialist-http,specialist_http,professional"
    )
    grad_detector_url: str = ""
    grad_detector_timeout: float = 60.0
    grad_detector_aliases: str = "grad,bi_grid,bi-grid"

    patchcore_model_root: str = "models/patchcore"
    patchcore_device: str = "cpu"
    patchcore_default_category: str = "bottle"
    patchcore_threshold: float = 0.5
    patchcore_image_size: int = 256
    patchcore_backbone: str = "resnet18"
    patchcore_pretrained_backbone: bool = False
    patchcore_max_memory_bank: int = 10000
    patchcore_heatmap_dir: str = "data/heatmaps"
    patchcore_detector_aliases: str = "patchcore,patch_core"

    rag_enabled: bool = True
    rag_dataset_root: str = "data_sets/mvtec_anomaly_detection"
    rag_vector_dir: str = "data/rag/chroma"
    rag_metadata_path: str = "data/rag/dataset_metadata.json"
    rag_descriptions_path: str = "data/rag/anomaly_descriptions.json"
    rag_top_k: int = 3
    rag_learning_threshold: float = 0.85
    rag_multimodal_embedding_model: str = "multimodal-embedding-v1"

    allowed_origins: str = "http://127.0.0.1:8000,http://localhost:8000"
    require_api_token: bool = False
    api_token: str = ""
    low_confidence_review_threshold: float = 0.75
    runtime_store_path: str = "data/runtime/industrial_state.json"


settings = Settings()
