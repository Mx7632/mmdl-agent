# 检测任务与结果的 Pydantic 数据模型。
from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

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

'''Start Time / End Time 的意义
作为这次检测任务的时间窗口标记：告诉系统“这张图对应哪个时间段/巡检批次/工况区间”，方便追溯、对账、后续做历史对比。
会被带进报告提示词里：让生成的初始报告更像真实运维记录（例如“在 03:00–04:00 这次巡检图像中发现…”）。
未来你接本地 CV/数据库时会用到：比如按时间段关联同一资产的多张图、报警记录、工单、传感器片段等。'''

'''data_source 的意义
溯源与审计：这张图是“手动上传/传感器抓拍/数据库/外部 API”来的，后续回看记录或出报告时能解释数据从哪来。
报告上下文：我们会把它放进任务上下文（DetectionTask.data_source），未来你可以很容易把它加入提示词，让报告更贴近业务表述（例如“来自传感器抓拍”）。
未来扩展的分流点：后面接本地 CV 或接入真实数据管道时，data_source 可以决定不同处理策略：
sensor 可能要绑定摄像头 ID、抓拍时间、工况
database 可能只传图像引用 ID，不传原图
api 可能需要鉴权、回调等
'''
class DetectionResult(BaseModel):
    """检测任务输出模型"""
    task_id: str
    status: str = Field(..., description="success|failed")
    anomalies: List[Dict[str, Any]] = Field(default_factory=list)
    summary: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

class ToolResponse(BaseModel):
    """工具统一响应模型"""
    tool_name: str
    success: bool
    result: Optional[DetectionResult] = None
    error: Optional[str] = None
