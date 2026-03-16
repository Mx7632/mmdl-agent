# 配置管理，基于 pydantic-settings 读取环境变量
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置类"""

    model_config = SettingsConfigDict(env_file=".env", env_prefix="APP_")

    # 应用基础配置
    app_name: str = "industrial-anomaly-agent"
    log_level: str = "INFO"
    enable_tracing: bool = False

    # 异常检测服务配置（供 HttpAnomalyDetectionTool 使用）
    anomaly_detection_url: str = "http://localhost:8080/"  #Todo 后期要修改的核心地方 
    anomaly_detection_timeout: float = 30.0

    # LLM 配置（供 summarize_node 使用）
    openai_api_key: str = "sk-c68a4a60a183496aad06b257b07eeed2"
    llm_model: str = "qwen3.5-plus"
    llm_temperature: float = 0.3
    llm_timeout: float = 60.0
    llm_max_tokens: int = 500
    llm_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"

    # Vision LLM (qwen3.5-plus) config (for image anomaly detection)
    llm_vision_model: str = "qwen3.5-plus"    # TODO: When switching to local CV inference, this section becomes unused.

settings = Settings()
