"""Generate text descriptions for anomaly metadata."""
from __future__ import annotations

import logging
from typing import Any

try:  # pragma: no cover
    from langchain_openai import ChatOpenAI
except Exception:  # pragma: no cover
    ChatOpenAI = None  # type: ignore[assignment]
from pydantic import SecretStr

from app.config.settings import settings
from app.rag.dataset_analyzer import ImageMetadata

logger = logging.getLogger(__name__)


class AnomalyTextGenerator:
    """Generate anomaly descriptions with LLM fallback to rules."""

    def __init__(self) -> None:
        self.llm: Any | None = None
        if settings.openai_api_key and ChatOpenAI is not None:
            try:
                self.llm = ChatOpenAI(
                    model=settings.llm_model,
                    temperature=0.2,
                    api_key=SecretStr(settings.openai_api_key),
                    timeout=settings.llm_timeout,
                    base_url=settings.llm_base_url,
                    extra_body={"enable_thinking": False},
                )
            except Exception as exc:  # pragma: no cover
                logger.warning("Failed to initialize text generator LLM: %s", exc)

    def generate(self, metadata: ImageMetadata) -> str:
        if self.llm:
            text = self._generate_with_llm(metadata)
            if text:
                return text
        return self._generate_with_rules(metadata)

    def generate_rule_only(self, metadata: ImageMetadata) -> str:
        return self._generate_with_rules(metadata)

    def _generate_with_llm(self, metadata: ImageMetadata) -> str:
        try:
            prompt = (
                "你是工业质检知识库构建助手。"
                "请根据以下结构化信息，输出 1-2 句中文检索描述，突出类别、是否异常、异常类型和严重程度。\n"
                f"category={metadata.category}; split={metadata.split}; "
                f"is_anomaly={metadata.is_anomaly}; anomaly_type={metadata.anomaly_type or 'good'}; "
                f"severity={metadata.severity or 'unknown'}"
            )
            resp = self.llm.invoke(prompt)
            content = getattr(resp, "content", "")
            return str(content).strip()
        except Exception as exc:  # pragma: no cover
            logger.warning("LLM text generation failed: %s", exc)
            return ""

    def _generate_with_rules(self, metadata: ImageMetadata) -> str:
        if metadata.is_anomaly:
            severity = metadata.severity or "unknown"
            return (
                f"工业异常样本。品类: {metadata.category}。"
                f"数据划分: {metadata.split}。"
                f"异常类型: {metadata.anomaly_type or 'unknown'}。"
                f"异常严重程度: {severity}。"
            )

        return (
            f"工业正常样本。品类: {metadata.category}。"
            f"数据划分: {metadata.split}。"
            f"状态: good / 无异常。"
        )

    def batch_generate(self, metadata_list: list[ImageMetadata]) -> dict[str, str]:
        return {metadata.image_id: self.generate(metadata) for metadata in metadata_list}
