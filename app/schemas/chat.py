from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """多模态 Q&A 请求模型"""
    task_id: str = Field(..., description="Unique task identifier")
    question: str = Field(..., description="User question or instruction")
    image_base64: Optional[str] = Field(None, description="Base64 encoded image data")
    image_mime: Optional[str] = Field(None, description="MIME type of the image")
    category: Optional[str] = Field(None, description="Asset category for RAG retrieval")
    parameters: Dict[str, Any] = Field(default_factory=dict)


class ChatStep(BaseModel):
    """Agent 执行步骤信息"""
    step_name: str
    action: str
    thought: str
    result: Optional[Any] = None


class ChatResponse(BaseModel):
    """多模态 Q&A 响应模型"""
    task_id: str
    status: str = Field(..., description="success|failed")
    steps: List[ChatStep] = Field(default_factory=list, description="The reasoning steps taken by the agent")
    answer: str = Field(..., description="Final comprehensive analysis and answer")
    rag_context: Optional[str] = Field(None, description="Context retrieved from RAG")
    metadata: Dict[str, Any] = Field(default_factory=dict)
