from __future__ import annotations

from typing import Any


def is_anomaly_case(row: dict[str, Any]) -> bool:
    metadata = row.get("metadata") or {}
    if metadata.get("is_anomaly") is not None:
        return bool(metadata.get("is_anomaly"))
    anomaly_type = str(metadata.get("anomaly_type") or "").strip().lower()
    return anomaly_type not in {"", "good", "normal", "none"}


def _dedupe_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    output: list[dict[str, Any]] = []
    for row in rows:
        row_id = str(row.get("id") or row.get("metadata", {}).get("image_path") or "")
        if row_id and row_id in seen:
            continue
        if row_id:
            seen.add(row_id)
        output.append(row)
    return output


class FewShotSelector:
    """Select balanced normal and abnormal examples for knowledge prompts."""

    def __init__(self, *, max_normal: int = 1, max_anomaly: int = 2) -> None:
        self.max_normal = max(0, max_normal)
        self.max_anomaly = max(0, max_anomaly)

    def select(self, rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
        normal: list[dict[str, Any]] = []
        anomaly: list[dict[str, Any]] = []
        for row in _dedupe_rows(rows):
            if is_anomaly_case(row):
                if len(anomaly) < self.max_anomaly:
                    anomaly.append(row)
            elif len(normal) < self.max_normal:
                normal.append(row)
        return {"normal": normal, "anomaly": anomaly}


class FewShotPromptBuilder:
    """Build a compact few-shot reference block from selected RAG rows."""

    def build(self, selected: dict[str, list[dict[str, Any]]]) -> str:
        sections: list[str] = []
        normal_rows = selected.get("normal") or []
        anomaly_rows = selected.get("anomaly") or []

        if normal_rows:
            sections.append("[Few-shot normal examples]\n" + "\n".join(self._format_row(row) for row in normal_rows))
        if anomaly_rows:
            sections.append("[Few-shot anomaly examples]\n" + "\n".join(self._format_row(row) for row in anomaly_rows))

        return "\n\n".join(sections)

    def _format_row(self, row: dict[str, Any]) -> str:
        metadata = row.get("metadata") or {}
        similarity = 1 - float(row.get("distance", 1.0) or 1.0)
        category = metadata.get("category") or "unknown"
        anomaly_type = metadata.get("anomaly_type") or ("anomaly" if is_anomaly_case(row) else "good")
        severity = metadata.get("severity") or "unknown"
        description = str(row.get("description") or "").strip()
        return (
            f"- category={category}; type={anomaly_type}; severity={severity}; "
            f"similarity={similarity:.2%}; description={description}"
        )


def build_fewshot_context(
    rows: list[dict[str, Any]],
    *,
    max_normal: int = 1,
    max_anomaly: int = 2,
) -> tuple[dict[str, list[dict[str, Any]]], str]:
    selected = FewShotSelector(max_normal=max_normal, max_anomaly=max_anomaly).select(rows)
    return selected, FewShotPromptBuilder().build(selected)
