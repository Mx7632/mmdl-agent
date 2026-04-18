"""RAG orchestration service for dataset indexing and online learning."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

from app.config.settings import settings
from app.rag.dataset_analyzer import DatasetAnalyzer
from app.rag.retriever import AnomalyRetriever
from app.rag.text_generator import AnomalyTextGenerator
from app.rag.vector_store import VectorStore


class RagService:
    def __init__(self) -> None:
        self.vector_store = VectorStore(settings.rag_vector_dir)
        self.retriever = AnomalyRetriever(self.vector_store)
        self.text_generator = AnomalyTextGenerator()

    def build_from_dataset(self, dataset_root: Optional[str] = None, include_normal: bool = True) -> Dict[str, Any]:
        root = dataset_root or settings.rag_dataset_root
        analyzer = DatasetAnalyzer(root)
        stats = analyzer.analyze()
        analyzer.save_metadata(settings.rag_metadata_path)

        rows = analyzer.get_all() if include_normal else analyzer.get_anomalies()
        payload = [(row, self.text_generator.generate(row)) for row in rows]
        self.vector_store.batch_upsert(payload, source="dataset")

        return {
            "dataset_root": root,
            "indexed_rows": len(payload),
            "vector_count": self.vector_store.count(),
            "stats": stats,
        }

    def query_rows(self, query_text: str, category: Optional[str], top_k: Optional[int]) -> list[dict[str, Any]]:
        k = top_k or settings.rag_top_k
        return self.retriever.retrieve_similar(
            query_description=query_text,
            top_k=k,
            category=category,
            only_anomaly=True,
        )

    def query_rows_by_image(self, image_path: str, category: Optional[str], top_k: Optional[int]) -> list[dict[str, Any]]:
        k = top_k or settings.rag_top_k
        return self.retriever.retrieve_similar_by_image(
            image_path=image_path,
            top_k=k,
            category=category,
            only_anomaly=True,
        )

    def query_similar(self, query_text: str, category: Optional[str], top_k: Optional[int]) -> str:
        rows = self.query_rows(query_text=query_text, category=category, top_k=top_k)
        return self.retriever.format_for_prompt(rows)

    def add_online_case(
        self,
        *,
        image_path: str,
        category: str,
        user_description: str,
        model_confidence: float,
        is_anomaly: bool,
        anomaly_type: Optional[str],
        severity: Optional[str],
    ) -> bool:
        image_file = Path(image_path)
        image_id = f"online_{image_file.stem}"
        return self.vector_store.upsert_user_case(
            image_id=image_id,
            image_path=str(image_file),
            category=category,
            user_description=user_description,
            model_confidence=model_confidence,
            is_anomaly=is_anomaly,
            anomaly_type=anomaly_type,
            severity=severity,
        )


def build_anomaly_query_text(anomalies: list[dict[str, Any]]) -> str:
    if not anomalies:
        return ""

    parts: list[str] = []
    for item in anomalies:
        anomaly_type = item.get("type", "unknown")
        details = item.get("details", "")
        score = item.get("score", 0)
        parts.append(f"异常类型:{anomaly_type}; 置信度:{score}; 细节:{details}")
    return " | ".join(parts)


_rag_service: Optional[RagService] = None


def get_rag_service() -> RagService:
    global _rag_service
    if _rag_service is None:
        _rag_service = RagService()
    return _rag_service
