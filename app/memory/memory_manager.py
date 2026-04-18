from typing import List, Optional, Dict, Any
from datetime import datetime
from app.memory.models import WorkingMemory, LongTermMemory, ToolContextMemory, MemoryType
from app.memory.utils import save_memory_to_file, load_memory_from_file, delete_expired_file
from app.memory.config import MAX_WORKING_MEMORY

class MemoryManager:
    def __init__(self):
        # 初始化本地内存缓存，提升读取速度
        self.working_memory_cache: List[WorkingMemory] = []
        self.long_term_memory_cache: List[LongTermMemory] = []
        self.tool_context_cache: List[ToolContextMemory] = []
        # 启动时加载本地持久化数据
        self._load_all_memory()

    # 加载所有本地存储的记忆数据
    def _load_all_memory(self):
        """启动项目时加载本地已存的记忆数据，避免数据丢失"""
        # 加载短期工作记忆
        working_data = load_memory_from_file("working_memory.json")
        self.working_memory_cache = [WorkingMemory(**item) for item in working_data]
        # 加载长期记忆
        long_term_data = load_memory_from_file("long_term_memory.json")
        self.long_term_memory_cache = [LongTermMemory(**item) for item in long_term_data]
        # 加载工具上下文记忆
        tool_data = load_memory_from_file("tool_context.json")
        self.tool_context_cache = [ToolContextMemory(**item) for item in tool_data]

    # 保存所有记忆数据到本地
    def _save_all_memory(self):
        """将缓存数据持久化到本地文件，保证数据不丢失"""
        # 序列化数据：适配pydantic v1.x版本，替换model_dump为dict
        working_dump = [item.model_dump() for item in self.working_memory_cache]
        long_term_dump = [item.model_dump() for item in self.long_term_memory_cache]
        tool_dump = [item.model_dump() for item in self.tool_context_cache]
        # 写入文件
        save_memory_to_file("working_memory.json", working_dump)
        save_memory_to_file("long_term_memory.json", long_term_dump)
        save_memory_to_file("tool_context.json", tool_dump)

    # 清理过期记忆
    def clean_expired_memory(self):
        """清理过期的短期记忆和工具上下文，避免内存溢出"""
        # 清理过期工作记忆
        self.working_memory_cache = [item for item in self.working_memory_cache if not item.is_expired()]
        # 清理过期工具上下文
        self.tool_context_cache = [item for item in self.tool_context_cache if not item.is_expired()]
        # 限制缓存大小，防止内存占用过高
        if len(self.working_memory_cache) > MAX_WORKING_MEMORY:
            self.working_memory_cache = self.working_memory_cache[-MAX_WORKING_MEMORY:]
        # 持久化清理后的数据
        self._save_all_memory()

    # ------------------------------
    # 短期工作记忆操作
    # ------------------------------
    def add_working_memory(self, memory: WorkingMemory):
        """新增短期工作记忆，自动清理过期数据并持久化"""
        self.clean_expired_memory()
        self.working_memory_cache.append(memory)
        self._save_all_memory()

    def get_working_memory(self, task_id: str, step_id: Optional[int] = None) -> List[WorkingMemory]:
        """根据任务ID/步骤ID查询工作记忆，支持精准/模糊查询"""
        self.clean_expired_memory()
        res = [item for item in self.working_memory_cache if item.task_id == task_id]
        if step_id:
            res = [item for item in res if item.step_id == step_id]
        return res

    # ------------------------------
    # 长期记忆操作
    # ------------------------------
    def add_long_term_memory(self, memory: LongTermMemory):
        """新增长期记忆，自动去重冗余数据"""
        # 避免重复存储同内容记忆
        exists = any(item.user_id == memory.user_id and item.memory_summary == memory.memory_summary for item in self.long_term_memory_cache)
        if not exists:
            self.long_term_memory_cache.append(memory)
            self._save_all_memory()

    def get_long_term_memory(self, user_id: str) -> List[LongTermMemory]:
        """根据用户ID查询长期记忆，实现跨任务复用"""
        return [item for item in self.long_term_memory_cache if item.user_id == user_id]

    # ------------------------------
    # 工具上下文记忆操作
    # ------------------------------
    def add_tool_context(self, context: ToolContextMemory):
        """新增工具调用上下文，自动清理过期数据"""
        self.clean_expired_memory()
        self.tool_context_cache.append(context)
        self._save_all_memory()

    def get_tool_context(self, task_id: str, step_id: int) -> Optional[ToolContextMemory]:
        """查询指定任务步骤的工具调用上下文，便于调试回溯"""
        self.clean_expired_memory()
        for item in self.tool_context_cache:
            if item.task_id == task_id and item.step_id == step_id:
                return item
        return None

# 全局实例，方便项目全局调用
memory_manager = MemoryManager()