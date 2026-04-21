"""
记忆管理器（MemoryManager）

三层记忆架构：
  WorkingMemory  → 会话级（分钟级），会话结束失效
  ShortTermMemory → 资产级（7天），跨任务参考
  LongTermMemory → 持久积累，永不过期，超阈值压缩

ToolContextMemory → 审计日志，5分钟过期
"""

from __future__ import annotations

import logging
import os
import json
from typing import List, Optional, Dict, Any
from datetime import datetime

from app.memory.models import (
    WorkingMemory,
    ShortTermMemory,
    LongTermMemory,
    ToolContextMemory,
)
from app.memory.utils import save_memory_to_file, load_memory_from_file, save_archive
from app.memory.config import (
    MAX_WORKING_MEMORY,
    MAX_SHORT_TERM,
    LONG_TERM_COMPRESS_THRESHOLD,
    MEMORY_ARCHIVE_PATH,
)

logger = logging.getLogger(__name__)


def _serialize(obj: Any) -> Dict[str, Any]:
    """Pydantic v2 序列化辅助，兼容 datetime。"""
    data = obj if isinstance(obj, dict) else obj.model_dump()
    for k, v in data.items():
        if isinstance(v, datetime):
            data[k] = v.strftime("%Y-%m-%d %H:%M:%S")
    return data


