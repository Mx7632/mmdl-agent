from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.rag.object_knowledge import query_object_knowledge


ObjectProfile = dict[str, Any]


DEFAULT_REGION_COMPONENT_MAP = {
    "top": 0,
    "upper": 0,
    "bottom": -1,
    "lower": -1,
    "left": 1,
    "right": 1,
    "middle": 1,
    "center": 1,
}


MVTEC_OBJECT_PROFILES: dict[str, ObjectProfile] = {
    "bottle": {
        "display_name": "玻璃瓶",
        "function_summary": "用于承载与密封内容物，重点关注瓶口封口区、瓶身主体和瓶底过渡区的完整性。",
        "components": ["瓶口封口区", "瓶身主体", "瓶底过渡区"],
        "focus": ["裂纹", "边缘缺口", "污染残留", "封口区异常"],
        "region_component_map": {"top": "瓶口封口区", "middle": "瓶身主体", "bottom": "瓶底过渡区"},
        "knowledge_notes": [
            "瓶口封口区异常通常优先影响密封可靠性与内容物保护能力。",
            "瓶身主体裂纹或冲击损伤更容易在运输、装配或受压场景下继续扩展。",
            "瓶底过渡区异常应结合支撑稳定性和应力集中情况复核。",
        ],
    },
    "cable": {
        "display_name": "工业线缆",
        "function_summary": "承担导电与绝缘功能，重点关注连接端区域、外护套和弯折应力区。",
        "components": ["连接端区域", "外护套", "弯折应力区"],
        "focus": ["护套破损", "磨损", "污染", "连接端异常"],
        "region_component_map": {"top": "连接端区域", "middle": "外护套", "bottom": "弯折应力区"},
        "knowledge_notes": [
            "连接端区域异常常与接触不良、装配偏差或污染积累有关。",
            "外护套异常会直接影响绝缘保护与耐磨能力。",
            "弯折应力区异常需要关注反复受力后的疲劳扩展风险。",
        ],
    },
    "capsule": {
        "display_name": "胶囊制品",
        "function_summary": "用于药品或颗粒封装，重点关注拼接边、壳体表面和端部圆角区。",
        "components": ["拼接边", "胶囊壳体", "端部圆角区"],
        "focus": ["裂纹", "凹陷", "污染", "边缘异常"],
        "region_component_map": {"top": "拼接边", "middle": "胶囊壳体", "bottom": "端部圆角区"},
        "knowledge_notes": [
            "拼接边异常通常需要优先复核封装完整性与药品保护能力。",
            "壳体表面污染或裂纹会同时影响外观一致性与使用安全判断。",
            "端部圆角区异常容易被忽略，建议结合多角度图像确认边缘连续性。",
        ],
    },
    "carpet": {
        "display_name": "工业地毯面材",
        "function_summary": "承担表面覆盖和纹理一致性要求，重点关注边缘区域、表层织物和纹理过渡区。",
        "components": ["边缘区域", "表层织物", "纹理过渡区"],
        "focus": ["污染", "纤维断裂", "纹理错位", "磨损"],
        "region_component_map": {"top": "边缘区域", "middle": "表层织物", "bottom": "纹理过渡区"},
        "knowledge_notes": [
            "边缘区域异常常与裁切、运输摩擦或装夹过程有关。",
            "表层织物异常更容易直接影响表观一致性。",
            "纹理过渡区的错位或磨损通常需要结合工艺标准复核是否可接受。",
        ],
    },
    "grid": {
        "display_name": "网格面板",
        "function_summary": "强调网格排列一致性与结构完整性，重点关注交叉节点、网格主体和边框区域。",
        "components": ["交叉节点", "网格主体", "边框区域"],
        "focus": ["变形", "断裂", "错位", "污染"],
        "region_component_map": {"top": "交叉节点", "middle": "网格主体", "bottom": "边框区域"},
        "knowledge_notes": [
            "交叉节点异常通常更容易带来局部结构强度下降。",
            "网格主体错位需要关注装配配合与整体排列精度。",
            "边框区域异常可能进一步影响固定与支撑稳定性。",
        ],
    },
    "hazelnut": {
        "display_name": "榛果表面样本",
        "function_summary": "关注顶部区域、外壳表面和底部接触面的完整性与色泽均匀性。",
        "components": ["顶部区域", "外壳表面", "底部接触面"],
        "focus": ["裂纹", "凹陷", "污染", "色差"],
        "region_component_map": {"top": "顶部区域", "middle": "外壳表面", "bottom": "底部接触面"},
        "knowledge_notes": [
            "外壳表面异常通常影响质量分级与外观一致性判断。",
            "顶部和底部接触面异常需要结合采集姿态确认是否为真实缺陷。",
        ],
    },
    "leather": {
        "display_name": "皮革面材",
        "function_summary": "强调裁切边、皮面主体和纹理集中区域的表观与完整性。",
        "components": ["裁切边", "皮面主体", "纹理集中区域"],
        "focus": ["划伤", "破洞", "起皱", "污染"],
        "region_component_map": {"top": "裁切边", "middle": "皮面主体", "bottom": "纹理集中区域"},
        "knowledge_notes": [
            "皮面主体异常更容易影响最终外观等级。",
            "裁切边异常通常需要结合加工环节复核。",
            "纹理集中区域起皱或破洞可能影响材料连续性与使用寿命。",
        ],
    },
    "metal_nut": {
        "display_name": "金属螺母",
        "function_summary": "承担连接与紧固功能，重点关注外缘、内孔螺纹区和受力接触面。",
        "components": ["外缘", "内孔螺纹区", "受力接触面"],
        "focus": ["缺口", "裂纹", "磨损", "污染"],
        "region_component_map": {"top": "外缘", "middle": "内孔螺纹区", "bottom": "受力接触面"},
        "knowledge_notes": [
            "内孔螺纹区异常通常优先影响连接配合与扭矩传递稳定性。",
            "外缘缺口或裂纹需要关注装配冲击与局部应力集中。",
            "受力接触面异常可能进一步影响载荷分布与紧固可靠性。",
        ],
    },
    "pill": {
        "display_name": "药片制品",
        "function_summary": "关注边缘、药片表面和压制标记区，避免影响识别与使用安全。",
        "components": ["边缘", "药片表面", "压制标记区"],
        "focus": ["破损", "污染", "裂纹", "色差"],
        "region_component_map": {"top": "压制标记区", "middle": "药片表面", "bottom": "边缘"},
        "knowledge_notes": [
            "药片边缘破损通常需要优先关注完整性与包装耐受性。",
            "压制标记区异常可能影响识别与批次区分。",
        ],
    },
    "screw": {
        "display_name": "工业螺钉",
        "function_summary": "承担连接紧固功能，重点关注螺钉头部、螺纹区和连接端。",
        "components": ["螺钉头部", "螺纹区", "连接端"],
        "focus": ["螺纹损伤", "头部破损", "弯曲", "污染"],
        "region_component_map": {"top": "螺钉头部", "middle": "螺纹区", "bottom": "连接端"},
        "knowledge_notes": [
            "螺纹区异常通常直接影响紧固配合与重复装配可靠性。",
            "头部受力槽破损会影响工具啮合与拧紧过程。",
            "连接端弯曲或毛刺需要关注装配导入与接触安全。",
        ],
    },
    "tile": {
        "display_name": "瓷砖面材",
        "function_summary": "关注角部区域、表层釉面和边缘完整性与色泽一致性。",
        "components": ["角部区域", "表层釉面", "边缘"],
        "focus": ["裂纹", "缺口", "污染", "色差"],
        "region_component_map": {"top": "角部区域", "middle": "表层釉面", "bottom": "边缘"},
        "knowledge_notes": [
            "角部与边缘异常通常更容易影响铺装完整性与运输耐受性。",
            "釉面异常需要结合外观标准和使用场景评估影响。",
        ],
    },
    "toothbrush": {
        "display_name": "牙刷组件",
        "function_summary": "关注刷头、刷毛区和手柄连接部的完整性与排列一致性。",
        "components": ["刷头", "刷毛区", "手柄连接部"],
        "focus": ["刷毛缺失", "连接异常", "污染", "变形"],
        "region_component_map": {"top": "刷头", "middle": "刷毛区", "bottom": "手柄连接部"},
        "knowledge_notes": [
            "刷毛区异常通常直接影响使用体验与清洁能力。",
            "手柄连接部异常需要关注连接牢固性与整体耐久性。",
        ],
    },
    "transistor": {
        "display_name": "晶体管器件",
        "function_summary": "承担电子开关或放大功能，重点关注封装体、引脚区和封装边缘。",
        "components": ["引脚区", "封装体", "封装边缘"],
        "focus": ["封装破损", "引脚异常", "污染", "裂纹"],
        "region_component_map": {"top": "引脚区", "middle": "封装体", "bottom": "封装边缘"},
        "knowledge_notes": [
            "引脚区异常通常优先影响焊接、导通与装配稳定性。",
            "封装体裂纹或污染需要关注绝缘与长期可靠性。",
        ],
    },
    "wood": {
        "display_name": "木质面材",
        "function_summary": "关注边缘、表层纹理区和节疤附近区域，避免影响结构和外观一致性。",
        "components": ["边缘", "表层纹理区", "节疤附近区域"],
        "focus": ["裂纹", "划伤", "污渍", "纹理异常"],
        "region_component_map": {"top": "边缘", "middle": "表层纹理区", "bottom": "节疤附近区域"},
        "knowledge_notes": [
            "边缘裂纹或缺口通常更容易在后续加工中继续扩展。",
            "纹理异常需要结合天然材料特征与工艺标准综合判断。",
        ],
    },
    "zipper": {
        "display_name": "拉链组件",
        "function_summary": "承担开合与咬合功能，重点关注滑块接触区、齿列区和布带区。",
        "components": ["滑块接触区", "齿列区", "布带区"],
        "focus": ["缺齿", "错位", "污染", "布带破损"],
        "region_component_map": {"top": "滑块接触区", "middle": "齿列区", "bottom": "布带区"},
        "knowledge_notes": [
            "齿列区异常通常优先影响咬合连续性与开合顺畅性。",
            "滑块接触区异常需要关注局部磨损和操作阻力变化。",
            "布带区异常则更多影响整体结构支撑与使用寿命。",
        ],
    },
}


