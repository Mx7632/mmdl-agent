from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


TASK_TYPE_MAP = {
    "Anomaly Detection": "anomaly_discrimination",
    "Defect Classification": "defect_classification",
    "Defect Localization": "defect_localization",
    "Defect Description": "defect_description",
    "Defect Analysis": "defect_analysis",
    "Object Classification": "object_classification",
    "Object Structure": "object_analysis",
    "Object Details": "object_analysis",
    "Object Analysis": "object_analysis",
}


@dataclass(frozen=True)
class MMADImportPaths:
    source_root: Path
    metadata_path: Path
    domain_knowledge_path: Path | None = None


def resolve_mmad_paths(source_root: str | Path, metadata_file: str = "mmad.json") -> MMADImportPaths:
    root = Path(source_root)
    metadata_path = root / "dataset" / "MMAD" / metadata_file
    if not metadata_path.exists():
        metadata_path = root / metadata_file
    if not metadata_path.exists():
        raise FileNotFoundError(f"MMAD metadata file not found: {metadata_path}")

    domain_knowledge_path = metadata_path.parent / "domain_knowledge.json"
    return MMADImportPaths(
        source_root=metadata_path.parent,
        metadata_path=metadata_path,
        domain_knowledge_path=domain_knowledge_path if domain_knowledge_path.exists() else None,
    )


def load_mmad_metadata(metadata_path: str | Path) -> dict[str, Any]:
    return json.loads(Path(metadata_path).read_text(encoding="utf-8"))


def load_mmad_domain_knowledge(domain_knowledge_path: str | Path | None) -> dict[str, Any]:
    if not domain_knowledge_path:
        return {}
    path = Path(domain_knowledge_path)
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def split_mmad_image_key(image_key: str) -> dict[str, str | None]:
    parts = image_key.replace("\\", "/").split("/")
    dataset = parts[0] if len(parts) > 0 else None
    category = parts[1] if len(parts) > 1 else None
    split = None
    defect_type = None

    if "test" in parts:
        index = parts.index("test")
        split = "test"
        defect_type = parts[index + 1] if len(parts) > index + 1 else None
    elif "train" in parts:
        index = parts.index("train")
        split = "train"
        defect_type = parts[index + 1] if len(parts) > index + 1 else None
    elif "image" in parts:
        index = parts.index("image")
        split = "image"
        defect_type = parts[index + 1] if len(parts) > index + 1 else None

    return {
        "dataset": dataset,
        "category": category,
        "split": split,
        "defect_type": defect_type,
    }


def normalize_mmad_task_type(question_type: str) -> str:
    return TASK_TYPE_MAP.get(question_type, "unknown")


def _answer_text(conversation: dict[str, Any]) -> str | None:
    answer = conversation.get("Answer")
    options = conversation.get("Options") or {}
    if answer in options:
        return options[answer]
    return None


def _resolve_image_path(source_root: Path, image_key: str, image_path: str | None) -> str:
    candidates = [
        source_root / image_key,
    ]
    if image_path:
        candidates.append(source_root / image_path)

    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return str(candidates[0])


