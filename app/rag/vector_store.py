"""Vector storage and retrieval using DashScope multimodal fused embeddings."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import chromadb

from app.config.settings import settings
from app.rag.dataset_analyzer import ImageMetadata

try:  # pragma: no cover
    from dashscope import MultiModalEmbedding
except Exception:  # pragma: no cover
    MultiModalEmbedding = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)


class VectorStore:
    """Manage fused multimodal vectors for anomaly retrieval."""

    def __init__(self, persist_dir: str | Path):
        self.persist_dir = Path(persist_dir)
        self.persist_dir.mkdir(parents=True, exist_ok=True)

        self.client = chromadb.PersistentClient(path=str(self.persist_dir))
        self.fused_collection = self.client.get_or_create_collection(
            name="anomaly_cases_fused",
            metadata={"hnsw:space": "cosine"},
        )

        self._mm_embedding_disabled = False
        if not settings.openai_api_key:
            self._mm_embedding_disabled = True
            logger.warning("DashScope API key missing, multimodal vector retrieval will be unavailable")

        if MultiModalEmbedding is None:
            self._mm_embedding_disabled = True
            logger.warning("dashscope SDK not installed, multimodal embedding unavailable")

    def _to_file_uri(self, image_path: str) -> str:
        path = Path(image_path)
        if not path.exists():
            return image_path
        # DashScope SDK on Windows may mis-handle file:// URIs as '/E:/...'.
        # Use normalized absolute local path instead.
        return str(path.resolve()).replace("\\", "/")

    def _extract_embedding(self, response: Any) -> Optional[List[float]]:
        output = None
        if isinstance(response, dict):
            output = response.get("output")
        else:
            output = getattr(response, "output", None)

        if not isinstance(output, dict):
            return None

        embeddings = output.get("embeddings") or output.get("results") or []
        if not embeddings:
            return None

        first = embeddings[0] if isinstance(embeddings, list) else None
        if not isinstance(first, dict):
            return None

        vec = first.get("embedding") or first.get("vector")
        if not isinstance(vec, list):
            return None

        try:
            return [float(v) for v in vec]
        except Exception:
            return None

    def _embed_fused(self, *, image_path: Optional[str], text: Optional[str]) -> Optional[List[float]]:
        if self._mm_embedding_disabled:
            return None
        if MultiModalEmbedding is None:
            return None

        payload: Dict[str, Any] = {}
        if image_path:
            payload["image"] = self._to_file_uri(image_path)

        content = (text or "").strip()
        if content:
            payload["text"] = content

        if not payload:
            return None

        try:
            response = MultiModalEmbedding.call(
                model=settings.rag_multimodal_embedding_model,
                api_key=settings.openai_api_key,
                input=[payload],
            )
            vec = self._extract_embedding(response)
            if vec is None:
                logger.warning("Multimodal embedding response has no usable vector")
            return vec
        except Exception as exc:
            logger.warning("Multimodal embedding failed: %s", exc)
            return None

    def _build_metadata(self, metadata: ImageMetadata, source: str) -> Dict[str, Any]:
        return {
            "source": source,
            "image_path": metadata.image_path,
            "category": metadata.category,
            "split": metadata.split,
            "is_anomaly": metadata.is_anomaly,
            "anomaly_type": metadata.anomaly_type or "good",
            "severity": metadata.severity or "unknown",
            "mask_path": metadata.mask_path or "",
        }

    def upsert_case(self, metadata: ImageMetadata, description: str, source: str = "dataset") -> None:
        fused_embedding = self._embed_fused(image_path=metadata.image_path, text=description)
        if fused_embedding is None:
            logger.warning("Skip sample without multimodal embedding: %s", metadata.image_id)
            return

        self.fused_collection.upsert(
            ids=[metadata.image_id],
            embeddings=[fused_embedding],
            documents=[description],
            metadatas=[self._build_metadata(metadata, source)],
        )

    def upsert_user_case(
        self,
        *,
        image_id: str,
        image_path: str,
        category: str,
        user_description: str,
        model_confidence: float,
        is_anomaly: bool,
        anomaly_type: Optional[str],
        severity: Optional[str],
        source: str = "user_feedback",
    ) -> bool:
        if model_confidence < settings.rag_learning_threshold:
            return False

        metadata = ImageMetadata(
            image_path=image_path,
            category=category,
            is_anomaly=is_anomaly,
            split="online",
            image_id=image_id,
            anomaly_type=anomaly_type,
            severity=severity or "unknown",
        )

        enriched = (
            f"{user_description}\n"
            f"模型置信度: {model_confidence:.3f}。"
            f"来源: 线上高置信样本。"
        )
        self.upsert_case(metadata, enriched, source=source)
        return True

    def batch_upsert(
        self,
        rows: List[tuple[ImageMetadata, str]],
        source: str = "dataset",
        progress_callback: Optional[callable] = None,
    ) -> None:
        total = len(rows)
        for idx, (metadata, description) in enumerate(rows, start=1):
            self.upsert_case(metadata, description, source=source)
            if progress_callback:
                progress_callback(idx, total)

    def _build_where_clause(self, category: Optional[str], only_anomaly: Optional[bool]) -> Optional[Dict[str, Any]]:
        conditions = []
        if category:
            conditions.append({"category": {"$eq": category}})
        if only_anomaly is not None:
            conditions.append({"is_anomaly": {"$eq": only_anomaly}})

        if not conditions:
            return None
        if len(conditions) == 1:
            return conditions[0]
        return {"$and": conditions}

    def query_text(
        self,
        *,
        query_text: str,
        top_k: int = 5,
        category: Optional[str] = None,
        only_anomaly: Optional[bool] = None,
    ) -> List[Dict[str, Any]]:
        embedding = self._embed_fused(image_path=None, text=query_text)
        if embedding is None:
            return []

        where = self._build_where_clause(category, only_anomaly)

        results = self.fused_collection.query(
            query_embeddings=[embedding],
            n_results=top_k,
            where=where,
        )
        return self._format_query_results(results)

    def query_image(
        self,
        *,
        image_path: str,
        top_k: int = 5,
        category: Optional[str] = None,
        only_anomaly: Optional[bool] = None,
    ) -> List[Dict[str, Any]]:
        embedding = self._embed_fused(image_path=image_path, text=None)
        if embedding is None:
            return []

        where = self._build_where_clause(category, only_anomaly)

        results = self.fused_collection.query(
            query_embeddings=[embedding],
            n_results=top_k,
            where=where,
        )
        return self._format_query_results(results)

    def query(
        self,
        *,
        query_text: str,
        top_k: int = 5,
        category: Optional[str] = None,
        only_anomaly: Optional[bool] = None,
    ) -> List[Dict[str, Any]]:
        return self.query_text(
            query_text=query_text,
            top_k=top_k,
            category=category,
            only_anomaly=only_anomaly,
        )

    def _format_query_results(self, results: Dict[str, Any]) -> List[Dict[str, Any]]:
        output: List[Dict[str, Any]] = []
        ids = results.get("ids", [[]])[0]
        docs = results.get("documents", [[]])[0]
        dists = results.get("distances", [[]])[0]
        metas = results.get("metadatas", [[]])[0]

        for i, row_id in enumerate(ids):
            output.append(
                {
                    "id": row_id,
                    "description": docs[i],
                    "distance": dists[i],
                    "metadata": metas[i],
                }
            )
        return output

    def count(self) -> int:
        return self.fused_collection.count()
