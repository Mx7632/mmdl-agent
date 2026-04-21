"""
自检节点（Self-Reflect Node）
职责：
  1. 评估当前检测结果的置信度
  2. 检查是否有未知异常类型需要用户澄清
  3. 查询长期记忆，获取同类案例参考
  4. 输出路由决策 → "proceed" | "retry" | "need_user"
"""

from __future__ import annotations

import logging
from typing import Any, List, Optional

from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from app.config.settings import settings
from app.memory.models import LongTermMemory
from app.memory.memory_manager import memory_manager
from app.memory.state import DetectionState
from app.exceptions.base import ConfigurationError, MaxTurnsError

logger = logging.getLogger(__name__)

# 最大循环轮次（熔断）
MAX_LOOP = 3

# 置信度阈值：低于此值则触发补充分析
CONFIDENCE_THRESHOLD = 0.7


def _build_reflection_prompt(
    anomalies: List[Any],
    history_text: str,
) -> str:
    """构造自检 Prompt，要求模型评估置信度并列出未知异常类型。"""
    anomaly_str = "\n".join(
        f"- type={a.get('type', 'unknown')}, score={a.get('score', 0):.2f}, details={a.get('details', '')}"
        for a in anomalies
    )
    return f"""你是一名工业设备图像异常检测的质量审核员。

请对以下检测结果进行质量评估：

## 本次检测异常列表
{anomaly_str or '（无异常）'}

## 历史同类检测摘要（参考用）
{history_text or '（无历史记录）'}

请输出严格 JSON（不要有任何额外文本）：
{{
  "confidence": 0.0~1.0 之间的浮点数，表示总体置信度，
  "reasoning": "一句话说明置信度判断依据",
  "unknown_anomaly_types": ["列出本次检测中你无法确认、需要人工核实的异常类型名称"],
  "can_proceed": true或false，是否可以直接生成报告
}}

规则：
- 如果异常列表为空，confidence=1.0，can_proceed=true
- 如果存在未知类型异常，can_proceed=false，unknown_anomaly_types 填入类型名
- 如果置信度 < 0.7，can_proceed=false
- 其他情况 can_proceed=true
"""


async def self_reflect_node(state: DetectionState) -> DetectionState:
    """
    自检节点：
      - 检查 loop_count 是否超限（熔断）
      - 调用 LLM 做置信度评估 + 未知异常识别
      - 查询长期记忆作为上下文
      - 写入 reflection_decision / confidence / unknown_anomaly_types
    """
    # ── 熔断检查 ──
    if state.loop_count >= MAX_LOOP:
        state.logs.append(
            f"[自检] 达到最大循环次数 {MAX_LOOP}，强制进入报告生成"
        )
        state.reflection_decision = "proceed"
        state.needs_user_input = False
        return state

    if not state.result:
        state.logs.append("[自检] 无检测结果，跳过自检")
        state.reflection_decision = "proceed"
        return state

    # ── 查询长期记忆 ──
    user_id = (state.task.parameters or {}).get("user_id", "default_user")
    long_term_memories = memory_manager.get_long_term_memory(user_id)
    history_text = (
        "\n".join(f"- {m.memory_summary[:200]}" for m in long_term_memories[-3:])
        or "（无历史记录）"
    )

    # ── 调用 LLM 自检 ──
    if not settings.openai_api_key:
        raise ConfigurationError(
            "openai_api_key 未配置",
            config_key="APP_OPENAI_API_KEY",
        )

    llm = ChatOpenAI(
        model=settings.llm_model,
        temperature=0.0,
        api_key=SecretStr(settings.openai_api_key),
        timeout=settings.llm_timeout,
        max_tokens=400,
        base_url=settings.llm_base_url,
        extra_body={"enable_thinking": False},
    )

    prompt = _build_reflection_prompt(
        anomalies=state.result.anomalies or [],
        history_text=history_text,
    )

    try:
        response = await llm.ainvoke([{"role": "user", "content": prompt}])
        raw = getattr(response, "content", "") or ""
        parsed = _parse_json(raw)
    except Exception as e:
        logger.warning(f"[自检] LLM 调用失败，降级处理: {e}")
        parsed = None

    # ── 解析结果并写回状态 ──
    if parsed:
        state.confidence = float(parsed.get("confidence", 0.5))
        state.unknown_anomaly_types = parsed.get("unknown_anomaly_types") or []
        can_proceed = bool(parsed.get("can_proceed", False))
    else:
        # LLM 降级：置信度设为阈值，无未知类型
        state.confidence = CONFIDENCE_THRESHOLD
        state.unknown_anomaly_types = []
        can_proceed = True

    # ── 路由决策 ──
    if not can_proceed:
        if state.unknown_anomaly_types:
            # 有未知异常类型 → 需要用户澄清
            state.reflection_decision = "need_user"
            state.needs_user_input = True
            state.logs.append(
                f"[自检] 置信度={state.confidence:.2f}，"
                f"存在未知类型: {state.unknown_anomaly_types}，等待用户澄清"
            )
        else:
            # 置信度低但无未知类型 → 补充分析
            state.reflection_decision = "retry"
            state.needs_user_input = False
            state.logs.append(
                f"[自检] 置信度={state.confidence:.2f} < {CONFIDENCE_THRESHOLD}，"
                f"触发补充分析（第 {state.loop_count + 1} 轮）"
            )
    else:
        state.reflection_decision = "proceed"
        state.needs_user_input = False
        state.logs.append(
            f"[自检] 置信度={state.confidence:.2f}，可进入报告生成"
        )

    return state


def _parse_json(raw: str) -> Optional[dict]:
    """从 LLM 输出中安全解析 JSON。"""
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
