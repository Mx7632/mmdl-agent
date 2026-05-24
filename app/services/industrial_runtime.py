from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from threading import RLock
from typing import Any
from uuid import uuid4

from app.config.settings import settings

REVIEW_PENDING = "pending_review"
REVIEW_APPROVED = "approved"
REVIEW_REJECTED = "rejected"


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def _anomaly_score(anomaly: dict[str, Any]) -> float:
    for key in ("score", "confidence", "anomaly_score"):
        if key in anomaly:
            return _safe_float(anomaly.get(key), 0.0)
    return 1.0


def normalize_industrial_result(
    result: dict[str, Any],
    *,
    model_version: str | None = None,
    sample_version: str | None = None,
) -> dict[str, Any]:
    """Add pilot-production fields without changing the existing response contract."""

    normalized = dict(result or {})
    anomalies = []
    raw_anomalies = normalized.get("anomalies") or []
    if isinstance(raw_anomalies, list):
        for index, item in enumerate(raw_anomalies, start=1):
            anomaly = dict(item) if isinstance(item, dict) else {"details": str(item)}
            score = _anomaly_score(anomaly)
            anomaly.setdefault("is_anomaly", True)
            anomaly.setdefault("score", score)
            anomaly.setdefault("defect_type", anomaly.get("type") or anomaly.get("anomaly_type") or "unknown")
            anomaly.setdefault("reason", anomaly.get("details") or anomaly.get("description") or "model_detected")
            anomaly.setdefault("rank", index)
            anomalies.append(anomaly)

    metadata = dict(normalized.get("metadata") or {})
    result_metadata = dict(metadata.get("result_metadata") or {})
    backend = (
        result_metadata.get("selected_backend")
        or result_metadata.get("detector_type")
        or result_metadata.get("tool")
        or metadata.get("selected_backend")
        or metadata.get("tool")
        or "unknown"
    )
    top_score = max([_anomaly_score(item) for item in anomalies], default=0.0)
    confidence = _safe_float(metadata.get("confidence"), top_score)
    if confidence <= 0:
        confidence = _safe_float(result_metadata.get("confidence"), top_score)
    if confidence <= 0:
        confidence = top_score

    is_anomaly = bool(anomalies)
    review_status = REVIEW_PENDING if is_anomaly and confidence < settings.low_confidence_review_threshold else "auto_pass"
    industrial = {
        "schema_version": "industrial-result/v1",
        "is_anomaly": is_anomaly,
        "score": confidence,
        "top_score": top_score,
        "defect_type": anomalies[0].get("defect_type") if anomalies else "good",
        "reason": anomalies[0].get("reason") if anomalies else "no_obvious_visual_anomaly",
        "model_backend": backend,
        "model_version": model_version or result_metadata.get("model_version") or str(backend),
        "sample_version": sample_version or result_metadata.get("sample_version") or "unversioned",
        "review_status": review_status,
        "requires_review": review_status == REVIEW_PENDING,
        "review_threshold": settings.low_confidence_review_threshold,
    }

    metadata["industrial"] = industrial
    normalized["anomalies"] = anomalies
    normalized["is_anomaly"] = is_anomaly
    normalized["score"] = confidence
    normalized["defect_type"] = industrial["defect_type"]
    normalized["review_status"] = industrial["review_status"]
    normalized["requires_review"] = industrial["requires_review"]
    normalized["metadata"] = metadata
    return normalized


