"""RAG orchestration service for dataset indexing and online learning."""
from __future__ import annotations

import json
import threading
import uuid
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

        self._build_jobs: dict[str, dict[str, Any]] = {}
        self._jobs_lock = threading.Lock()

    def _set_job(self, task_id: str, data: dict[str, Any]) -> None:
        with self._jobs_lock:
            self._build_jobs[task_id] = {**(self._build_jobs.get(task_id, {})), **data}

    def start_build_job(self, dataset_root: Optional[str] = None, include_normal: bool = True) -> str:
        task_id = f"rag-build-{uuid.uuid4().hex[:12]}"
        self._set_job(
            task_id,
            {
                "task_id": task_id,
                "status": "running",
                "phase": "queued",
                "percent": 0,
                "message": "任务已创建，准备开始",
                "processed": 0,
                "total": 0,
                "result": None,
                "error": None,
            },
        )

        thread = threading.Thread(
            target=self._run_build_job,
            args=(task_id, dataset_root, include_normal),
            daemon=True,
        )
        thread.start()
        return task_id

    def _run_build_job(self, task_id: str, dataset_root: Optional[str], include_normal: bool) -> None:
        root = dataset_root or settings.rag_dataset_root
        try:
            analyzer = DatasetAnalyzer(root)

            def scan_progress(done: int, total: int, category: str) -> None:
                percent = int((done / max(total, 1)) * 20)
                self._set_job(
                    task_id,
                    {
                        "phase": "scanning",
                        "percent": percent,
                        "processed": done,
                        "total": total,
                        "message": f"扫描数据集类别: {category} ({done}/{total})",
                    },
                )

            stats = analyzer.analyze(progress_callback=scan_progress)
            analyzer.save_metadata(settings.rag_metadata_path)

            rows = analyzer.get_all() if include_normal else analyzer.get_anomalies()
            total_rows = len(rows)

            self._set_job(
                task_id,
                {
                    "phase": "generating_text",
                    "percent": 30,
                    "processed": 0,
                    "total": total_rows,
                    "message": "正在生成样本文本描述...",
                },
            )

            use_rule_only = total_rows > 500
            if use_rule_only:
                self._set_job(
                    task_id,
                    {
                        "phase": "generating_text",
                        "percent": 30,
                        "processed": 0,
                        "total": total_rows,
                        "message": "样本量较大，使用规则模板生成描述...",
                    },
                )

            payload: list[tuple[Any, str]] = []
            for idx, row in enumerate(rows, start=1):
                if use_rule_only:
                    text = self.text_generator.generate_rule_only(row)
                else:
                    text = self.text_generator.generate(row)
                payload.append((row, text))
                gen_percent = 30 + int((idx / max(total_rows, 1)) * 30)
                self._set_job(
                    task_id,
                    {
                        "phase": "generating_text",
                        "percent": min(gen_percent, 60),
                        "processed": idx,
                        "total": total_rows,
                        "message": f"正在生成样本文本描述: {idx}/{total_rows}",
                    },
                )

            def upsert_progress(done: int, total: int) -> None:
                percent = 60 + int((done / max(total, 1)) * 35)
                self._set_job(
                    task_id,
                    {
                        "phase": "embedding",
                        "percent": min(percent, 95),
                        "processed": done,
                        "total": total,
                        "message": f"向量化并写入样本: {done}/{total}",
                    },
                )

            self.vector_store.batch_upsert(payload, source="dataset", progress_callback=upsert_progress)

            result = {
                "dataset_root": root,
                "indexed_rows": len(payload),
                "vector_count": self.vector_store.count(),
                "stats": stats,
            }

            self._set_job(
                task_id,
                {
                    "status": "completed",
                    "phase": "done",
                    "percent": 100,
                    "message": "建库完成",
                    "result": result,
                },
            )
        except Exception as exc:
            self._set_job(
                task_id,
                {
                    "status": "failed",
                    "phase": "failed",
                    "percent": 100,
                    "message": "建库失败",
                    "error": str(exc),
                },
            )

    def get_build_job_status(self, task_id: str) -> Optional[dict[str, Any]]:
        with self._jobs_lock:
            job = self._build_jobs.get(task_id)
            return dict(job) if job else None

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

    def generate_anomaly_descriptions(
        self,
        dataset_root: Optional[str] = None,
        output_path: Optional[str] = None,
        incremental: bool = True,
    ) -> Dict[str, Any]:
        root = dataset_root or settings.rag_dataset_root
        analyzer = DatasetAnalyzer(root)
        analyzer.analyze()

        rows = analyzer.get_anomalies()
        use_rule_only = len(rows) > 500

        output = Path(output_path or settings.rag_descriptions_path)
        output.parent.mkdir(parents=True, exist_ok=True)

        existing_records: list[dict[str, Any]] = []
        existing_ids: set[str] = set()
        if incremental and output.exists():
            try:
                with output.open("r", encoding="utf-8") as f:
                    old_payload = json.load(f)
                existing_records = list(old_payload.get("records", []))
                existing_ids = {
                    str(item.get("image_id"))
                    for item in existing_records
                    if isinstance(item, dict) and item.get("image_id")
                }
            except Exception:
                existing_records = []
                existing_ids = set()

        new_records: list[dict[str, Any]] = []
        skipped = 0
        for row in rows:
            if incremental and row.image_id in existing_ids:
                skipped += 1
                continue

            description = self.text_generator.generate_rule_only(row) if use_rule_only else self.text_generator.generate(row)
            new_records.append(
                {
                    "image_id": row.image_id,
                    "image_path": row.image_path,
                    "category": row.category,
                    "split": row.split,
                    "is_anomaly": row.is_anomaly,
                    "anomaly_type": row.anomaly_type,
                    "severity": row.severity,
                    "description": description,
                }
            )

        records = existing_records + new_records if incremental else new_records

        payload = {
            "dataset_root": str(Path(root)),
            "total_anomaly_rows": len(rows),
            "generated": len(new_records),
            "skipped": skipped,
            "incremental": incremental,
            "records": records,
        }
        with output.open("w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

        return {
            "dataset_root": str(Path(root)),
            "output_path": str(output),
            "total_anomaly_rows": len(rows),
            "generated": len(new_records),
            "skipped": skipped,
            "incremental": incremental,
        }

    def query_rows(self, query_text: str, category: Optional[str], top_k: Optional[int]) -> list[dict[str, Any]]:
        k = top_k or settings.rag_top_k
        rows = self.retriever.retrieve_similar(
            query_description=query_text,
            top_k=k,
            category=category,
            only_anomaly=True,
        )
        if not rows and category:
            rows = self.retriever.retrieve_similar(
                query_description=query_text,
                top_k=k,
                category=None,
                only_anomaly=True,
            )
        return rows

    def query_rows_by_image(self, image_path: str, category: Optional[str], top_k: Optional[int]) -> list[dict[str, Any]]:
        k = top_k or settings.rag_top_k
        rows = self.retriever.retrieve_similar_by_image(
            image_path=image_path,
            top_k=k,
            category=category,
            only_anomaly=True,
        )
        if not rows and category:
            rows = self.retriever.retrieve_similar_by_image(
                image_path=image_path,
                top_k=k,
                category=None,
                only_anomaly=True,
            )
        return rows

    def query_similar(
        self,
        query_text: str,
        category: Optional[str],
        top_k: Optional[int],
        image_path: Optional[str] = None,
    ) -> str:
        rows = self.query_rows(query_text=query_text, category=category, top_k=top_k)
        if not rows and image_path:
            rows = self.query_rows_by_image(image_path=image_path, category=category, top_k=top_k)
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