def _resolve_mask_path(source_root: Path, image_key: str, mask_path: str | None) -> str | None:
    if not mask_path:
        return None
    parts = image_key.replace("\\", "/").split("/")
    prefix = Path(*parts[:2]) if len(parts) >= 2 else Path()
    candidates = [
        source_root / prefix / mask_path,
        source_root / mask_path,
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return str(candidates[0])


def build_mmad_qa_items(image_key: str, item: dict[str, Any]) -> list[dict[str, Any]]:
    qa_items: list[dict[str, Any]] = []
    for index, conversation in enumerate(item.get("conversation") or [], start=1):
        question_type = str(conversation.get("type") or "unknown")
        qa_items.append(
            {
                "id": f"{image_key}#q{index}",
                "annotation_id": image_key,
                "task": normalize_mmad_task_type(question_type),
                "original_type": question_type,
                "question": conversation.get("Question"),
                "options": conversation.get("Options") or {},
                "answer": conversation.get("Answer"),
                "answer_text": _answer_text(conversation),
                "annotation_verified": bool(conversation.get("annotation", False)),
            }
        )
    return qa_items


def build_mmad_analysis_stub(qa_items: list[dict[str, Any]]) -> dict[str, Any]:
    analysis: dict[str, Any] = {
        "anomaly_discrimination": {},
        "defect_classification": {},
        "defect_localization": {},
        "defect_description": {},
        "defect_analysis": {},
        "object_classification": {},
        "object_analysis": {},
    }
    for qa in qa_items:
        task = qa["task"]
        target = analysis.get(task)
        if not isinstance(target, dict):
            continue
        target.setdefault("qa_items", []).append(
            {
                "question": qa["question"],
                "answer": qa["answer"],
                "answer_text": qa["answer_text"],
                "original_type": qa["original_type"],
            }
        )
    return analysis


def convert_mmad_item(
    image_key: str,
    item: dict[str, Any],
    *,
    source_root: str | Path,
    domain_knowledge: dict[str, Any] | None = None,
) -> dict[str, Any]:
    root = Path(source_root)
    parts = split_mmad_image_key(image_key)
    qa_items = build_mmad_qa_items(image_key, item)
    dataset = parts["dataset"]
    category = parts["category"]
    defect_type = parts["defect_type"]
    is_anomaly = defect_type not in (None, "good")
    domain_note = None
    if domain_knowledge and dataset and category and defect_type:
        dataset_key = "MVTec" if dataset in {"MVTec-AD", "DS-MVTec"} else dataset
        domain_note = (
            domain_knowledge.get(dataset_key, {})
            .get(category, {})
            .get(defect_type)
        )

    return {
        "id": image_key,
        "source": "mmad",
        "dataset": dataset,
        "category": category,
        "split": parts["split"],
        "defect_type": defect_type,
        "is_anomaly": is_anomaly,
        "image_path": _resolve_image_path(root, image_key, item.get("image_path")),
        "mask_path": _resolve_mask_path(root, image_key, item.get("mask_path")),
        "similar_templates": list(item.get("similar_templates") or []),
        "random_templates": list(item.get("random_templates") or []),
        "domain_knowledge": domain_note,
        "qa_items": qa_items,
        "mmad_analysis": build_mmad_analysis_stub(qa_items),
    }


def iter_mmad_annotations(
    *,
    source_root: str | Path,
    metadata_file: str = "mmad.json",
    dataset_filter: str | None = None,
    category_filter: str | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    paths = resolve_mmad_paths(source_root, metadata_file=metadata_file)
    metadata = load_mmad_metadata(paths.metadata_path)
    domain_knowledge = load_mmad_domain_knowledge(paths.domain_knowledge_path)
    annotations: list[dict[str, Any]] = []

    for image_key, item in metadata.items():
        parts = split_mmad_image_key(image_key)
        if dataset_filter and parts["dataset"] != dataset_filter:
            continue
        if category_filter and parts["category"] != category_filter:
            continue
        annotations.append(
            convert_mmad_item(
                image_key,
                item,
                source_root=paths.source_root,
                domain_knowledge=domain_knowledge,
            )
        )
        if limit is not None and len(annotations) >= limit:
            break

    return annotations


def write_jsonl(path: str | Path, rows: list[dict[str, Any]]) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def flatten_qa_items(annotations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for annotation in annotations:
        for qa in annotation.get("qa_items") or []:
            rows.append(
                {
                    **qa,
                    "image_path": annotation.get("image_path"),
                    "mask_path": annotation.get("mask_path"),
                    "dataset": annotation.get("dataset"),
                    "category": annotation.get("category"),
                    "defect_type": annotation.get("defect_type"),
                    "is_anomaly": annotation.get("is_anomaly"),
                }
            )
    return rows
