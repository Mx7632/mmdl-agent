"""
检查点存储模块 (Checkpoint Store)
为 LangGraph 工作流提供状态持久化能力。
"""

from typing import Dict, Optional
from app.memory.state import DetectionState


class CheckpointStore:
    """
    检查点存储的抽象基类。
    定义了所有具体存储后端必须实现的接口。
    """

    def save(self, state: DetectionState) -> None:
        """
        保存给定的状态对象。

        Args:
            state (DetectionState): 要保存的 LangGraph 状态实例。
        """
        raise NotImplementedError("save method must be implemented by subclass")

    def load(self, task_id: str) -> Optional[DetectionState]:
        """
        根据任务ID加载之前保存的状态。

        Args:
            task_id (str): 用于检索状态的唯一任务标识符。

        Returns:
            Optional[DetectionState]: 如果找到则返回状态，否则返回 None。
        """
        raise NotImplementedError("load method must be implemented by subclass")


class MemoryCheckpointStore(CheckpointStore):
    """
    基于内存的检查点存储实现。
    
    将所有状态保存在内存字典中，适用于开发和测试环境。
    重启后数据会丢失。
    """

    def __init__(self):
        self._store: Dict[str, DetectionState] = {}

    def save(self, state: DetectionState) -> None:
        """将状态保存到内存字典中。"""
        self._store[state.task.task_id] = state

    def load(self, task_id: str) -> Optional[DetectionState]:
        """从内存字典中根据task_id加载状态。"""
        return self._store.get(task_id)
