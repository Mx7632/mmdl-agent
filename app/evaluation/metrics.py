from __future__ import annotations

from typing import Any


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value > 0
    return str(value).strip().lower() in {"1", "true", "yes", "anomaly", "abnormal"}


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def bbox_iou(pred: list[float] | None, truth: list[float] | None) -> float:
    if not pred or not truth or len(pred) != 4 or len(truth) != 4:
        return 0.0
    px1, py1, px2, py2 = [float(v) for v in pred]
    tx1, ty1, tx2, ty2 = [float(v) for v in truth]
    ix1, iy1 = max(px1, tx1), max(py1, ty1)
    ix2, iy2 = min(px2, tx2), min(py2, ty2)
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    intersection = iw * ih
    pred_area = max(0.0, px2 - px1) * max(0.0, py2 - py1)
    truth_area = max(0.0, tx2 - tx1) * max(0.0, ty2 - ty1)
    union = pred_area + truth_area - intersection
    return intersection / union if union > 0 else 0.0


def _roc_auc(labels: list[bool], scores: list[float]) -> float | None:
    positives = [(score, index) for index, (label, score) in enumerate(zip(labels, scores)) if label]
    negatives = [(score, index) for index, (label, score) in enumerate(zip(labels, scores)) if not label]
    if not positives or not negatives:
        return None

    wins = 0.0
    total = len(positives) * len(negatives)
    for pos_score, _ in positives:
        for neg_score, _ in negatives:
            if pos_score > neg_score:
                wins += 1.0
            elif pos_score == neg_score:
                wins += 0.5
    return wins / total


def evaluate_predictions(rows: list[dict[str, Any]], *, threshold: float = 0.5) -> dict[str, Any]:
    labels: list[bool] = []
    scores: list[float] = []
    ious: list[float] = []
    tp = fp = tn = fn = 0

    for row in rows:
        truth = row.get("ground_truth") or row.get("label") or {}
        prediction = row.get("prediction") or row
        actual = _as_bool(truth.get("is_anomaly") if isinstance(truth, dict) else truth)
        score = _as_float(prediction.get("score") or prediction.get("confidence") or prediction.get("anomaly_score"), 0.0)
        predicted = _as_bool(prediction.get("is_anomaly")) or score >= threshold

        labels.append(actual)
        scores.append(score)
        if actual and predicted:
            tp += 1
        elif not actual and predicted:
            fp += 1
        elif not actual and not predicted:
            tn += 1
        else:
            fn += 1

        pred_bbox = prediction.get("bbox")
        if not pred_bbox and prediction.get("anomalies"):
            pred_bbox = (prediction.get("anomalies") or [{}])[0].get("bbox")
        truth_bbox = truth.get("bbox") if isinstance(truth, dict) else None
        if actual and truth_bbox:
            ious.append(bbox_iou(pred_bbox, truth_bbox))

    total = max(1, len(rows))
    precision = tp / max(1, tp + fp)
    recall = tp / max(1, tp + fn)
    f1 = 2 * precision * recall / max(1e-12, precision + recall)
    return {
        "count": len(rows),
        "threshold": threshold,
        "accuracy": (tp + tn) / total,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "false_positive_rate": fp / max(1, fp + tn),
        "false_negative_rate": fn / max(1, fn + tp),
        "tp": tp,
        "fp": fp,
        "tn": tn,
        "fn": fn,
        "auroc": _roc_auc(labels, scores),
        "mean_iou": sum(ious) / len(ious) if ious else None,
        "pro_proxy": sum(1 for value in ious if value >= 0.3) / len(ious) if ious else None,
    }
