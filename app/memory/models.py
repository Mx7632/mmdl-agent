from pydantic import BaseModel, Field
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from app.memory.config import WORKING_MEMORY_EXPIRE, TOOL_CONTEXT_EXPIRE

# 记忆类型枚举
class MemoryType:
    WORKING = "working"        # 短期工作记忆：当前任务上下文
    LONG_TERM = "long_term"    # 长期记忆：用户偏好、任务结果摘要
    TOOL_CONTEXT = "tool_context"  # 工具上下文：单次工具调用信息

# 短期工作记忆模型（适配LangGraph状态）
class WorkingMemory(BaseModel):
    task_id: str  # 任务唯一标识，与LangGraph线程ID绑定
    step_id: int  # 任务执行步骤，对应图节点执行顺序
    user_id: str  # 用户标识
    agent_context: Dict[str, Any]  # Agent上下文，同步LangGraph状态
    create_time: datetime = Field(default_factory=datetime.now)
    expire_time: Optional[datetime] = None

    def __init__(self, **data):
        super().__init__(**data)
        self.expire_time = self.create_time + timedelta(minutes=WORKING_MEMORY_EXPIRE)

    def is_expired(self) -> bool:
        return datetime.now() > self.expire_time

# 长期记忆模型
class LongTermMemory(BaseModel):
    user_id: str
    memory_summary: str  # 记忆摘要
    related_tasks: List[str] = Field(default_factory=list)  # 关联LangGraph任务ID
    create_time: datetime = Field(default_factory=datetime.now)

# 工具上下文记忆模型
class ToolContextMemory(BaseModel):
    task_id: str
    step_id: int
    tool_name: str  # 调用的工具名称
    tool_input: Dict[str, Any]  # 工具输入参数
    tool_output: Optional[Dict[str, Any]] = None  # 工具返回结果
    create_time: datetime = Field(default_factory=datetime.now)
    expire_time: Optional[datetime] = None

    def __init__(self, **data):
        super().__init__(**data)
        self.expire_time = self.create_time + timedelta(minutes=TOOL_CONTEXT_EXPIRE)

    def is_expired(self) -> bool:
        return datetime.now() > self.expire_time

# LangGraph图状态模型（新增，对接记忆模块）
class AgentGraphState(BaseModel):
    """LangGraph智能体状态，同步绑定记忆数据"""
    task_id: str  # 任务ID，关联工作记忆
    current_step: int = 1  # 当前执行步骤
    user_input: str = ""  # 用户输入内容
    agent_response: str = ""  # 智能体响应结果
    tool_result: Optional[Dict[str, Any]] = None  # 工具执行结果
    memory_loaded: bool = False  # 记忆是否加载完成
