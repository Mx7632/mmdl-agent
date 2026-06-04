from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw


IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp"}


def sanitize_name(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9_-]+", "_", value)
    value = re.sub(r"_+", "_", value).strip("_")
    return value or "defect"


def read_labelme_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def find_image_for_json(json_path: Path) -> Path | None:
    for suffix in IMAGE_EXTENSIONS:
        candidate = json_path.with_suffix(suffix)
        if candidate.exists():
            return candidate
    return None


def defect_type_from_json(json_path: Path) -> str:
    try:
        payload = read_labelme_json(json_path)
    except Exception:
        payload = {}
    shapes = payload.get("shapes") if isinstance(payload, dict) else []
    labels = [
        sanitize_name(str(shape.get("label", "")))
        for shape in shapes
        if isinstance(shape, dict) and str(shape.get("label", "")).strip()
    ]
    if labels:
        return labels[0]
    return sanitize_name(json_path.stem.split("-", 1)[0])


def make_mask(json_path: Path, output_path: Path, fallback_image: Path) -> None:
    payload = read_labelme_json(json_path)
    width = int(payload.get("imageWidth") or 0)
    height = int(payload.get("imageHeight") or 0)
    if width <= 0 or height <= 0:
        with Image.open(fallback_image) as image:
            width, height = image.size

    mask = Image.new("L", (width, height), 0)
    draw = ImageDraw.Draw(mask)
    for shape in payload.get("shapes") or []:
        if not isinstance(shape, dict):
            continue
        points = shape.get("points") or []
        polygon = [(float(x), float(y)) for x, y in points if isinstance(x, (int, float)) and isinstance(y, (int, float))]
        if len(polygon) >= 3:
            draw.polygon(polygon, fill=255)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    mask.save(output_path)


def copy_image(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def build_dataset(
    *,
    source_root: Path,
    output_root: Path,
    category: str,
    clsname: str,
    normal_train_ratio: float,
) -> dict[str, Any]:
    normal_dir = source_root / "正常样本"
    defect_dir = source_root / "缺陷样本"
    if not normal_dir.exists():
        raise FileNotFoundError(f"Missing normal sample directory: {normal_dir}")
    if not defect_dir.exists():
        raise FileNotFoundError(f"Missing defect sample directory: {defect_dir}")

    dataset_root = output_root / "mvtec_anomaly_detection"
    category_root = dataset_root / category
    train_good_dir = category_root / "train" / "good"
    test_good_dir = category_root / "test" / "good"

    normal_images = sorted(
        path for path in normal_dir.iterdir() if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    )
    split_index = max(1, int(len(normal_images) * normal_train_ratio))
    train_normals = normal_images[:split_index]
    test_normals = normal_images[split_index:]

    train_rows: list[dict[str, Any]] = []
    test_rows: list[dict[str, Any]] = []

    for index, image_path in enumerate(train_normals):
        name = f"{index:04d}{image_path.suffix.lower()}"
        target = train_good_dir / name
        copy_image(image_path, target)
        train_rows.append(
            {
                "filename": f"{category}/train/good/{name}",
                "label": 0,
                "label_name": "good",
                "clsname": clsname,
            }
        )

    for index, image_path in enumerate(test_normals):
        name = f"{index:04d}{image_path.suffix.lower()}"
        target = test_good_dir / name
        copy_image(image_path, target)
        test_rows.append(
            {
                "filename": f"{category}/test/good/{name}",
                "label": 0,
                "label_name": "good",
                "clsname": clsname,
            }
        )

    defect_jsons = sorted(defect_dir.rglob("*.json"))
    defect_counts: dict[str, int] = {}
    missing_images: list[str] = []
    for json_path in defect_jsons:
        image_path = find_image_for_json(json_path)
        if image_path is None:
            missing_images.append(str(json_path))
            continue

        defect_type = defect_type_from_json(json_path)
        defect_counts[defect_type] = defect_counts.get(defect_type, 0) + 1
        index = defect_counts[defect_type] - 1
        image_name = f"{index:04d}{image_path.suffix.lower()}"
        mask_name = f"{index:04d}_mask.png"

        target_image = category_root / "test" / defect_type / image_name
        target_mask = category_root / "ground_truth" / defect_type / mask_name
        copy_image(image_path, target_image)
        make_mask(json_path, target_mask, image_path)

        test_rows.append(
            {
                "filename": f"{category}/test/{defect_type}/{image_name}",
                "label": 1,
                "label_name": "defective",
                "clsname": clsname,
                "maskname": f"{category}/ground_truth/{defect_type}/{mask_name}",
            }
        )

    write_jsonl(output_root / "train.json", train_rows)
    write_jsonl(output_root / "test.json", test_rows)

    summary = {
        "source_root": str(source_root),
        "output_root": str(output_root),
        "dataset_root": str(dataset_root),
        "category": category,
        "clsname": clsname,
        "normal_images": len(normal_images),
        "train_good": len(train_normals),
        "test_good": len(test_normals),
        "defect_images": sum(defect_counts.values()),
        "defect_types": defect_counts,
        "missing_image_json_count": len(missing_images),
        "missing_image_jsons": missing_images[:20],
        "train_json": str(output_root / "train.json"),
        "test_json": str(output_root / "test.json"),
    }
    (output_root / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Convert lace textile samples into a GRAD/MVTec-style dataset.")
    parser.add_argument(
        "--source-root",
        default=r"D:\cloudpan\datasets\纺织样本\纺织样本\蕾丝样本数据",
        help="Original lace sample dataset root.",
    )
    parser.add_argument(
        "--output-root",
        default="data/grad_lace/MVTec-AD",
        help="Output root that will contain mvtec_anomaly_detection, train.json and test.json.",
    )
    parser.add_argument("--category", default="lace", help="Directory category name.")
    parser.add_argument(
        "--clsname",
        default="leather",
        help=(
            "GRAD clsname written to JSON. Default is leather because upstream GRAD custom_dataset.py "
            "does not include a lace class id."
        ),
    )
    parser.add_argument("--normal-train-ratio", type=float, default=0.8)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    summary = build_dataset(
        source_root=Path(args.source_root),
        output_root=Path(args.output_root),
        category=args.category,
        clsname=args.clsname,
        normal_train_ratio=args.normal_train_ratio,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
