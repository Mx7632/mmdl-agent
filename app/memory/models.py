from pydantic import BaseModel, Field
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from app.memory.config import WORKING_MEMORY_EXPIRE, TOOL_CONTEXT_EXPIRE, SHORT_TERM_MEMORY_EXPIRE

# 记忆类型枚举
class MemoryType:
    WORKING = "working"        # 短期工作记忆：当前任务上下文
    SHORT_TERM = "short_term"  # 中期记忆：跨资产参考（优化新增）
    LONG_TERM = "long_term"    # 长期记忆：用户偏好、任务结果摘要
    TOOL_CONTEXT = "tool_context"  # 工具上下文：单次工具调用信息


# ─── 短期工作记忆（会话级）───
class WorkingMemory(BaseModel):
    """会话级工作记忆，绑定单个 task_id，会话结束自动失效。"""
    task_id: str
    step_id: int
    user_id: str
    agent_context: Dict[str, Any]  # Agent 上下文，同步 LangGraph 状态
    create_time: datetime = Field(default_factory=datetime.now)
    expire_time: Optional[datetime] = None

    def __init__(self, **data):
        super().__init__(**data)
        self.expire_time = self.create_time + timedelta(minutes=WORKING_MEMORY_EXPIRE)

    def is_expired(self) -> bool:
        return datetime.now() > self.expire_time


# ─── 中期记忆（资产级参考，优化新增）───
class ShortTermMemory(BaseModel):
    """中期记忆，跨同一资产的多任务参考，比 WorkingMemory 生命周期长。
    用于：同一设备/资产多次检测的历史线索积累。
    """
    asset_id: str          # 资产 ID（核心索引）
    user_id: str
    memory_summary: str     # 记忆摘要（前 300 字）
    memory_details: Optional[Dict[str, Any]] = None  # 异常详情 JSON
    tags: List[str] = Field(default_factory=list)    # 标签：[设备类型, 异常类型]
    anomaly_count: int = 0  # 检出的异常数量
    create_time: datetime = Field(default_factory=datetime.now)
    expire_time: Optional[datetime] = None

    def __init__(self, **data):
        super().__init__(**data)
        self.expire_time = self.create_time + timedelta(days=SHORT_TERM_MEMORY_EXPIRE)

    def is_expired(self) -> bool:
        return datetime.now() > self.expire_time


# ─── 长期记忆（持久积累）───
class LongTermMemory(BaseModel):
    """长期记忆，支持按 asset_id 和 tags 跨任务检索（优化新增字段）。"""
    user_id: str
    asset_id: Optional[str] = None   # 资产 ID（新增：精准定位同设备历史）
    memory_summary: str               # 记忆摘要（截取前 1500 字）
    memory_details: Optional[Dict[str, Any]] = None  # 异常详情 JSON（新增）
    tags: List[str] = Field(default_factory=list)     # 标签（新增）
    related_tasks: List[str] = Field(default_factory=list)
    create_time: datetime = Field(default_factory=datetime.now)


# ─── 工具上下文记忆（审计日志）───
class ToolContextMemory(BaseModel):
    """工具调用上下文记忆，支持按 asset_id 统计工具效果（优化新增字段）。"""
    task_id: str
    step_id: int
    asset_id: Optional[str] = None   # 资产 ID（新增：关联设备）
    tool_name: str
    tool_input: Dict[str, Any]
    tool_output: Optional[Dict[str, Any]] = None
    create_time: datetime = Field(default_factory=datetime.now)
    expire_time: Optional[datetime] = None

    def __init__(self, **data):
        super().__init__(**data)
        self.expire_time = self.create_time + timedelta(minutes=TOOL_CONTEXT_EXPIRE)

    def is_expired(self) -> bool:
        return datetime.now() > self.expire_time


# ─── LangGraph 图状态模型（对接记忆模块）───
class AgentGraphState(BaseModel):
    """LangGraph 智能体状态，同步绑定记忆数据。"""
    task_id: str
    current_step: int = 1
    user_input: str = ""
    agent_response: str = ""
    tool_result: Optional[Dict[str, Any]] = None
    memory_loaded: bool = False