def _merge_object_context(profile: ObjectProfile, object_context: dict[str, Any] | None) -> ObjectProfile:
    merged = deepcopy(profile)
    for key, value in (object_context or {}).items():
        if value in (None, "", [], {}):
            continue
        merged[key] = value
    return merged


def get_object_profile(category: str | None, *, object_context: dict[str, Any] | None = None) -> ObjectProfile:
    key = str(category or "").strip().lower()
    profile = MVTEC_OBJECT_PROFILES.get(key, {})
    default_profile: ObjectProfile = {
        "category": key or "unknown",
        "display_name": key or "工业部件",
        "function_summary": "当前类别缺少专门的产品画像，可结合现场工艺、结构语义和部件功能进一步补充。",
        "components": ["关键功能区", "表面主体", "边缘区域"],
        "focus": ["表面异常", "结构损伤", "污染"],
        "region_component_map": {},
        "knowledge_notes": [
            "当前对象分析主要依赖默认规则画像，建议补充更细的产品结构和功能背景。",
        ],
    }
    resolved = {**default_profile, **deepcopy(profile)}
    resolved = _merge_object_context(resolved, object_context)
    resolved["category"] = key or resolved.get("category", "unknown")
    return resolved


def _pick_component_by_position(components: list[str], location: str, region_map: dict[str, Any]) -> str:
    lowered = location.lower()
    for token, mapped in region_map.items():
        if token in lowered:
            if isinstance(mapped, str):
                return mapped
            if isinstance(mapped, int) and components:
                index = mapped if mapped >= 0 else len(components) + mapped
                index = min(max(index, 0), len(components) - 1)
                return components[index]

    for token, fallback_index in DEFAULT_REGION_COMPONENT_MAP.items():
        if token in lowered and components:
            index = fallback_index if fallback_index >= 0 else len(components) + fallback_index
            index = min(max(index, 0), len(components) - 1)
            return components[index]
    return components[min(1, len(components) - 1)] if components else "关键功能区"


