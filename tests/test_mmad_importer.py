from __future__ import annotations

import json
import shutil
from pathlib import Path

from app.analysis.mmad_importer import (
    flatten_qa_items,
    iter_mmad_annotations,
    normalize_mmad_task_type,
    split_mmad_image_key,
)


def test_split_mmad_image_key_supports_ds_mvtec_layout():
    parts = split_mmad_image_key("DS-MVTec/bottle/image/broken_large/000.png")

    assert parts["dataset"] == "DS-MVTec"
    assert parts["category"] == "bottle"
    assert parts["split"] == "image"
    assert parts["defect_type"] == "broken_large"


def test_normalize_mmad_task_type_maps_to_project_seven_tasks():
    assert normalize_mmad_task_type("Anomaly Detection") == "anomaly_discrimination"
    assert normalize_mmad_task_type("Defect Localization") == "defect_localization"
    assert normalize_mmad_task_type("Object Details") == "object_analysis"


def test_iter_mmad_annotations_converts_official_qa():
    source_root = Path(".tmp_mmad_importer_test")
    if source_root.exists():
        shutil.rmtree(source_root)
    dataset_root = source_root / "dataset" / "MMAD"
    try:
        image_path = dataset_root / "DS-MVTec" / "bottle" / "image" / "broken_large" / "000.png"
        mask_path = dataset_root / "DS-MVTec" / "bottle" / "rbg_mask" / "broken_large" / "000_rbg_mask.png"
        image_path.parent.mkdir(parents=True)
        mask_path.parent.mkdir(parents=True)
        image_path.write_bytes(b"image")
        mask_path.write_bytes(b"mask")
        metadata = {
            "DS-MVTec/bottle/image/broken_large/000.png": {
                "image_path": "image/broken_large/000.png",
                "mask_path": "rbg_mask/broken_large/000_rbg_mask.png",
                "conversation": [
                    {
                        "Question": "Is there any defect in the object?",
                        "Answer": "A",
                        "Options": {"A": "Yes.", "B": "No."},
                        "type": "Anomaly Detection",
                        "annotation": True,
                    },
                    {
                        "Question": "There is a defect in the object. What is the type of the defect?",
                        "Answer": "C",
                        "Options": {"A": "Scratch.", "C": "Broken large."},
                        "type": "Defect Classification",
                        "annotation": True,
                    },
                ],
                "similar_templates": ["MVTec-AD/bottle/train/good/001.png"],
                "random_templates": [],
            }
        }
        domain_knowledge = {
            "MVTec": {
                "bottle": {
                    "broken_large": "<Large Breakage>\nDescription: Presents a safety hazard."
                }
            }
        }
        (dataset_root / "mmad.json").write_text(json.dumps(metadata), encoding="utf-8")
        (dataset_root / "domain_knowledge.json").write_text(json.dumps(domain_knowledge), encoding="utf-8")

        annotations = iter_mmad_annotations(source_root=source_root)
        qa_items = flatten_qa_items(annotations)

        assert len(annotations) == 1
        annotation = annotations[0]
        assert annotation["dataset"] == "DS-MVTec"
        assert annotation["category"] == "bottle"
        assert annotation["defect_type"] == "broken_large"
        assert annotation["is_anomaly"] is True
        assert annotation["image_path"].endswith("DS-MVTec\\bottle\\image\\broken_large\\000.png") or annotation[
            "image_path"
        ].endswith("DS-MVTec/bottle/image/broken_large/000.png")
        assert annotation["mask_path"] is not None
        assert "Large Breakage" in annotation["domain_knowledge"]
        assert annotation["mmad_analysis"]["anomaly_discrimination"]["qa_items"][0]["answer_text"] == "Yes."
        assert annotation["mmad_analysis"]["defect_classification"]["qa_items"][0]["answer_text"] == "Broken large."
        assert len(qa_items) == 2
        assert qa_items[0]["task"] == "anomaly_discrimination"
    finally:
        if source_root.exists():
            shutil.rmtree(source_root)
