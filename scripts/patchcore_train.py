from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config.settings import settings
from app.tools.patchcore_detection import available_mvtec_categories, train_patchcore_category


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Train a lightweight PatchCore backend on one MVTec category.")
    parser.add_argument("--category", required=True, help="MVTec category, for example bottle or capsule")
    parser.add_argument("--dataset-root", default=settings.rag_dataset_root, help="Path to MVTec root")
    parser.add_argument("--model-root", default=settings.patchcore_model_root, help="Output model root")
    parser.add_argument("--image-size", type=int, default=settings.patchcore_image_size, help="Training image size")
    parser.add_argument("--device", default=settings.patchcore_device, help="cpu or cuda")
    parser.add_argument("--backbone", default=settings.patchcore_backbone, help="Feature backbone name")
    parser.add_argument(
        "--pretrained-backbone",
        action="store_true",
        default=settings.patchcore_pretrained_backbone,
        help="Try to use torchvision pretrained weights if available locally",
    )
    parser.add_argument(
        "--max-memory-bank",
        type=int,
        default=settings.patchcore_max_memory_bank,
        help="Maximum number of patch embeddings to keep",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    category = args.category.strip().lower()

    categories = available_mvtec_categories(args.dataset_root)
    if category not in categories:
        parser.error(f"Unknown category '{category}'. Available categories: {', '.join(categories)}")

    metadata = train_patchcore_category(
        category=category,
        dataset_root=args.dataset_root,
        model_root=args.model_root,
        image_size=args.image_size,
        backbone_name=args.backbone,
        pretrained_backbone=args.pretrained_backbone,
        device=args.device,
        max_memory_bank=args.max_memory_bank,
    )
    print(json.dumps(metadata, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
