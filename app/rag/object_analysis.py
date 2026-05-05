from __future__ import annotations

from typing import Any


MVTEC_OBJECT_PROFILES: dict[str, dict[str, Any]] = {
    "bottle": {
        "display_name": "玻璃瓶",
        "function_summary": "用于承载与密封内容物，重点关注瓶身完整性、瓶口封口区和污染残留。",
        "components": ["瓶身", "瓶口封口区", "瓶底过渡区"],
        "focus": ["裂纹", "边缘缺口", "污染残留", "封口区异常"],
    },
    "cable": {
        "display_name": "工业线缆",
        "function_summary": "承担导电与绝缘功能，重点关注护套完整性、导体连接区和表面磨损。",
        "components": ["外护套", "连接端区域", "线缆弯折区"],
        "focus": ["护套破损", "磨损", "污染", "连接端异常"],
    },
    "capsule": {
        "display_name": "胶囊制品",
        "function_summary": "用于药品或颗粒封装，重点关注壳体表面完整性、拼接边和污染。",
        "components": ["胶囊壳体", "拼接边", "端部圆角区"],
        "focus": ["裂纹", "凹陷", "污染", "边缘异常"],
    },
    "carpet": {
        "display_name": "工业地毯面材",
        "function_summary": "承担表面覆盖和纹理一致性要求，重点关注织物纹理、表层污染和破损。",
        "components": ["表层织物", "边缘区域", "纹理过渡区"],
        "focus": ["污染", "纤维断裂", "纹理错位", "磨损"],
    },
    "grid": {
        "display_name": "网格面板",
        "function_summary": "强调网格排列一致性与结构完整性，重点关注栅格间距、断裂和形变。",
        "components": ["网格主体", "交叉节点", "边框区域"],
        "focus": ["变形", "断裂", "错位", "污染"],
    },
    "hazelnut": {
        "display_name": "榛果表面样本",
        "function_summary": "关注外壳表面完整性与色泽均匀性，重点检查裂纹、凹陷和污染。",
        "components": ["外壳表面", "顶部区域", "底部接触面"],
        "focus": ["裂纹", "凹陷", "污染", "色差"],
    },
    "leather": {
        "display_name": "皮革面材",
        "function_summary": "强调表面纹理与完整性，重点关注划伤、起皱、孔洞和污染。",
        "components": ["表层皮面", "纹理区域", "边缘裁切区"],
        "focus": ["划伤", "破洞", "起皱", "污染"],
    },
    "metal_nut": {
        "display_name": "金属螺母",
        "function_summary": "承担连接与紧固功能，重点关注外缘完整性、螺纹区和表面损伤。",
        "components": ["外缘", "内孔螺纹区", "受力接触面"],
        "focus": ["缺口", "裂纹", "磨损", "污染"],
    },
    "pill": {
        "display_name": "药片制品",
        "function_summary": "关注表面完整性、边缘破损和污染，避免影响识别与使用安全。",
        "components": ["药片表面", "边缘", "压制标记区"],
        "focus": ["破损", "污染", "裂纹", "色差"],
    },
    "screw": {
        "display_name": "工业螺钉",
        "function_summary": "承担连接紧固功能，重点关注螺纹完整性、头部受力槽和表面破损。",
        "components": ["螺纹区", "螺钉头部", "连接端"],
        "focus": ["螺纹损伤", "头部破损", "弯曲", "污染"],
    },
    "tile": {
        "display_name": "瓷砖面材",
        "function_summary": "关注表面平整度、边缘完整性与色泽一致性。",
        "components": ["表层釉面", "边缘", "角部区域"],
        "focus": ["裂纹", "缺口", "污染", "色差"],
    },
    "toothbrush": {
        "display_name": "牙刷组件",
        "function_summary": "关注刷头、刷毛排列和手柄连接完整性。",
        "components": ["刷头", "刷毛区", "手柄连接部"],
        "focus": ["刷毛缺失", "连接异常", "污染", "变形"],
    },
    "transistor": {
        "display_name": "晶体管器件",
        "function_summary": "承担电子开关/放大功能，重点关注封装完整性、引脚区和表面污染。",
        "components": ["器件封装体", "引脚区", "边缘封装线"],
        "focus": ["封装破损", "引脚异常", "污染", "裂纹"],
    },
    "wood": {
        "display_name": "木质面材",
        "function_summary": "关注纹理连续性、表面破损和污渍，避免影响结构和外观一致性。",
        "components": ["表层纹理区", "边缘", "节疤附近区域"],
        "focus": ["裂纹", "划伤", "污渍", "纹理异常"],
    },
    "zipper": {
        "display_name": "拉链组件",
        "function_summary": "承担开合与咬合功能，重点关注齿列完整性、布带和滑块区域。",
        "components": ["齿列区", "布带区", "滑块接触区"],
        "focus": ["缺齿", "错位", "污染", "布带破损"],
    },
}


