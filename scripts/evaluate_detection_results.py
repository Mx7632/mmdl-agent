from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from app.evaluation.metrics import evaluate_predictions


def _load_rows(path: Path) -> list[dict]:
    if path.suffix.lower() == ".jsonl":
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        return data.get("rows") or data.get("samples") or []
    return data


def _write_csv(path: Path, metrics: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["metric", "value"])
        for key, value in metrics.items():
            writer.writerow([key, value])


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate industrial anomaly detection predictions.")
    parser.add_argument("--input", required=True, help="JSON/JSONL rows with ground_truth and prediction fields.")
    parser.add_argument("--output-json", default="output/evaluation/metrics.json")
    parser.add_argument("--output-csv", default="output/evaluation/metrics.csv")
    parser.add_argument("--threshold", type=float, default=0.5)
    args = parser.parse_args()

    rows = _load_rows(Path(args.input))
    metrics = evaluate_predictions(rows, threshold=args.threshold)

    output_json = Path(args.output_json)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_csv(Path(args.output_csv), metrics)
    print(json.dumps(metrics, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
