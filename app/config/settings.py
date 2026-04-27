# 配置管理，基于 pydantic-settings 读取环境变量
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置类"""

    model_config = SettingsConfigDict(env_file=".env", env_prefix="APP_", extra="ignore")

    # 应用基础配置
    app_name: str = "industrial-anomaly-agent"
    log_level: str = "INFO"
    enable_tracing: bool = False
    checkpoint_backend: str = "postgres"
    database_url: str = ""
    database_schema: str = "public"

    # 异常检测服务配置（供 HttpAnomalyDetectionTool 使用）
    anomaly_detection_url: str = "http://localhost:8080/"  # TODO: 后续改为可配置/服务发现
    anomaly_detection_timeout: float = 30.0

    # LLM 配置（供 summarize_node 使用）
    openai_api_key: str = "sk-e47fe58e1afe4db2ba6d340373b48919"
    llm_model: str = "qwen3.5-plus"
    llm_temperature: float = 0.3
    llm_timeout: float = 60.0
    llm_max_tokens: int = 500
    llm_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"

    # Vision LLM (qwen3.5-plus) config (for image anomaly detection)
    llm_vision_model: str = "qwen3.5-plus"  # TODO: Switching to local CV makes this unused.
    vision_detector_backend: str = "qwen"
    professional_vision_detector_type: str = "anomalygpt"
    professional_vision_detector_url: str = ""
    professional_vision_detector_timeout: float = 30.0
    professional_vision_detector_aliases: str = (
        "anomalygpt,anomaly_gpt,specialist-http,specialist_http,professional"
    )

    # RAG 配置
    rag_enabled: bool = True
    rag_dataset_root: str = "data_sets/mvtec_anomaly_detection"
    rag_vector_dir: str = "data/rag/chroma"
    rag_metadata_path: str = "data/rag/dataset_metadata.json"
    rag_descriptions_path: str = "data/rag/anomaly_descriptions.json"
    rag_top_k: int = 3
    rag_learning_threshold: float = 0.85
    rag_multimodal_embedding_model: str = "multimodal-embedding-v1"

settings = Settings()
