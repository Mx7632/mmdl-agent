from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.analysis.mmad_importer import flatten_qa_items, iter_mmad_annotations, write_jsonl


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import official MMAD metadata into project JSONL files.")
    parser.add_argument("--source-root", required=True, help="Path to the local MMAD repository or dataset/MMAD directory.")
    parser.add_argument("--metadata-file", default="mmad.json", help="MMAD metadata file name, e.g. mmad.json.")
    parser.add_argument("--output-root", default="data/mmad", help="Output directory for converted JSONL files.")
    parser.add_argument("--dataset", default=None, help="Optional dataset filter, e.g. MVTec-AD or DS-MVTec.")
    parser.add_argument("--category", default=None, help="Optional category filter, e.g. bottle.")
    parser.add_argument("--limit", type=int, default=None, help="Optional max number of images to import.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    annotations = iter_mmad_annotations(
        source_root=args.source_root,
        metadata_file=args.metadata_file,
        dataset_filter=args.dataset,
        category_filter=args.category,
        limit=args.limit,
    )
    qa_items = flatten_qa_items(annotations)
    output_root = Path(args.output_root)
    annotation_path = output_root / "annotations.jsonl"
    qa_path = output_root / "qa.jsonl"
    write_jsonl(annotation_path, annotations)
    write_jsonl(qa_path, qa_items)
    print(f"Imported {len(annotations)} MMAD annotation(s).")
    print(f"Imported {len(qa_items)} MMAD QA item(s).")
    print(f"Annotations: {annotation_path}")
    print(f"QA: {qa_path}")


if __name__ == "__main__":
    main()
