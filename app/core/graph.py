from __future__ import annotations

import logging

from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from app.config.settings import settings
from app.exceptions.base import ConfigurationError, DataMissingError
from app.memory.state import DetectionState
from app.prompts.image_report import IMAGE_REPORT_PROMPT
from app.rag.service import build_anomaly_query_text, get_rag_service
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

        # RAG: 根据检测结果检索相似工业异常案例
        rag_context = ""
        if settings.rag_enabled:
            try:
                query_text = build_anomaly_query_text(state.result.anomalies)
                if query_text:
                    category = state.task.parameters.get("category") if state.task.parameters else None
                    rag_context = get_rag_service().query_similar(
                        query_text=query_text,
                        category=category,
                        top_k=settings.rag_top_k,
                    )
                else:
                    rag_context = "未生成有效异常查询，跳过 RAG 检索。"
            except Exception as exc:
                rag_context = "RAG 检索失败，已跳过。"
                state.errors.append(f"rag_failed: {exc}")

        state.context["rag_context"] = rag_context
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
            api_key=SecretStr(settings.openai_api_key),
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
            rag_context=state.context.get("rag_context", "未启用 RAG 检索。"),
        )

        response = await llm.ainvoke(messages)
        state.result.summary = getattr(response, "content", str(response))
        state.logs.append("LLM summary generated")

        # 高置信度样本自动增量入库（用户后续可用）
        if settings.rag_enabled:
            try:
                params = state.task.parameters or {}
                image_path = params.get("image_path", "")
                category = params.get("category", "unknown")
                if image_path and state.result.anomalies:
                    top_score = max(float(a.get("score", 0.0)) for a in state.result.anomalies)
                    if state.task.question:
                        get_rag_service().add_online_case(
                            image_path=image_path,
                            category=category,
                            user_description=state.task.question,
                            model_confidence=top_score,
                            is_anomaly=True,
                            anomaly_type=state.result.anomalies[0].get("type"),
                            severity="unknown",
                        )
            except Exception as exc:
                state.errors.append(f"rag_online_ingest_failed: {exc}")
    except Exception as e:
        logger.error(f"LLM invocation failed: {str(e)}")
        state.errors.append(f"summary_failed: {str(e)}")
        state.result.summary = "报告生成失败（LLM 不可用或鉴权失败）。"
        state.result.metadata = dict(state.result.metadata or {})
        state.result.metadata["summary_failed"] = True

    return state
