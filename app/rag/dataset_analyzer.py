"""Analyze MVTec dataset and classify normal vs anomalous images."""
from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import cv2
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class ImageMetadata:
    """Metadata for a single image."""

    image_path: str
    category: str
    is_anomaly: bool
    split: str
    image_id: str
    anomaly_type: Optional[str] = None
    mask_path: Optional[str] = None
    severity: Optional[str] = None  # low | medium | high | unknown


class DatasetAnalyzer:
    """Analyze MVTec anomaly detection dataset."""

    def __init__(self, dataset_root: str | Path):
        self.dataset_root = Path(dataset_root)
        self.metadata_list: List[ImageMetadata] = []
        self.categories: List[str] = []

    def analyze(self) -> Dict[str, Any]:
        """Scan dataset and classify images."""
        logger.info("Analyzing dataset at %s", self.dataset_root)

        self.categories = sorted(
            [d.name for d in self.dataset_root.iterdir() if d.is_dir() and not d.name.startswith(".")]
        )

        self.metadata_list = []
        for category in self.categories:
            self._process_category(category)

        stats = self._compute_stats()
        logger.info("Analysis complete: total=%s anomalies=%s normal=%s", stats["total_images"], stats["anomalies"], stats["normal"])
        return stats

    def _process_category(self, category: str) -> None:
        category_path = self.dataset_root / category
        train_path = category_path / "train"
        test_path = category_path / "test"
        ground_truth_path = category_path / "ground_truth"

        # train/good 全部是正常样本
        good_train_path = train_path / "good"
        if good_train_path.exists():
            for img_file in sorted(good_train_path.glob("*.png")):
                self.metadata_list.append(
                    ImageMetadata(
                        image_path=str(img_file),
                        category=category,
                        is_anomaly=False,
                        split="train",
                        image_id=self._build_image_id(img_file, category, "train", "good"),
                        anomaly_type=None,
                    )
                )

        # test/good 是正常，test/<defect_type> 是异常
        if test_path.exists():
            for sub_dir in sorted(test_path.iterdir()):
                if not sub_dir.is_dir():
                    continue

                anomaly_type = sub_dir.name
                is_anomaly = anomaly_type != "good"

                for img_file in sorted(sub_dir.glob("*.png")):
                    mask_path = None
                    severity = None

                    if is_anomaly and ground_truth_path.exists():
                        candidate = ground_truth_path / anomaly_type / f"{img_file.stem}_mask.png"
                        if candidate.exists():
                            mask_path = str(candidate)
                            severity = self._estimate_severity(candidate)
                        else:
                            severity = "unknown"

                    self.metadata_list.append(
                        ImageMetadata(
                            image_path=str(img_file),
                            category=category,
                            is_anomaly=is_anomaly,
                            split="test",
                            image_id=self._build_image_id(img_file, category, "test", anomaly_type),
                            anomaly_type=anomaly_type if is_anomaly else None,
                            mask_path=mask_path,
                            severity=severity,
                        )
                    )

    def _build_image_id(self, image_path: Path, category: str, split: str, anomaly_type: str) -> str:
        raw = f"{category}:{split}:{anomaly_type}:{image_path.name}"
        digest = hashlib.md5(raw.encode("utf-8")).hexdigest()[:12]
        return f"{category}_{split}_{anomaly_type}_{image_path.stem}_{digest}"

    def _estimate_severity(self, mask_path: Path) -> str:
        try:
            mask = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
            if mask is None:
                return "unknown"

            total_pixels = int(mask.size)
            anomaly_pixels = int(np.count_nonzero(mask))
            ratio = anomaly_pixels / total_pixels if total_pixels > 0 else 0.0

            if ratio < 0.01:
                return "low"
            if ratio < 0.05:
                return "medium"
            return "high"
        except Exception as exc:  # pragma: no cover
            logger.warning("Failed to estimate severity for %s: %s", mask_path, exc)
            return "unknown"

    def _compute_stats(self) -> Dict[str, Any]:
        total = len(self.metadata_list)
        anomalies = sum(1 for m in self.metadata_list if m.is_anomaly)
        normal = total - anomalies

        by_category: Dict[str, Dict[str, int]] = {}
        for category in self.categories:
            cat_items = [m for m in self.metadata_list if m.category == category]
            by_category[category] = {
                "total": len(cat_items),
                "anomalies": sum(1 for m in cat_items if m.is_anomaly),
                "normal": sum(1 for m in cat_items if not m.is_anomaly),
            }

        return {
            "total_images": total,
            "anomalies": anomalies,
            "normal": normal,
            "categories": len(self.categories),
            "stats_by_category": by_category,
        }

    def get_all(self) -> List[ImageMetadata]:
        return self.metadata_list

    def get_anomalies(self) -> List[ImageMetadata]:
        return [m for m in self.metadata_list if m.is_anomaly]

    def get_normal(self) -> List[ImageMetadata]:
        return [m for m in self.metadata_list if not m.is_anomaly]

    def save_metadata(self, output_path: str | Path) -> None:
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)

        payload = {
            "dataset_root": str(self.dataset_root),
            "metadata": [asdict(m) for m in self.metadata_list],
            "stats": self._compute_stats(),
        }

        with output.open("w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)

    def load_metadata(self, input_path: str | Path) -> None:
        with Path(input_path).open("r", encoding="utf-8") as f:
            payload = json.load(f)

        self.metadata_list = [ImageMetadata(**m) for m in payload.get("metadata", [])]
        self.categories = sorted(list({m.category for m in self.metadata_list}))
