"""Vector storage and retrieval using Chroma."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import chromadb
import cv2
import numpy as np
from langchain_openai import OpenAIEmbeddings

from app.config.settings import settings
from app.rag.dataset_analyzer import ImageMetadata

logger = logging.getLogger(__name__)


class VectorStore:
    """Manage vector storage for anomaly images and text descriptions."""

    def __init__(self, persist_dir: str | Path):
        self.persist_dir = Path(persist_dir)
        self.persist_dir.mkdir(parents=True, exist_ok=True)

        self.client = chromadb.PersistentClient(path=str(self.persist_dir))
        self.text_collection = self.client.get_or_create_collection(
            name="anomaly_cases_text",
            metadata={"hnsw:space": "cosine"},
        )
        self.image_collection = self.client.get_or_create_collection(
            name="anomaly_cases_image",
            metadata={"hnsw:space": "cosine"},
        )

        self.embeddings: Optional[OpenAIEmbeddings] = None
        if settings.openai_api_key:
            self.embeddings = OpenAIEmbeddings(
                model="text-embedding-3-small",
                api_key=settings.openai_api_key,
            )
        else:
            logger.warning("OpenAI API key missing, vector retrieval will be unavailable")

    def _embed_text(self, text: str) -> Optional[List[float]]:
        if not self.embeddings:
            return None
        return self.embeddings.embed_query(text)

    def _embed_image(self, image_path: str) -> Optional[List[float]]:
        """Generate deterministic image feature embedding from histogram + edges."""
        try:
            image = cv2.imread(image_path, cv2.IMREAD_COLOR)
            if image is None:
                return None

            hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
            hist = cv2.calcHist([hsv], [0, 1, 2], None, [8, 4, 4], [0, 180, 0, 256, 0, 256])
            hist = cv2.normalize(hist, hist).flatten()

            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            edges = cv2.Canny(gray, 50, 150)
            edge_ratio = float(np.count_nonzero(edges)) / float(edges.size)

            shape_ratio = [float(image.shape[0]) / max(1.0, float(image.shape[1]))]
            feature = np.concatenate([hist.astype(np.float32), np.array([edge_ratio], dtype=np.float32), np.array(shape_ratio, dtype=np.float32)])
            return feature.tolist()
        except Exception as exc:
            logger.warning("Failed to embed image %s: %s", image_path, exc)
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
        text_embedding = self._embed_text(description)
        image_embedding = self._embed_image(metadata.image_path)

        if text_embedding is not None:
            self.text_collection.upsert(
                ids=[metadata.image_id],
                embeddings=[text_embedding],
                documents=[description],
                metadatas=[self._build_metadata(metadata, source)],
            )

        if image_embedding is not None:
            self.image_collection.upsert(
                ids=[metadata.image_id],
                embeddings=[image_embedding],
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

    def batch_upsert(self, rows: List[tuple[ImageMetadata, str]], source: str = "dataset") -> None:
        for metadata, description in rows:
            self.upsert_case(metadata, description, source=source)

    def query_text(
        self,
        *,
        query_text: str,
        top_k: int = 5,
        category: Optional[str] = None,
        only_anomaly: Optional[bool] = None,
    ) -> List[Dict[str, Any]]:
        embedding = self._embed_text(query_text)
        if embedding is None:
            return []

        where: Dict[str, Any] = {}
        if category:
            where["category"] = {"$eq": category}
        if only_anomaly is not None:
            where["is_anomaly"] = {"$eq": only_anomaly}

        results = self.text_collection.query(
            query_embeddings=[embedding],
            n_results=top_k,
            where=where or None,
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
        embedding = self._embed_image(image_path)
        if embedding is None:
            return []

        where: Dict[str, Any] = {}
        if category:
            where["category"] = {"$eq": category}
        if only_anomaly is not None:
            where["is_anomaly"] = {"$eq": only_anomaly}

        results = self.image_collection.query(
            query_embeddings=[embedding],
            n_results=top_k,
            where=where or None,
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
        return max(self.text_collection.count(), self.image_collection.count())