def _derive_component_findings(profile: ObjectProfile, anomalies: list[dict[str, Any]]) -> list[dict[str, Any]]:
    components = [str(item) for item in profile.get("components", [])]
    region_map = profile.get("region_component_map", {}) or {}
    findings: list[dict[str, Any]] = []

    for item in anomalies:
        location = str(item.get("location") or "").strip() or "unknown"
        component = _pick_component_by_position(components, location, region_map)
        findings.append(
            {
                "component": component,
                "location": location,
                "anomaly_type": str(item.get("type") or "surface_anomaly"),
                "severity_hint": str(item.get("severity_hint") or ""),
                "description": str(item.get("description") or ""),
            }
        )

    ordered: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for item in findings:
        key = (item["component"], item["location"])
        if key in seen:
            continue
        seen.add(key)
        ordered.append(item)
    return ordered


def _derive_component_scope(profile: ObjectProfile, anomalies: list[dict[str, Any]]) -> list[str]:
    base_components = [str(item) for item in profile.get("components", [])]
    findings = _derive_component_findings(profile, anomalies)
    scoped = [item["component"] for item in findings]
    ordered = list(dict.fromkeys(scoped + base_components))
    return ordered[:3]


def _derive_functional_impact(profile: ObjectProfile, anomalies: list[dict[str, Any]], component_scope: list[str]) -> list[str]:
    focus = [str(item) for item in profile.get("focus", [])]
    severity = "medium"
    if anomalies:
        max_score = max(float(item.get("score", 0.0) or 0.0) for item in anomalies if isinstance(item, dict))
        if max_score >= 0.75:
            severity = "high"
        elif max_score < 0.45:
            severity = "low"

    impact_notes = [
        f"当前异常主要涉及 {component_scope[0]}，建议结合该部位的结构完整性、装配要求或功能负载判断是否影响后续使用。"
    ]
    if len(component_scope) > 1:
        impact_notes.append(
            f"如异常进一步扩展到 {component_scope[1]}，可能影响 {profile.get('display_name', '该部件')} 的局部功能稳定性。"
        )
    if focus:
        impact_notes.append(f"该类别常见关注点包括：{'、'.join(focus[:3])}。")
    if severity == "high":
        impact_notes.append("当前异常响应较强，若位于关键受力、密封或导通区域，应优先按高风险缺陷处理。")
    elif severity == "medium":
        impact_notes.append("当前异常响应中等，建议结合工艺标准和历史案例确认是否会持续扩大或影响可靠性。")
    else:
        impact_notes.append("当前异常响应较弱，可结合历史记录判断其是否属于早期缺陷或可接受纹理波动。")
    return impact_notes


