from __future__ import annotations

from typing import Any


OBJECT_KNOWLEDGE_BASE: dict[str, list[dict[str, Any]]] = {
    "bottle": [
        {
            "title": "封口区风险",
            "keywords": ["top", "upper", "封口", "瓶口", "裂纹", "缺口"],
            "note": "瓶口封口区异常通常优先影响密封可靠性与内容物保护能力。",
        },
        {
            "title": "瓶身结构风险",
            "keywords": ["middle", "center", "瓶身", "crack", "scratch", "surface_anomaly"],
            "note": "瓶身主体裂纹或冲击损伤更容易在运输、装配或受压场景下继续扩展。",
        },
        {
            "title": "瓶底支撑风险",
            "keywords": ["bottom", "lower", "瓶底", "dent"],
            "note": "瓶底过渡区异常应结合支撑稳定性和应力集中情况复核。",
        },
    ],
    "cable": [
        {
            "title": "连接端导通风险",
            "keywords": ["top", "upper", "连接端", "污染", "异常"],
            "note": "连接端区域异常常与接触不良、装配偏差或污染积累有关。",
        },
        {
            "title": "护套完整性",
            "keywords": ["middle", "护套", "scratch", "wear", "surface_anomaly"],
            "note": "外护套异常会直接影响绝缘保护与耐磨能力。",
        },
        {
            "title": "弯折疲劳",
            "keywords": ["bottom", "lower", "弯折", "crack", "裂纹"],
            "note": "弯折应力区异常需要关注反复受力后的疲劳扩展风险。",
        },
    ],
    "metal_nut": [
        {
            "title": "螺纹配合风险",
            "keywords": ["middle", "螺纹", "dent", "scratch", "surface_anomaly"],
            "note": "内孔螺纹区异常通常优先影响连接配合与扭矩传递稳定性。",
        },
        {
            "title": "外缘冲击风险",
            "keywords": ["top", "outer", "外缘", "缺口", "裂纹"],
            "note": "外缘缺口或裂纹需要关注装配冲击与局部应力集中。",
        },
        {
            "title": "受力面载荷风险",
            "keywords": ["bottom", "lower", "受力", "磨损"],
            "note": "受力接触面异常可能进一步影响载荷分布与紧固可靠性。",
        },
    ],
    "screw": [
        {
            "title": "头部受力槽风险",
            "keywords": ["top", "头部", "head", "damage", "surface_anomaly"],
            "note": "螺钉头部异常会影响工具啮合与拧紧过程稳定性。",
        },
        {
            "title": "螺纹连接风险",
            "keywords": ["middle", "thread", "螺纹", "scratch", "crack"],
            "note": "螺纹区异常通常直接影响紧固配合与重复装配可靠性。",
        },
        {
            "title": "连接端导入风险",
            "keywords": ["bottom", "end", "连接端", "bend", "弯曲"],
            "note": "连接端弯曲或毛刺需要关注装配导入与接触安全。",
        },
    ],
    "zipper": [
        {
            "title": "滑块接触风险",
            "keywords": ["top", "滑块", "污染", "磨损"],
            "note": "滑块接触区异常需要关注局部磨损和操作阻力变化。",
        },
        {
            "title": "齿列咬合风险",
            "keywords": ["middle", "齿列", "缺齿", "错位"],
            "note": "齿列区异常通常优先影响咬合连续性与开合顺畅性。",
        },
        {
            "title": "布带支撑风险",
            "keywords": ["bottom", "布带", "破损"],
            "note": "布带区异常会影响整体结构支撑与使用寿命。",
        },
    ],
}


def query_object_knowledge(
    *,
    category: str | None,
    anomalies: list[dict[str, Any]] | None = None,
    query_text: str = "",
    limit: int = 4,
) -> list[dict[str, Any]]:
    key = str(category or "").strip().lower()
    catalog = OBJECT_KNOWLEDGE_BASE.get(key, [])
    if not catalog:
        return []

    corpus = " ".join(
        [
            query_text,
            *(
                " ".join(
                    str(item.get(field, ""))
                    for field in ("type", "location", "description", "details")
                )
                for item in (anomalies or [])
                if isinstance(item, dict)
            ),
        ]
    ).lower()

    hits: list[dict[str, Any]] = []
    for entry in catalog:
        keywords = [str(item).lower() for item in entry.get("keywords", [])]
        score = sum(1 for token in keywords if token and token in corpus)
        if score <= 0:
            continue
        hits.append(
            {
                "title": entry.get("title", "对象知识"),
                "note": entry.get("note", ""),
                "score": score,
            }
        )

    hits.sort(key=lambda item: item.get("score", 0), reverse=True)
    if hits:
        return hits[:limit]

    fallback = []
    for entry in catalog[:limit]:
        fallback.append({"title": entry.get("title", "对象知识"), "note": entry.get("note", ""), "score": 0})
    return fallback
