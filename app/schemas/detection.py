# 检测任务与结果的 Pydantic 数据模型。
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, ValidationError


class DetectionTask(BaseModel):
    """检测任务输入模型"""

    task_id: str = Field(..., description="Unique task identifier")
    asset_id: str = Field(..., description="Asset or equipment identifier")
    start_time: str = Field(..., description="ISO8601 start time")
    end_time: str = Field(..., description="ISO8601 end time")
    data_source: Optional[str] = Field(None, description="Data source name")
    input_type: Optional[str] = Field(None, description="timeseries|image")
    question: Optional[str] = Field(None, description="User question for report generation")
    parameters: Dict[str, Any] = Field(default_factory=dict)

    def __init__(self, **data: Any) -> None:
        try:
            super().__init__(**data)
        except ValidationError as exc:
            raise TypeError(str(exc)) from exc


class DetectionResult(BaseModel):
    """检测任务输出模型"""

    task_id: str
    status: str = Field(..., description="success|failed")
    answer: Optional[str] = Field(default=None, description="简洁的检测回答")
    anomalies: List[Dict[str, Any]] = Field(default_factory=list)
    summary: Optional[str] = None
    thought: Optional[str] = Field(None, description="The expert agent's reasoning process")
    explanation: Optional[Dict[str, Any]] = Field(None, description="Detailed explanation of findings")
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ToolResponse(BaseModel):
    """工具统一响应模型"""

    tool_name: str
    success: bool
    result: Optional[DetectionResult] = None
    error: Optional[str] = None


class RagBuildRequest(BaseModel):
    """RAG 建库请求"""

    dataset_root: Optional[str] = None
    include_normal: bool = True


class RagGenerateDescriptionsRequest(BaseModel):
    """生成异常样本文本描述请求"""

    dataset_root: Optional[str] = None
    output_path: Optional[str] = None
    incremental: bool = True


class RagGenerateDescriptionsResponse(BaseModel):
    """生成异常样本文本描述响应"""

    status: str
    dataset_root: str
    output_path: str
    total_anomaly_rows: int
    generated: int
    skipped: int = 0
    incremental: bool = False


class RagBuildStartResponse(BaseModel):
    """RAG 建库启动响应"""

    status: str
    task_id: str
    message: str


class RagBuildStatusResponse(BaseModel):
    """RAG 建库进度响应"""

    status: str
    task_id: str
    phase: str
    percent: int
    message: str
    processed: int = 0
    total: int = 0
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class RagBuildResponse(BaseModel):
    """RAG 建库响应"""

    status: str
    dataset_root: str
    indexed_rows: int
    vector_count: int
    stats: Dict[str, Any]


class RagQueryRequest(BaseModel):
    """RAG 文本查询请求"""

    query_text: str = Field(..., min_length=1)
    category: Optional[str] = None
    top_k: int = Field(default=3, ge=1, le=20)


class RagImageQueryRequest(BaseModel):
    """RAG 图片查询请求"""

    image_path: str = Field(..., min_length=1)
    category: Optional[str] = None
    top_k: int = Field(default=3, ge=1, le=20)


class RagQueryItem(BaseModel):
    """RAG 查询结果项"""

    id: str
    description: str
    distance: float
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RagQueryResponse(BaseModel):
    """RAG 查询响应"""

    status: str
    count: int
    results: List[RagQueryItem] = Field(default_factory=list)
    prompt_context: str


class RagIngestFeedbackRequest(BaseModel):
    """RAG 在线反馈入库请求"""

    image_path: str
    category: str = "unknown"
    user_description: str = Field(..., min_length=1)
    model_confidence: float = Field(..., ge=0.0, le=1.0)
    is_anomaly: bool = True
    anomaly_type: Optional[str] = None
    severity: Optional[str] = None


class RagIngestFeedbackResponse(BaseModel):
    """RAG 在线反馈入库响应"""

    status: str
    accepted: bool
    learning_threshold: float
    message: str