def _build_object_knowledge_notes(profile: ObjectProfile, component_scope: list[str]) -> list[str]:
    notes = [str(item) for item in profile.get("knowledge_notes", []) if str(item).strip()]
    if component_scope:
        notes.insert(0, f"本次分析重点部件为：{'、'.join(component_scope)}。")
    return notes[:5]


def build_structured_object_analysis(
    *,
    category: str | None,
    anomalies: list[dict[str, Any]] | None = None,
    asset_id: str | None = None,
    object_context: dict[str, Any] | None = None,
    query_text: str = "",
) -> dict[str, Any]:
    profile = get_object_profile(category, object_context=object_context)
    anomalies = [item for item in (anomalies or []) if isinstance(item, dict)]
    component_findings = _derive_component_findings(profile, anomalies)
    component_scope = _derive_component_scope(profile, anomalies)
    functional_impact = _derive_functional_impact(profile, anomalies, component_scope)
    knowledge_hits = query_object_knowledge(
        category=profile.get("category"),
        anomalies=anomalies,
        query_text=query_text,
    )
    object_knowledge_notes = _build_object_knowledge_notes(profile, component_scope)
    object_knowledge_notes.extend(
        item["note"] for item in knowledge_hits if item.get("note") and item.get("note") not in object_knowledge_notes
    )
    object_knowledge_notes = object_knowledge_notes[:6]

    object_summary = (
        f"{profile['display_name']}（asset_id={asset_id or 'unknown'}）的主要关注部位包括 {'、'.join(component_scope)}。"
        f"其核心功能背景是：{profile['function_summary']}"
    )
    object_knowledge_summary = (
        f"结合该对象的默认产品知识，当前更应优先关注 {'、'.join(component_scope[:2])} 的功能连续性、结构完整性和工艺一致性。"
    )

    prompt_sections = [
        "[Object profile]",
        f"- 类别: {profile['display_name']}",
        f"- 资产标识: {asset_id or 'unknown'}",
        f"- 功能概述: {profile['function_summary']}",
        "",
        "[Component scope]",
        *(f"- {item}" for item in component_scope),
        "",
        "[Component findings]",
        *(
            f"- {item['location']} 对应 {item['component']}，异常类型 {item['anomaly_type']}"
            for item in component_findings
        ),
        "",
        "[Functional impact]",
        *(f"- {item}" for item in functional_impact),
        "",
        "[Object knowledge]",
        *(f"- {item['title']}: {item['note']}" for item in knowledge_hits),
        *(f"- {item}" for item in object_knowledge_notes),
    ]

    return {
        "object_profile": profile,
        "component_scope": component_scope,
        "component_findings": component_findings,
        "functional_impact": functional_impact,
        "object_summary": object_summary,
        "object_knowledge_notes": object_knowledge_notes,
        "object_knowledge_summary": object_knowledge_summary,
        "object_knowledge_hits": knowledge_hits,
        "prompt_context": "\n".join(section for section in prompt_sections if section is not None).strip(),
    }
