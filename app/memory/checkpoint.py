"""
检查点存储模块 (Checkpoint Store)
为 LangGraph 工作流提供状态持久化能力。

支持 DetectionState 对象和 dict 两种格式。
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Union

from app.memory.state import DetectionState


def _deep_to_dict(obj: Any) -> Any:
    """递归将 Pydantic 对象转为纯 dict，确保可 JSON 序列化。"""
    if obj is None:
        return None
    if isinstance(obj, dict):
        return {k: _deep_to_dict(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_deep_to_dict(item) for item in obj]
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if isinstance(obj, (str, int, float, bool)):
        return obj
    # fallback：尝试 dict() 转换
    try:
        return dict(obj)
    except Exception:
        return obj


class CheckpointStore:
    """检查点存储的抽象基类。"""

    def save(self, state: Union[DetectionState, dict]) -> None:
        """保存给定的状态对象（DetectionState 或 dict）。"""
        raise NotImplementedError("save method must be implemented by subclass")

    def load(self, task_id: str) -> Optional[Union[DetectionState, dict]]:
        """根据任务ID加载之前保存的状态。"""
        raise NotImplementedError("load method must be implemented by subclass")


class MemoryCheckpointStore(CheckpointStore):
    """基于内存的检查点存储——保存 dict 格式，避开 model_validate 状态丢失问题。"""

    def __init__(self):
        # 使用 dict 存储，避开 model_validate 导致的状态丢失
        self._store: Dict[str, dict] = {}

    def save(self, state: Union[DetectionState, dict]) -> None:
        """将状态（dict）保存到内存字典中。"""
        if isinstance(state, DetectionState):
            state = state.model_dump()
        else:
            # graph.ainvoke() 返回的 dict 中可能嵌套 Pydantic 对象，需深转换
            state = _deep_to_dict(state)
        task = state.get("task", {})
        task_id = task.get("task_id") if isinstance(task, dict) else getattr(task, "task_id", "unknown")
        self._store[task_id] = state

    def load(self, task_id: str) -> Optional[dict]:
        """从内存字典中根据 task_id 加载状态（返回 dict）。"""
        return self._store.get(task_id)
