"""Retrieval interface for anomaly detection."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.rag.vector_store import VectorStore


class AnomalyRetriever:
    """Retrieve anomaly references from vector store."""

    def __init__(self, vector_store: VectorStore):
        self.vector_store = vector_store

    def retrieve_similar(
        self,
        *,
        query_description: str,
        top_k: int,
        category: Optional[str] = None,
        only_anomaly: Optional[bool] = True,
    ) -> List[Dict[str, Any]]:
        return self.vector_store.query_text(
            query_text=query_description,
            top_k=top_k,
            category=category,
            only_anomaly=only_anomaly,
        )

    def retrieve_similar_by_image(
        self,
        *,
        image_path: str,
        top_k: int,
        category: Optional[str] = None,
        only_anomaly: Optional[bool] = True,
    ) -> List[Dict[str, Any]]:
        return self.vector_store.query_image(
            image_path=image_path,
            top_k=top_k,
            category=category,
            only_anomaly=only_anomaly,
        )

    def format_for_prompt(self, rows: List[Dict[str, Any]]) -> str:
        if not rows:
            return "未检索到相似工业异常样本。"

        parts: list[str] = ["RAG相似案例参考："]
        for idx, row in enumerate(rows, start=1):
            meta = row.get("metadata") or {}
            sim = 1 - float(row.get("distance", 1.0))
            parts.append(
                (
                    f"{idx}. 描述: {row.get('description', '')}\n"
                    f"   类别: {meta.get('category', 'unknown')}\n"
                    f"   异常类型: {meta.get('anomaly_type', 'unknown')}\n"
                    f"   严重程度: {meta.get('severity', 'unknown')}\n"
                    f"   相似度: {sim:.2%}"
                )
            )
        return "\n".join(parts)
