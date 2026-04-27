# LEGACY: retained for reference only; not used by the current supervisor-based graph.
"""
补充分析节点（Supplement Node�?
职责�?
  - �?self_reflect 判定置信度不足时，对检测结果进行补充分�?
  - 增加 loop_count 计数
  - 可结合用户回复内容（conversation_history）做更有针对性的分析
  - 不会重新调用视觉模型，只对已有结果做深化处理
"""

from __future__ import annotations

import logging
from typing import Any, List

from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from app.config.settings import settings
from app.memory.state import DetectionState
from app.exceptions.base import ConfigurationError

logger = logging.getLogger(__name__)


async def supplement_node(state: DetectionState) -> DetectionState:
    """
    补充分析节点�?
      - 在已有检测结果基础上，�?LLM 做深化分�?
      - 结合对话历史（用户补充信息）提升置信�?
      - 增加 loop_count，写�?context['supplement_done']
    """
    # ── 计数器递增 ──
    state.loop_count += 1
    state.logs.append(
        f"[补充分析] �?{state.loop_count} 轮，置信�?{state.confidence:.2f}，开始深化分�?
    )

    if not state.result:
        state.errors.append("补充分析失败：无检测结果可分析")
        return state

    # ── 收集上下�?──
    conversation_context = ""
    if state.conversation_history:
        entries = [
            f"[{m['role']}] {m['content']}"
            for m in state.conversation_history
            if m.get("content")
        ]
        conversation_context = "\n".join(entries)

    # ── 构造深化分�?Prompt ──
    anomaly_str = "\n".join(
        f"- type={a.get('type', 'unknown')}, score={a.get('score', 0):.2f}, "
        f"details={a.get('details', '')}"
        for a in (state.result.anomalies or [])
    )

    user_input_context = (
        f"\n\n## 用户补充信息\n{conversation_context}"
        if conversation_context
        else "\n\n## 用户补充信息\n（无�?
    )

    prompt = f"""你是一名工业设备图像异常检测专家，正在对已有检测结果进行深化分析�?

## 已知异常列表
{anomaly_str or '（无异常�?}

## 原始任务信息
- 任务ID: {state.task.task_id}
- 资产ID: {state.task.asset_id}
- 用户问题: {state.task.question or '（无�?}
{user_input_context}

## 你的任务
请在已有异常列表基础上，结合专业知识进行深化分析�?
1. 补充每个异常的【可能成因】和【风险等级�?
2. 如果某些异常在图中证据不足，标注�?待核�?
3. 提升整体置信度（如果分析后确实可信度高）

输出严格 JSON（不要有任何额外文本）：
{{
  "anomalies": [
    {{
      "type": "异常类型",
      "score": 0.0~1.0 置信度分�?
      "details": "详细描述",
      "possible_causes": ["可能原因1", "可能原因2"],
      "risk_level": "high|medium|low",
      "needs_verification": true或false（证据不足时为true�?
    }}
  ],
  "overall_confidence": 0.0~1.0，整体置信度
}}

注意�?
- 只在有充分理由时提升分数
- 如果原结果中异常置信度偏低且无明确证据，设为"待核�?
- anomalies 列表可以增删修改
"""


    if not settings.openai_api_key:
        raise ConfigurationError(
            "openai_api_key 未配�?,
            config_key="APP_OPENAI_API_KEY",
        )

    llm = ChatOpenAI(
        model=settings.llm_model,
        temperature=0.1,
        api_key=SecretStr(settings.openai_api_key),
        timeout=settings.llm_timeout,
        max_tokens=600,
        base_url=settings.llm_base_url,
        extra_body={"enable_thinking": False},
    )

    try:
        response = await llm.ainvoke([{"role": "user", "content": prompt}])
        raw = getattr(response, "content", "") or ""
        parsed = _parse_json(raw)
    except Exception as e:
        logger.warning(f"[补充分析] LLM 调用失败，降级保留原结果: {e}")
        parsed = None

    if parsed and isinstance(parsed.get("anomalies"), list):
        # 更新异常列表
        state.result.anomalies = parsed["anomalies"]
        state.confidence = float(parsed.get("overall_confidence", state.confidence))
        state.context["supplement_done"] = True
        state.context["supplement_round"] = state.loop_count
        state.logs.append(
            f"[补充分析] �?{state.loop_count} 轮完成，置信度提升至 {state.confidence:.2f}"
        )
    else:
        state.context["supplement_done"] = False
        state.errors.append("补充分析结果解析失败，保留原结果")

    return state


def _parse_json(raw: str) -> Any:
    import json, re
    raw = raw.strip()
    try:
        return json.loads(raw)
    except Exception:
        pass
    m = re.search(r"\{[\s\S]*\}", raw)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            pass
    return None

