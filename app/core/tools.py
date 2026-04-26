"""
Tool definitions exposed to the LangChain/LangGraph planner.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Type

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from app.rag.service import RagService
from app.schemas.detection import DetectionTask
from app.tools.anomaly_detection import HttpAnomalyDetectionTool
from app.tools.image_anomaly_detection import ImageAnomalyDetectionTool


class TimeSeriesDetectInput(BaseModel):
    task_id: str = Field(..., description="Task identifier")
    asset_id: str = Field(..., description="Asset or equipment identifier")
    start_time: str = Field(..., description="ISO8601 start time")
    end_time: str = Field(..., description="ISO8601 end time")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Extra detector parameters")


class ImageDetectInput(BaseModel):
    task_id: str = Field(..., description="Task identifier")
    asset_id: str = Field(..., description="Asset or equipment identifier")
    image_base64: Optional[str] = Field(None, description="Base64 encoded image data")
    question: Optional[str] = Field(None, description="Optional user question")
    tool_type: Optional[str] = Field(
        None,
        description="Visual backend selector, for example qwen3.5-plus or anomalygpt",
    )
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Extra visual detector parameters")


class ImageLocalizeInput(BaseModel):
    task_id: str = Field(..., description="Task identifier")
    asset_id: str = Field(..., description="Asset or equipment identifier")
    image_base64: Optional[str] = Field(None, description="Base64 encoded image data")
    question: Optional[str] = Field(None, description="Optional user question about anomaly location")
    tool_type: Optional[str] = Field(
        None,
        description="Visual backend selector, for example qwen3.5-plus or anomalygpt",
    )
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Extra localization parameters")


class RagQueryInput(BaseModel):
    query: str = Field(..., description="Query text")
    top_k: int = Field(3, description="Number of similar items to return")
    category: Optional[str] = Field(None, description="Optional category filter")


class TimeSeriesAnomalyTool(BaseTool):
    name: str = "timeseries_anomaly_detection"
    description: str = (
        "Analyze sensor or time-series anomaly data through the external HTTP detection service."
    )
    args_schema: Type[BaseModel] = TimeSeriesDetectInput

    def _run(self, **kwargs: Any) -> str:
        raise NotImplementedError("This tool only supports async execution via _arun")

    async def _arun(self, **kwargs: Any) -> str:
        task = DetectionTask(
            task_id=kwargs["task_id"],
            asset_id=kwargs["asset_id"],
            start_time=kwargs["start_time"],
            end_time=kwargs["end_time"],
            parameters=kwargs.get("parameters", {}),
        )
        tool = HttpAnomalyDetectionTool()
        response = await tool.run(task)
        if response.success and response.result:
            return response.result.model_dump_json()
        return f"Error: {response.error or 'Unknown error'}"


class VisualAnomalyTool(BaseTool):
    name: str = "visual_anomaly_detection"
    description: str = (
        "Inspect equipment images for defects, leakage, meter anomalies, and other visual issues."
    )
    args_schema: Type[BaseModel] = ImageDetectInput

    def _run(self, **kwargs: Any) -> str:
        raise NotImplementedError("This tool only supports async execution via _arun")

    async def _arun(self, **kwargs: Any) -> str:
        parameters = dict(kwargs.get("parameters", {}))
        if kwargs.get("tool_type"):
            parameters["tool_type"] = kwargs["tool_type"]

        task = DetectionTask(
            task_id=kwargs["task_id"],
            asset_id=kwargs["asset_id"],
            start_time="now",
            end_time="now",
            parameters={
                "image_base64": kwargs["image_base64"],
                **parameters,
            },
            question=kwargs.get("question"),
        )
        tool = ImageAnomalyDetectionTool()
        response = await tool.run(task)
        if response.success and response.result:
            return response.result.model_dump_json()
        return f"Error: {response.error or 'Unknown error'}"


class VisualAnomalyLocalizationTool(BaseTool):
    name: str = "visual_anomaly_localization"
    description: str = (
        "Locate where anomalies appear in an image and return bounding boxes or coarse regions."
    )
    args_schema: Type[BaseModel] = ImageLocalizeInput

    def _run(self, **kwargs: Any) -> str:
        raise NotImplementedError("This tool only supports async execution via _arun")

    async def _arun(self, **kwargs: Any) -> str:
        parameters = dict(kwargs.get("parameters", {}))
        if kwargs.get("tool_type"):
            parameters["tool_type"] = kwargs["tool_type"]
        parameters["require_localization"] = True

        task = DetectionTask(
            task_id=kwargs["task_id"],
            asset_id=kwargs["asset_id"],
            start_time="now",
            end_time="now",
            parameters={
                "image_base64": kwargs["image_base64"],
                **parameters,
            },
            question=kwargs.get("question"),
        )
        tool = ImageAnomalyDetectionTool()
        response = await tool.run(task)
        if response.success and response.result:
            return response.result.model_dump_json()
        return f"Error: {response.error or 'Unknown error'}"


class KnowledgeRetrievalTool(BaseTool):
    name: str = "knowledge_retrieval"
    description: str = (
        "Retrieve similar industrial cases, manuals, and handling suggestions from the knowledge base."
    )
    args_schema: Type[BaseModel] = RagQueryInput

    def _run(self, query: str, top_k: int = 3, category: Optional[str] = None) -> str:
        raise NotImplementedError("This tool only supports async execution via _arun")

    async def _arun(self, query: str, top_k: int = 3, category: Optional[str] = None) -> str:
        rag_service = RagService()
        results = rag_service.retriever.retrieve_similar(
            query_description=query,
            top_k=top_k,
            category=category,
        )
        return rag_service.retriever.format_for_prompt(results)


def get_industrial_tools() -> List[BaseTool]:
    """Return all tools available to the planner."""
    return [
        TimeSeriesAnomalyTool(),
        VisualAnomalyTool(),
        VisualAnomalyLocalizationTool(),
        KnowledgeRetrievalTool(),
    ]