def get_object_profile(category: str | None) -> dict[str, Any]:
    key = str(category or "").strip().lower()
    profile = MVTEC_OBJECT_PROFILES.get(key)
    if profile:
        return {"category": key, **profile}
    return {
        "category": key or "unknown",
        "display_name": key or "工业部件",
        "function_summary": "当前类别缺少专门的产品画像，可结合现场工艺与部件功能进一步补充。",
        "components": ["关键功能区", "边缘区域", "表面主体"],
        "focus": ["表面异常", "结构损伤", "污染"],
    }


def _derive_component_scope(profile: dict[str, Any], anomalies: list[dict[str, Any]]) -> list[str]:
    base_components = [str(item) for item in profile.get("components", [])]
    if not anomalies:
        return base_components[:3]

    scoped: list[str] = []
    for item in anomalies:
        location = str(item.get("location") or "").lower()
        if any(token in location for token in ("top", "upper")) and base_components:
            scoped.append(base_components[0])
        elif any(token in location for token in ("bottom", "lower")) and len(base_components) > 1:
            scoped.append(base_components[-1])
        elif any(token in location for token in ("left", "right", "middle", "center")) and len(base_components) > 1:
            scoped.append(base_components[min(1, len(base_components) - 1)])

    ordered = list(dict.fromkeys(scoped + base_components))
    return ordered[:3]


def _derive_functional_impact(profile: dict[str, Any], anomalies: list[dict[str, Any]]) -> list[str]:
    components = _derive_component_scope(profile, anomalies)
    focus = [str(item) for item in profile.get("focus", [])]
    severity = "medium"
    if anomalies:
        max_score = max(float(item.get("score", 0.0) or 0.0) for item in anomalies if isinstance(item, dict))
        if max_score >= 0.75:
            severity = "high"
        elif max_score < 0.45:
            severity = "low"

    impact_notes = [
        f"当前异常主要涉及 {components[0]}，建议结合该部位的结构完整性与装配要求判断是否影响后续使用。"
    ]
    if len(components) > 1:
        impact_notes.append(f"如异常扩展到 {components[1]}，可能进一步影响 {profile.get('display_name', '该部件')} 的局部功能稳定性。")
    if focus:
        impact_notes.append(f"该类别常见关注点包括：{'、'.join(focus[:3])}。")
    if severity == "high":
        impact_notes.append("当前异常响应较强，若位于关键受力、密封或导通区域，应优先按高风险缺陷处理。")
    elif severity == "medium":
        impact_notes.append("当前异常响应中等，建议结合工艺标准和历史案例确认是否会持续扩大或影响可靠性。")
    else:
        impact_notes.append("当前异常响应较弱，可结合历史记录判断其是否属于早期缺陷或可接受纹理波动。")
    return impact_notes


def build_structured_object_analysis(
    *,
    category: str | None,
    anomalies: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    profile = get_object_profile(category)
    anomalies = [item for item in (anomalies or []) if isinstance(item, dict)]
    component_scope = _derive_component_scope(profile, anomalies)
    functional_impact = _derive_functional_impact(profile, anomalies)
    object_summary = (
        f"{profile['display_name']} 的主要关注部位包括 {', '.join(component_scope)}。"
        f"其核心功能背景是：{profile['function_summary']}"
    )
    prompt_sections = [
        "[Object profile]",
        f"- 类别: {profile['display_name']}",
        f"- 功能概述: {profile['function_summary']}",
        "",
        "[Component scope]",
        *(f"- {item}" for item in component_scope),
        "",
        "[Functional impact]",
        *(f"- {item}" for item in functional_impact),
    ]
    return {
        "object_profile": profile,
        "component_scope": component_scope,
        "functional_impact": functional_impact,
        "object_summary": object_summary,
        "prompt_context": "\n".join(prompt_sections).strip(),
    }
