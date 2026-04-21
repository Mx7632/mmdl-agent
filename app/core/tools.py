"""
基于 LangChain 标准的工具集定义，用于 Agent 动态编排。
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Type

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from app.schemas.detection import DetectionTask, DetectionResult
from app.tools.anomaly_detection import HttpAnomalyDetectionTool
from app.tools.image_anomaly_detection import ImageAnomalyDetectionTool
from app.rag.service import RagService

# ─── 参数模型定义 ─────────────────────────────────────────────────────────

class TimeSeriesDetectInput(BaseModel):
    task_id: str = Field(..., description="任务唯一标识符")
    asset_id: str = Field(..., description="工业资产或设备 ID")
    start_time: str = Field(..., description="ISO8601 开始时间")
    end_time: str = Field(..., description="ISO8601 结束时间")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="额外的检测参数，如阈值等")

class ImageDetectInput(BaseModel):
    task_id: str = Field(..., description="任务唯一标识符")
    asset_id: str = Field(..., description="工业资产或设备 ID")
    image_base64: Optional[str] = Field(None, description="Base64 编码的图像数据。如果任务已附带图片，该参数可省略。")
    question: Optional[str] = Field(None, description="针对图像的特定问题")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="视觉模型参数")

class RagQueryInput(BaseModel):
    query: str = Field(..., description="检索关键词或描述性短语")
    top_k: int = Field(3, description="返回的最相关案例数量")
    category: Optional[str] = Field(None, description="资产类别，用于缩小检索范围")

# ─── 工具类定义 ───────────────────────────────────────────────────────────

class TimeSeriesAnomalyTool(BaseTool):
    name: str = "timeseries_anomaly_detection"
    description: str = "用于分析传感器数值序列、振动数据等时序数据的异常。支持通过 HTTP 调用专业检测算法。"
    args_schema: Type[BaseModel] = TimeSeriesDetectInput

    def _run(self, **kwargs: Any) -> str:
        raise NotImplementedError("This tool only supports async execution via _arun")

    async def _arun(self, **kwargs: Any) -> str:
        task = DetectionTask(
            task_id=kwargs["task_id"],
            asset_id=kwargs["asset_id"],
            start_time=kwargs["start_time"],
            end_time=kwargs["end_time"],
            parameters=kwargs.get("parameters", {})
        )
        tool = HttpAnomalyDetectionTool()
        response = await tool.run(task)
        if response.success and response.result:
            return response.result.model_dump_json()
        return f"Error: {response.error or 'Unknown error'}"

class VisualAnomalyTool(BaseTool):
    name: str = "visual_anomaly_detection"
    description: str = "用于通过图像或照片识别工业设备表面缺陷、漏油、仪表异常等。基于视觉大模型分析。"
    args_schema: Type[BaseModel] = ImageDetectInput

    def _run(self, **kwargs: Any) -> str:
        raise NotImplementedError("This tool only supports async execution via _arun")

    async def _arun(self, **kwargs: Any) -> str:
        task = DetectionTask(
            task_id=kwargs["task_id"],
            asset_id=kwargs["asset_id"],
            start_time="now", # 图像检测通常是即时的
            end_time="now",
            parameters={
                "image_base64": kwargs["image_base64"],
                **kwargs.get("parameters", {})
            },
            question=kwargs.get("question")
        )
        tool = ImageAnomalyDetectionTool()
        response = await tool.run(task)
        if response.success and response.result:
            return response.result.model_dump_json()
        return f"Error: {response.error or 'Unknown error'}"

class KnowledgeRetrievalTool(BaseTool):
    name: str = "knowledge_retrieval"
    description: str = "检索工业领域知识库、设备手册、历史故障案例及相似异常样本。用于辅助诊断和提供处理建议。"
    args_schema: Type[BaseModel] = RagQueryInput

    def _run(self, query: str, top_k: int = 3, category: Optional[str] = None) -> str:
        raise NotImplementedError("This tool only supports async execution via _arun")

    async def _arun(self, query: str, top_k: int = 3, category: Optional[str] = None) -> str:
        rag_service = RagService()
        results = rag_service.retriever.retrieve_similar(
            query_description=query,
            top_k=top_k,
            category=category
        )
        return rag_service.retriever.format_for_prompt(results)

# ─── 工具导出 ─────────────────────────────────────────────────────────────

def get_industrial_tools() -> List[BaseTool]:
    """获取所有可用的工业 Agent 工具。"""
    return [
        TimeSeriesAnomalyTool(),
        VisualAnomalyTool(),
        KnowledgeRetrievalTool()
    ]