class MemoryManager:
    def __init__(self):
        self.working_memory_cache: List[WorkingMemory] = []
        self.short_term_memory_cache: List[ShortTermMemory] = []
        self.long_term_memory_cache: List[LongTermMemory] = []
        self.tool_context_cache: List[ToolContextMemory] = []
        self._load_all_memory()

    # ── 加载 / 持久化 ──────────────────────────────────────────

    def _load_all_memory(self):
        """启动时加载本地持久化数据。"""
        for cls, fname in [
            (WorkingMemory, "working_memory.json"),
            (ToolContextMemory, "tool_context.json"),
        ]:
            raw = load_memory_from_file(fname)
            cache = getattr(self, f"{cls.__name__.lower().replace('memory', '_memory')}_cache", None)
            if cache is not None:
                for item in raw:
                    try:
                        cache.append(cls(**item))
                    except Exception as e:
                        logger.warning(f"加载 {fname} 条目失败: {e}")

        # LongTermMemory / ShortTermMemory（可能有额外字段，宽容加载）
        for cls, fname, attr in [
            (ShortTermMemory, "short_term_memory.json", "short_term_memory_cache"),
            (LongTermMemory, "long_term_memory.json", "long_term_memory_cache"),
        ]:
            raw = load_memory_from_file(fname)
            for item in raw:
                try:
                    # 过滤掉过期字段避免 Pydantic 报错
                    valid = {k: v for k, v in item.items() if k in cls.model_fields}
                    getattr(self, attr).append(cls(**valid))
                except Exception as e:
                    logger.warning(f"加载 {fname} 条目失败: {e}")

    def _save_all_memory(self):
        """持久化所有缓存到本地文件。"""
        mapping = [
            (self.working_memory_cache, "working_memory.json"),
            (self.short_term_memory_cache, "short_term_memory.json"),
            (self.long_term_memory_cache, "long_term_memory.json"),
            (self.tool_context_cache, "tool_context.json"),
        ]
        for cache, fname in mapping:
            try:
                save_memory_to_file(fname, [_serialize(item) for item in cache])
            except Exception as e:
                logger.warning(f"保存 {fname} 失败: {e}")

    # ── 清理 ──────────────────────────────────────────────────

    def clean_expired_memory(self):
        """清理过期的 WorkingMemory 和 ToolContextMemory。"""
        before_w = len(self.working_memory_cache)
        before_t = len(self.tool_context_cache)
        before_s = len(self.short_term_memory_cache)

        self.working_memory_cache = [
            m for m in self.working_memory_cache if not m.is_expired()
        ]
        self.tool_context_cache = [
            m for m in self.tool_context_cache if not m.is_expired()
        ]
        self.short_term_memory_cache = [
            m for m in self.short_term_memory_cache if not m.is_expired()
        ]

        # 限制缓存大小
        if len(self.working_memory_cache) > MAX_WORKING_MEMORY:
            self.working_memory_cache = self.working_memory_cache[-MAX_WORKING_MEMORY:]
        if len(self.short_term_memory_cache) > MAX_SHORT_TERM:
            self.short_term_memory_cache = self.short_term_memory_cache[-MAX_SHORT_TERM:]

        after_w = len(self.working_memory_cache)
        after_t = len(self.tool_context_cache)
        after_s = len(self.short_term_memory_cache)

        if before_w != after_w or before_t != after_t or before_s != after_s:
            self._save_all_memory()

    # ── WorkingMemory（会话级）────────────────────────────────

    def add_working_memory(self, memory: WorkingMemory):
        """新增会话工作记忆，自动清理过期数据并持久化。"""
        self.clean_expired_memory()
        self.working_memory_cache.append(memory)
        self._save_all_memory()

    def get_working_memory(
        self, task_id: str, step_id: Optional[int] = None
    ) -> List[WorkingMemory]:
        """根据 task_id（及可选 step_id）查询会话工作记忆。"""
        self.clean_expired_memory()
        res = [m for m in self.working_memory_cache if m.task_id == task_id]
        if step_id is not None:
            res = [m for m in res if m.step_id == step_id]
        return res

    # ── ShortTermMemory（资产级，【优化新增】）─────────────────

    def add_short_term_memory(self, memory: ShortTermMemory):
        """新增加强版中期记忆，自动去重后写入。"""
        # 去重：同 asset_id + 同摘要内容 → 跳过
        exists = any(
            m.asset_id == memory.asset_id
            and m.memory_summary == memory.memory_summary
            for m in self.short_term_memory_cache
        )
        if not exists:
            self.short_term_memory_cache.append(memory)
            self._save_all_memory()

    def get_short_term_memory(self, asset_id: str) -> List[ShortTermMemory]:
        """按资产 ID 查询中期记忆，跨任务参考同设备历史。"""
        return [m for m in self.short_term_memory_cache if m.asset_id == asset_id]

    def get_short_term_memory_summary(
        self, asset_id: str, limit: int = 5
    ) -> str:
        """获取指定资产的近期记忆摘要（供 prompt 使用）。"""
        memories = self.get_short_term_memory(asset_id)[-limit:]
        if not memories:
            return "（无历史检测记录）"
        lines = [
            f"- [{m.create_time.strftime('%m-%d')}] {m.memory_summary[:200]}"
            for m in memories
        ]
        return "\n".join(lines)

    # ── LongTermMemory（持久积累，【优化新增 asset_id 过滤】）─

    def add_long_term_memory(self, memory: LongTermMemory):
        """
        新增长期记忆，支持自动压缩。
        当同一 asset_id 的记录超过阈值时：
          1. 取所有相关记录
          2. 用 LLM 归纳合并成一条"汇总记忆"
          3. 原始记录移入 archive/
        """
        # 去重检查
        exists = any(
            m.user_id == memory.user_id
            and m.memory_summary == memory.memory_summary
            for m in self.long_term_memory_cache
        )
        if exists:
            return

        self.long_term_memory_cache.append(memory)

        # ── 触发压缩检查 ──
        if memory.asset_id:
            same_asset = [
                m for m in self.long_term_memory_cache
                if m.asset_id == memory.asset_id
            ]
            if len(same_asset) > LONG_TERM_COMPRESS_THRESHOLD:
                self._compress_long_term_by_asset(memory.asset_id, same_asset)

        self._save_all_memory()

    def _compress_long_term_by_asset(
        self, asset_id: str, records: List[LongTermMemory]
    ):
        """
        将同一 asset_id 的多条 LongTermMemory 压缩为一条汇总，
        原始记录存档到 archive/。
        """
        logger.info(
            f"[记忆压缩] asset_id={asset_id}，共 {len(records)} 条，触发压缩"
        )

        # 原始记录存档
        archive_data = [_serialize(r) for r in records]
        archive_file = f"long_term_{asset_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}.json"
        save_archive(archive_file, archive_data)

        # 构建汇总记忆
        summary_lines = "\n".join(
            f"## 记录{i+1}（{r.create_time.strftime('%Y-%m-%d')}）\n{r.memory_summary[:400]}"
            for i, r in enumerate(records[-LONG_TERM_COMPRESS_THRESHOLD:])
        )
        compressed = LongTermMemory(
            user_id=records[0].user_id,
            asset_id=asset_id,
            memory_summary=(
                f"【{asset_id} 定期汇总】（压缩自 {len(records)} 条记录）\n\n"
                + summary_lines
            ),
            tags=["compressed_summary", *records[0].tags],
            related_tasks=[r for r in records[-1].related_tasks],
        )

        # 移除原始记录，替换为汇总
        self.long_term_memory_cache = [
            m for m in self.long_term_memory_cache if m.asset_id != asset_id
        ]
        self.long_term_memory_cache.append(compressed)

        logger.info(
            f"[记忆压缩] 完成，{len(records)} 条 → 1 条汇总，"
            f"已存档至 {MEMORY_ARCHIVE_PATH}/{archive_file}"
        )

    def get_long_term_memory(
        self,
        user_id: str,
        asset_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
        limit: int = 5,
    ) -> List[LongTermMemory]:
        """
        按 user_id 精确过滤，可额外按 asset_id / tags 过滤。
        优化：asset_id 比 user_id 更精准，同设备历史优先返回。
        """
        candidates = [
            m for m in self.long_term_memory_cache
            if m.user_id == user_id
        ]

        if asset_id:
            # 优先返回同 asset_id 的记录（同设备检测最有参考价值）
            asset_memories = [m for m in candidates if m.asset_id == asset_id]
            if asset_memories:
                return asset_memories[-limit:]
            # 没找到同 asset_id，再回退到 user_id 全部
            return candidates[-limit:]

        if tags:
            candidates = [
                m for m in candidates
                if any(t in (m.tags or []) for t in tags)
            ]

        return candidates[-limit:]

    # ── ToolContextMemory（审计日志，【优化新增读取能力】）───

    def add_tool_context(self, context: ToolContextMemory):
        """新增工具调用上下文，自动清理过期数据。"""
        self.clean_expired_memory()
        self.tool_context_cache.append(context)
        self._save_all_memory()

    def get_tool_context(
        self, task_id: str, step_id: Optional[int] = None
    ) -> Optional[ToolContextMemory]:
        """查询指定任务步骤的工具调用上下文。"""
        self.clean_expired_memory()
        for item in self.tool_context_cache:
            if item.task_id == task_id:
                if step_id is None or item.step_id == step_id:
                    return item
        return None

    def get_tool_effect_summary(self, asset_id: str, limit: int = 10) -> str:
        """
        【优化新增】工具效果追踪：统计同一资产的历史检测记录，
        用于评估模型对该类设备的敏感度。
        """
        records = [
            m for m in self.tool_context_cache
            if m.asset_id == asset_id
        ][-limit:]

        if not records:
            return "（无历史工具调用记录）"

        total_anomalies = sum(
            (m.tool_output or {}).get("anomaly_count", 0)
            for m in records
        )
        detection_count = len(records)
        avg = total_anomalies / detection_count if detection_count else 0

        lines = [
            f"- [{m.create_time.strftime('%m-%d %H:%M')}] "
            f"{m.tool_name} → 异常数={m.tool_output.get('anomaly_count', 0)}"
            for m in records
        ]
        header = (
            f"该设备历史检测 {detection_count} 次，"
            f"累计检出异常 {total_anomalies} 个，平均每次 {avg:.1f} 个：\n"
        )
        return header + "\n".join(lines)

    # ── 辅助：构建 prompt 上下文（供节点调用）────────────────

    def build_memory_context(
        self,
        user_id: str,
        asset_id: Optional[str] = None,
        task_id: Optional[str] = None,
    ) -> Dict[str, str]:
        """
        构建统一的记忆上下文，供各节点拼入 prompt。
        返回结构：
          {
            "short_term": "...",
            "long_term": "...",
            "tool_effect": "...",
          }
        """
        short_term = (
            self.get_short_term_memory_summary(asset_id or "", limit=5)
            if asset_id
            else "（未提供资产ID，无法查询中期记忆）"
        )
        long_term = "\n".join(
            f"- {m.memory_summary[:300]}"
            for m in self.get_long_term_memory(user_id, asset_id=asset_id, limit=3)
        ) or "（无长期记忆）"
        tool_effect = (
            self.get_tool_effect_summary(asset_id, limit=5)
            if asset_id
            else "（未提供资产ID，无法追踪工具效果）"
        )
        return {
            "short_term": short_term,
            "long_term": long_term,
            "tool_effect": tool_effect,
        }


# ── 全局单例 ──
memory_manager = MemoryManager()
