"""Command-line entry for building dataset RAG index."""
from __future__ import annotations

import argparse
import json

from app.rag.service import get_rag_service


def main() -> None:
    parser = argparse.ArgumentParser(description="Build anomaly RAG index from dataset")
    parser.add_argument("--dataset-root", default=None, help="dataset root path")
    parser.add_argument("--only-anomaly", action="store_true", help="index only anomaly images")
    args = parser.parse_args()

    service = get_rag_service()
    result = service.build_from_dataset(
        dataset_root=args.dataset_root,
        include_normal=not args.only_anomaly,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
