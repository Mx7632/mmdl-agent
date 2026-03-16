from __future__ import annotations

import logging

from langchain_openai import ChatOpenAI

from app.config.settings import settings
from app.exceptions.base import ConfigurationError, DataMissingError, ModelError
from app.memory.state import DetectionState
from app.prompts.image_report import IMAGE_REPORT_PROMPT
from app.tools.image_anomaly_detection import ImageAnomalyDetectionTool

logger = logging.getLogger(__name__)


def _is_image_task(state: DetectionState) -> bool:
    if getattr(state.task, "input_type", None) == "image":
        return True
    params = state.task.parameters or {}
    return bool(params.get("image_base64"))


async def load_data_node(state: DetectionState) -> DetectionState:
    if not state.task:
        raise DataMissingError("DetectionTask missing")
    state.context["loaded"] = True
    state.logs.append("Data loaded")
    return state


async def anomaly_detect_node(state: DetectionState) -> DetectionState:
    params = state.task.parameters or {}
    tool_type = params.get("tool_type")
    if tool_type not in (None, "qwen3.5-plus", "qwen3.5-plus_image"):
        # For now we only support image detection with qwen3.5-plus.
        state.errors.append(f"unsupported_tool_type: {tool_type}")
    tool = ImageAnomalyDetectionTool()

    response = await tool.run(state.task)
    if response.success and response.result:
        state.result = response.result
        state.logs.append(f"Anomaly detection completed using {tool.name}")
    else:
        state.errors.append(response.error or "Unknown tool error")
    return state


async def summarize_node(state: DetectionState) -> DetectionState:
    if not state.result:
        state.logs.append("No result to summarize")
        return state

    if not settings.openai_api_key:
        raise ConfigurationError("openai_api_key not configured", config_key="APP_OPENAI_API_KEY")

    try:
        llm = ChatOpenAI(
            model=settings.llm_model,
            temperature=settings.llm_temperature,
            api_key=settings.openai_api_key,
            timeout=settings.llm_timeout,
            max_tokens=settings.llm_max_tokens,
            base_url=settings.llm_base_url,
            extra_body={"enable_thinking": False},
        )

        messages = IMAGE_REPORT_PROMPT.format_messages(
            task_id=state.task.task_id,
            asset_id=state.task.asset_id,
            start_time=state.task.start_time,
            end_time=state.task.end_time,
            question=state.task.question or "",
            anomalies=state.result.anomalies,
        )

        response = await llm.ainvoke(messages)
        state.result.summary = getattr(response, "content", str(response))
        state.logs.append("LLM summary generated")
    except Exception as e:
        logger.error(f"LLM invocation failed: {str(e)}")
        # Degrade gracefully: return detection output even if report generation fails.
        state.errors.append(f"summary_failed: {str(e)}")
        state.result.summary = (
            "报告生成失败（LLM 不可用或鉴权失败）。"
        )
        state.result.metadata = dict(state.result.metadata or {})
        state.result.metadata["summary_failed"] = True

    return state