class IndustrialRuntimeStore:
    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path or settings.runtime_store_path)
        self._lock = RLock()
        self._state: dict[str, Any] = {"tasks": {}, "batches": {}, "feedback": {}, "metrics": {}}
        self._loaded = False

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        with self._lock:
            if self._loaded:
                return
            if self.path.exists():
                try:
                    self._state = json.loads(self.path.read_text(encoding="utf-8"))
                except Exception:
                    self._state = {"tasks": {}, "batches": {}, "feedback": {}, "metrics": {}}
            self._state.setdefault("tasks", {})
            self._state.setdefault("batches", {})
            self._state.setdefault("feedback", {})
            self._state.setdefault("metrics", {})
            self._loaded = True

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self._state, ensure_ascii=False, indent=2), encoding="utf-8")

    def record_task(self, task: Any, result: dict[str, Any], *, batch_id: str | None = None) -> dict[str, Any]:
        self._ensure_loaded()
        normalized = normalize_industrial_result(result)
        industrial = normalized.get("metadata", {}).get("industrial", {})
        record = {
            "task_id": normalized.get("task_id") or getattr(task, "task_id", ""),
            "batch_id": batch_id,
            "asset_id": getattr(task, "asset_id", ""),
            "category": (getattr(task, "parameters", {}) or {}).get("patchcore_category")
            or ((getattr(task, "parameters", {}) or {}).get("detector_params") or {}).get("category")
            or "unknown",
            "status": normalized.get("status", "unknown"),
            "is_anomaly": industrial.get("is_anomaly", False),
            "score": industrial.get("score", 0.0),
            "defect_type": industrial.get("defect_type", "unknown"),
            "review_status": industrial.get("review_status", "auto_pass"),
            "requires_review": industrial.get("requires_review", False),
            "model_backend": industrial.get("model_backend", "unknown"),
            "model_version": industrial.get("model_version", "unknown"),
            "sample_version": industrial.get("sample_version", "unversioned"),
            "created_at": _now(),
            "updated_at": _now(),
            "result": normalized,
            "review": None,
        }
        with self._lock:
            # Merge with existing record to preserve report metadata etc.
            existing = self._state["tasks"].get(record["task_id"])
            if existing and isinstance(existing.get("result"), dict):
                for key in ("has_report", "summary"):
                    if key in existing["result"] and key not in normalized:
                        normalized[key] = existing["result"][key]
            self._state["tasks"][record["task_id"]] = record
            metrics = self._state.setdefault("metrics", {})
            metrics["task_count"] = len(self._state["tasks"])
            metrics["last_task_at"] = record["created_at"]
            self._save()
        return record

    def create_batch(self, *, asset_id: str, question: str | None, item_count: int) -> dict[str, Any]:
        self._ensure_loaded()
        batch_id = f"batch-{uuid4().hex[:12]}"
        batch = {
            "batch_id": batch_id,
            "asset_id": asset_id,
            "question": question,
            "item_count": item_count,
            "task_ids": [],
            "status": "running",
            "created_at": _now(),
            "updated_at": _now(),
        }
        with self._lock:
            self._state["batches"][batch_id] = batch
            self._save()
        return batch

    def finish_batch(self, batch_id: str, task_ids: list[str], *, status: str = "success") -> dict[str, Any]:
        self._ensure_loaded()
        with self._lock:
            batch = self._state["batches"].setdefault(batch_id, {"batch_id": batch_id})
            batch["task_ids"] = task_ids
            batch["status"] = status
            batch["updated_at"] = _now()
            self._save()
            return dict(batch)

    def list_tasks(
        self,
        *,
        asset_id: str | None = None,
        status: str | None = None,
        defect_type: str | None = None,
        review_status: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        self._ensure_loaded()
        rows = list(self._state["tasks"].values())
        if asset_id:
            rows = [row for row in rows if row.get("asset_id") == asset_id]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        if defect_type:
            rows = [row for row in rows if row.get("defect_type") == defect_type]
        if review_status:
            rows = [row for row in rows if row.get("review_status") == review_status]
        rows.sort(key=lambda row: row.get("created_at", ""), reverse=True)
        return [self._public_task(row) for row in rows[: max(1, min(limit, 200))]]

    def get_task(self, task_id: str) -> dict[str, Any] | None:
        self._ensure_loaded()
        row = self._state["tasks"].get(task_id)
        return self._public_task(row) if row else None

    def patch_task_result(self, task_id: str, updates: dict) -> bool:
        """Patch specific fields into an existing task's result dict. Returns True if task existed."""
        self._ensure_loaded()
        with self._lock:
            row = self._state["tasks"].get(task_id)
            if row is None:
                return False
            row["result"].update(updates)
            row["updated_at"] = _now()
            self._save()
            return True

    def delete_task(self, task_id: str) -> bool:
        """Delete a single task record. Returns True if it existed."""
        self._ensure_loaded()
        with self._lock:
            removed = self._state["tasks"].pop(task_id, None)
            if removed is not None:
                metrics = self._state.setdefault("metrics", {})
                metrics["task_count"] = len(self._state["tasks"])
                self._save()
                return True
            return False

    def delete_all_tasks(self) -> int:
        """Delete all task records. Returns count of removed tasks."""
        self._ensure_loaded()
        with self._lock:
            count = len(self._state["tasks"])
            self._state["tasks"] = {}
            metrics = self._state.setdefault("metrics", {})
            metrics["task_count"] = 0
            self._save()
            return count

    def review_task(
        self,
        task_id: str,
        *,
        decision: str,
        defect_type: str | None = None,
        notes: str | None = None,
        reviewer: str | None = None,
    ) -> dict[str, Any]:
        self._ensure_loaded()
        normalized = REVIEW_APPROVED if decision in {"approve", "approved", "confirm", "confirmed"} else REVIEW_REJECTED
        with self._lock:
            row = self._state["tasks"].get(task_id)
            if row is None:
                raise KeyError(task_id)
            if defect_type:
                row["defect_type"] = defect_type
                result = row.get("result") or {}
                result["defect_type"] = defect_type
                for anomaly in result.get("anomalies") or []:
                    anomaly["defect_type"] = defect_type
            row["review_status"] = normalized
            row["requires_review"] = False
            row["review"] = {
                "decision": normalized,
                "defect_type": defect_type or row.get("defect_type"),
                "notes": notes or "",
                "reviewer": reviewer or "operator",
                "reviewed_at": _now(),
            }
            row["updated_at"] = _now()
            self._save()
            return self._public_task(row)

    def pending_reviews(self, limit: int = 50) -> list[dict[str, Any]]:
        return self.list_tasks(review_status=REVIEW_PENDING, limit=limit)

    def create_feedback(self, payload: dict[str, Any]) -> dict[str, Any]:
        self._ensure_loaded()
        feedback_id = f"feedback-{uuid4().hex[:12]}"
        record = {
            "feedback_id": feedback_id,
            "review_status": REVIEW_PENDING,
            "created_at": _now(),
            "updated_at": _now(),
            **payload,
        }
        with self._lock:
            self._state["feedback"][feedback_id] = record
            self._save()
        return dict(record)

    def review_feedback(self, feedback_id: str, decision: str) -> dict[str, Any]:
        self._ensure_loaded()
        normalized = REVIEW_APPROVED if decision in {"approve", "approved"} else REVIEW_REJECTED
        with self._lock:
            row = self._state["feedback"].get(feedback_id)
            if row is None:
                raise KeyError(feedback_id)
            row["review_status"] = normalized
            row["updated_at"] = _now()
            self._save()
            return dict(row)

    def batch_report(self, batch_id: str) -> dict[str, Any]:
        self._ensure_loaded()
        batch = self._state["batches"].get(batch_id)
        if not batch:
            raise KeyError(batch_id)
        tasks = [self._state["tasks"][task_id] for task_id in batch.get("task_ids", []) if task_id in self._state["tasks"]]
        defect_counts = Counter(row.get("defect_type", "unknown") for row in tasks)
        review_counts = Counter(row.get("review_status", "unknown") for row in tasks)
        anomaly_count = sum(1 for row in tasks if row.get("is_anomaly"))
        return {
            "batch_id": batch_id,
            "status": batch.get("status"),
            "task_count": len(tasks),
            "anomaly_count": anomaly_count,
            "normal_count": len(tasks) - anomaly_count,
            "defect_distribution": dict(defect_counts),
            "review_distribution": dict(review_counts),
            "sample_tasks": [self._public_task(row) for row in tasks[:5]],
            "summary": (
                f"Batch {batch_id} processed {len(tasks)} image(s), "
                f"with {anomaly_count} anomaly candidate(s) and {review_counts.get(REVIEW_PENDING, 0)} pending review."
            ),
        }

    def metrics(self) -> dict[str, Any]:
        self._ensure_loaded()
        tasks = list(self._state["tasks"].values())
        statuses = Counter(row.get("status", "unknown") for row in tasks)
        reviews = Counter(row.get("review_status", "unknown") for row in tasks)
        backends = Counter(row.get("model_backend", "unknown") for row in tasks)
        return {
            "task_count": len(tasks),
            "batch_count": len(self._state["batches"]),
            "feedback_count": len(self._state["feedback"]),
            "status_counts": dict(statuses),
            "review_counts": dict(reviews),
            "backend_counts": dict(backends),
            **self._state.get("metrics", {}),
        }

    def reset_for_tests(self, path: str | Path | None = None) -> None:
        with self._lock:
            if path is not None:
                self.path = Path(path)
            self._state = {"tasks": {}, "batches": {}, "feedback": {}, "metrics": {}}
            self._loaded = True
            if self.path.exists():
                self.path.unlink()

    def _public_task(self, row: dict[str, Any]) -> dict[str, Any]:
        result = row.get("result") or {}
        return {
            key: row.get(key)
            for key in (
                "task_id",
                "batch_id",
                "asset_id",
                "category",
                "status",
                "is_anomaly",
                "score",
                "defect_type",
                "review_status",
                "requires_review",
                "model_backend",
                "model_version",
                "sample_version",
                "created_at",
                "updated_at",
                "review",
            )
        } | {"result": result}


industrial_store = IndustrialRuntimeStore()
