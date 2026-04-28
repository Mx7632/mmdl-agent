from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config.settings import settings
from app.tools.patchcore_detection import available_mvtec_categories, predict_patchcore_image


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run lightweight PatchCore inference on a single image.")
    parser.add_argument("--image", required=True, help="Image path")
    parser.add_argument("--category", required=True, help="MVTec category")
    parser.add_argument("--task-id", default="patchcore-cli", help="Task identifier for output artifact names")
    parser.add_argument("--threshold", type=float, default=settings.patchcore_threshold, help="Heatmap threshold")
    parser.add_argument("--dataset-root", default=settings.rag_dataset_root, help="Path to MVTec root")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    category = args.category.strip().lower()

    categories = available_mvtec_categories(args.dataset_root)
    if category not in categories:
        parser.error(f"Unknown category '{category}'. Available categories: {', '.join(categories)}")

    result = predict_patchcore_image(
        image_path=args.image,
        category=category,
        threshold=args.threshold,
        task_id=args.task_id,
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
