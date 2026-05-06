from __future__ import annotations

from typing import Any


def build_anomaly_query_text(anomalies: list[dict[str, Any]]) -> str:
    if not anomalies:
        return ""

    parts: list[str] = []
    for item in anomalies:
        anomaly_type = item.get("type", "unknown")
        details = item.get("details", "")
        score = item.get("score", 0)
        parts.append(f"异常类型:{anomaly_type}; 置信度:{score}; 细节:{details}")
    return " | ".join(parts)


def _normalize_text(value: Any, *, limit: int = 140) -> str:
    text = str(value or "").strip()
    return text if len(text) <= limit else f"{text[:limit].rstrip()}..."


def _derive_analysis_severity(anomalies: list[dict[str, Any]]) -> str:
    if not anomalies:
        return "low"
    score = max(float(item.get("score", 0.0) or 0.0) for item in anomalies if isinstance(item, dict))
    if score >= 0.75:
        return "high"
    if score >= 0.45:
        return "medium"
    return "low"


def build_structured_analysis(
    *,
    rows: list[dict[str, Any]],
    anomalies: list[dict[str, Any]] | None = None,
    query_text: str = "",
) -> dict[str, Any]:
    anomalies = [item for item in (anomalies or []) if isinstance(item, dict)]
    severity = _derive_analysis_severity(anomalies)
    anomaly_types = [str(item.get("type", "unknown")) for item in anomalies]
    locations = [str(item.get("location")) for item in anomalies if item.get("location")]

    similar_cases: list[dict[str, Any]] = []
    for row in rows[:3]:
        metadata = row.get("metadata", {}) if isinstance(row, dict) else {}
        similar_cases.append(
            {
                "id": row.get("id"),
                "category": metadata.get("category"),
                "anomaly_type": metadata.get("anomaly_type") or metadata.get("severity") or "unknown",
                "distance": row.get("distance"),
                "summary": _normalize_text(row.get("description")),
            }
        )

    type_label = "、".join(dict.fromkeys(anomaly_types)) if anomaly_types else (query_text or "当前异常")
    location_label = "、".join(dict.fromkeys(locations)) if locations else "当前热区"
    possible_causes = [
        f"{location_label} 出现的 {type_label} 可能与局部表面损伤、污染残留或工艺波动有关。"
    ]
    if rows:
        first_meta = rows[0].get("metadata", {}) if isinstance(rows[0], dict) else {}
        similar_type = first_meta.get("anomaly_type")
        if similar_type:
            possible_causes.append(f"检索到的相似案例多与“{similar_type}”相关，可优先复核同类缺陷机理。")

    risk_notes = [
        (
            "当前异常响应较强，若对应关键受力或密封区域，建议按较高风险处理。"
            if severity == "high"
            else "当前异常响应中等，建议结合工艺标准复核其是否会扩大或影响装配质量。"
            if severity == "medium"
            else "当前异常响应较弱，建议结合历史记录判断是否为早期缺陷或允许纹理。"
        )
    ]
    if rows:
        risk_notes.append("已检索到相似案例，可结合历史样本判断该异常是否具有重复发生趋势。")

    repair_actions = [
        "优先复核异常区域原图、热力图和边界框，确认异常是否稳定存在。",
        "如异常位于关键功能区域，建议补拍更多角度并安排人工复检。",
    ]
    if rows:
        repair_actions.append("参考相似案例的处理经验，优先检查同类缺陷常见成因与工艺环节。")

    analysis_summary = (
        f"针对 {type_label}，系统检索到 {len(rows)} 条相似案例。"
        f"结合当前 {severity} 级异常响应，建议从成因复核、风险评估和复检动作三个方面继续确认。"
    )

    sections = [
        "[相似案例]",
        *(f"- {item['summary']}" for item in similar_cases),
        "",
        "[可能成因]",
        *(f"- {item}" for item in possible_causes),
        "",
        "[风险提示]",
        *(f"- {item}" for item in risk_notes),
        "",
        "[建议动作]",
        *(f"- {item}" for item in repair_actions),
    ]
    prompt_context = "\n".join(sections).strip()

    return {
        "similar_cases": similar_cases,
        "possible_causes": possible_causes,
        "risk_notes": risk_notes,
        "repair_actions": repair_actions,
        "analysis_summary": analysis_summary,
        "prompt_context": prompt_context,
    }
