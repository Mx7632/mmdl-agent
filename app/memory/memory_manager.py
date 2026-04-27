from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.memory.config import (
    LONG_TERM_COMPRESS_THRESHOLD,
    MAX_CONVERSATION_SUMMARY_CHARS,
    MAX_CONVERSATION_TURNS,
    MAX_SHORT_TERM,
    MAX_WORKING_MEMORY,
    MEMORY_ARCHIVE_PATH,
)
from app.memory.models import LongTermMemory, ShortTermMemory, ToolContextMemory, WorkingMemory
from app.memory.utils import load_memory_from_file, save_archive, save_memory_to_file

logger = logging.getLogger(__name__)


def _serialize(obj: Any) -> Dict[str, Any]:
    data = obj if isinstance(obj, dict) else obj.model_dump()
    for key, value in data.items():
        if isinstance(value, datetime):
            data[key] = value.strftime("%Y-%m-%d %H:%M:%S")
    return data


def _truncate(text: str, limit: int) -> str:
    normalized = " ".join(text.split())
    if len(normalized) <= limit:
        return normalized
    return f"{normalized[: max(limit - 3, 0)]}..."


class MemoryManager:
    def __init__(self):
        self.working_memory_cache: List[WorkingMemory] = []
        self.short_term_memory_cache: List[ShortTermMemory] = []
        self.long_term_memory_cache: List[LongTermMemory] = []
        self.tool_context_cache: List[ToolContextMemory] = []
        self._load_all_memory()

    def _load_all_memory(self) -> None:
        for cls, filename in [
            (WorkingMemory, "working_memory.json"),
            (ToolContextMemory, "tool_context.json"),
        ]:
            raw = load_memory_from_file(filename)
            cache = getattr(self, f"{cls.__name__.lower().replace('memory', '_memory')}_cache", None)
            if cache is None:
                continue
            for item in raw:
                try:
                    cache.append(cls(**item))
                except Exception as exc:
                    logger.warning("Failed to load %s item: %s", filename, exc)

        for cls, filename, attr_name in [
            (ShortTermMemory, "short_term_memory.json", "short_term_memory_cache"),
            (LongTermMemory, "long_term_memory.json", "long_term_memory_cache"),
        ]:
            raw = load_memory_from_file(filename)
            cache = getattr(self, attr_name)
            for item in raw:
                try:
                    valid = {key: value for key, value in item.items() if key in cls.model_fields}
                    cache.append(cls(**valid))
                except Exception as exc:
                    logger.warning("Failed to load %s item: %s", filename, exc)

    def _save_all_memory(self) -> None:
        mapping = [
            (self.working_memory_cache, "working_memory.json"),
            (self.short_term_memory_cache, "short_term_memory.json"),
            (self.long_term_memory_cache, "long_term_memory.json"),
            (self.tool_context_cache, "tool_context.json"),
        ]
        for cache, filename in mapping:
            try:
                save_memory_to_file(filename, [_serialize(item) for item in cache])
            except Exception as exc:
                logger.warning("Failed to save %s: %s", filename, exc)

    def clean_expired_memory(self) -> None:
        before = (
            len(self.working_memory_cache),
            len(self.tool_context_cache),
            len(self.short_term_memory_cache),
        )

        self.working_memory_cache = [item for item in self.working_memory_cache if not item.is_expired()]
        self.tool_context_cache = [item for item in self.tool_context_cache if not item.is_expired()]
        self.short_term_memory_cache = [item for item in self.short_term_memory_cache if not item.is_expired()]

        if len(self.working_memory_cache) > MAX_WORKING_MEMORY:
            self.working_memory_cache = self.working_memory_cache[-MAX_WORKING_MEMORY:]
        if len(self.short_term_memory_cache) > MAX_SHORT_TERM:
            self.short_term_memory_cache = self.short_term_memory_cache[-MAX_SHORT_TERM:]

        after = (
            len(self.working_memory_cache),
            len(self.tool_context_cache),
            len(self.short_term_memory_cache),
        )
        if before != after:
            self._save_all_memory()

    def add_working_memory(self, memory: WorkingMemory) -> None:
        self.clean_expired_memory()
        self.working_memory_cache.append(memory)
        self._save_all_memory()

    def get_working_memory(self, task_id: str, step_id: Optional[int] = None) -> List[WorkingMemory]:
        self.clean_expired_memory()
        result = [item for item in self.working_memory_cache if item.task_id == task_id]
        if step_id is not None:
            result = [item for item in result if item.step_id == step_id]
        return result

    def add_short_term_memory(self, memory: ShortTermMemory) -> None:
        exists = any(
            item.asset_id == memory.asset_id and item.memory_summary == memory.memory_summary
            for item in self.short_term_memory_cache
        )
        if exists:
            return
        self.short_term_memory_cache.append(memory)
        self.clean_expired_memory()
        self._save_all_memory()

    def get_short_term_memory(self, asset_id: str) -> List[ShortTermMemory]:
        self.clean_expired_memory()
        return [item for item in self.short_term_memory_cache if item.asset_id == asset_id]

    def get_short_term_memory_summary(self, asset_id: str, limit: int = 5) -> str:
        memories = self.get_short_term_memory(asset_id)[-limit:]
        if not memories:
            return "(no historical detection records)"
        lines = [f"- [{item.create_time.strftime('%m-%d')}] {_truncate(item.memory_summary, 200)}" for item in memories]
        return "\n".join(lines)

    def add_long_term_memory(self, memory: LongTermMemory) -> None:
        exists = any(
            item.user_id == memory.user_id and item.memory_summary == memory.memory_summary
            for item in self.long_term_memory_cache
        )
        if exists:
            return

        self.long_term_memory_cache.append(memory)
        if memory.asset_id:
            same_asset = [item for item in self.long_term_memory_cache if item.asset_id == memory.asset_id]
            if len(same_asset) > LONG_TERM_COMPRESS_THRESHOLD:
                self._compress_long_term_by_asset(memory.asset_id, same_asset)
        self._save_all_memory()

    def _compress_long_term_by_asset(self, asset_id: str, records: List[LongTermMemory]) -> None:
        logger.info("[MemoryCompression] Compressing %s long-term record(s) for asset_id=%s", len(records), asset_id)

        archive_data = [_serialize(record) for record in records]
        archive_file = f"long_term_{asset_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}.json"
        save_archive(archive_file, archive_data)

        recent_records = records[-LONG_TERM_COMPRESS_THRESHOLD:]
        summary_lines = "\n".join(
            f"## Record {index + 1} ({record.create_time.strftime('%Y-%m-%d')})\n{_truncate(record.memory_summary, 400)}"
            for index, record in enumerate(recent_records)
        )
        compressed = LongTermMemory(
            user_id=records[0].user_id,
            asset_id=asset_id,
            memory_summary=f"[{asset_id} periodic summary] compressed from {len(records)} records\n\n{summary_lines}",
            tags=sorted({"compressed_summary", *(tag for record in records for tag in (record.tags or []))}),
            related_tasks=sorted(
                {
                    task_id
                    for record in records
                    for task_id in (record.related_tasks or [])
                }
            ),
        )

        self.long_term_memory_cache = [item for item in self.long_term_memory_cache if item.asset_id != asset_id]
        self.long_term_memory_cache.append(compressed)
        logger.info(
            "[MemoryCompression] Archived raw records to %s/%s and kept one summary entry",
            MEMORY_ARCHIVE_PATH,
            archive_file,
        )

    def get_long_term_memory(
        self,
        user_id: str,
        asset_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
        limit: int = 5,
    ) -> List[LongTermMemory]:
        candidates = [item for item in self.long_term_memory_cache if item.user_id == user_id]
        if asset_id:
            asset_memories = [item for item in candidates if item.asset_id == asset_id]
            if asset_memories:
                return asset_memories[-limit:]
            return candidates[-limit:]
        if tags:
            candidates = [item for item in candidates if any(tag in (item.tags or []) for tag in tags)]
        return candidates[-limit:]

    def add_tool_context(self, context: ToolContextMemory) -> None:
        self.clean_expired_memory()
        self.tool_context_cache.append(context)
        self._save_all_memory()

    def get_tool_context(self, task_id: str, step_id: Optional[int] = None) -> Optional[ToolContextMemory]:
        self.clean_expired_memory()
        for item in self.tool_context_cache:
            if item.task_id != task_id:
                continue
            if step_id is None or item.step_id == step_id:
                return item
        return None

    def get_tool_effect_summary(self, asset_id: str, limit: int = 10) -> str:
        records = [item for item in self.tool_context_cache if item.asset_id == asset_id][-limit:]
        if not records:
            return "(no historical tool traces)"

        total_anomalies = sum((item.tool_output or {}).get("anomaly_count", 0) for item in records)
        avg = total_anomalies / len(records) if records else 0
        lines = [
            f"- [{item.create_time.strftime('%m-%d %H:%M')}] {item.tool_name} -> anomalies {(item.tool_output or {}).get('anomaly_count', 0)}"
            for item in records
        ]
        header = (
            f"Historical tool runs: {len(records)}, total anomalies: {total_anomalies}, "
            f"average per run: {avg:.1f}\n"
        )
        return header + "\n".join(lines)

    def build_memory_context(
        self,
        user_id: str,
        asset_id: Optional[str] = None,
        task_id: Optional[str] = None,
    ) -> Dict[str, str]:
        del task_id
        short_term = (
            self.get_short_term_memory_summary(asset_id or "", limit=5)
            if asset_id
            else "(asset_id missing, short-term memory unavailable)"
        )
        long_term = "\n".join(
            f"- {_truncate(item.memory_summary, 300)}"
            for item in self.get_long_term_memory(user_id, asset_id=asset_id, limit=3)
        ) or "(no long-term memory)"
        tool_effect = (
            self.get_tool_effect_summary(asset_id, limit=5)
            if asset_id
            else "(asset_id missing, tool-effect history unavailable)"
        )
        return {
            "short_term": short_term,
            "long_term": long_term,
            "tool_effect": tool_effect,
        }

    def compact_conversation_history(
        self,
        history: List[Dict[str, str]],
        *,
        existing_summary: Optional[str] = None,
        keep_recent: int = MAX_CONVERSATION_TURNS,
        max_summary_chars: int = MAX_CONVERSATION_SUMMARY_CHARS,
    ) -> tuple[Optional[str], List[Dict[str, str]], int]:
        if len(history) <= keep_recent:
            return existing_summary, list(history), 0

        compacted_count = len(history) - keep_recent
        older_turns = history[:compacted_count]
        recent_turns = history[compacted_count:]

        summary_parts: list[str] = []
        if existing_summary:
            summary_parts.append(existing_summary.strip())
        if older_turns:
            lines = [
                f"- {item.get('role', 'assistant')}: {_truncate(item.get('content', ''), 240)}"
                for item in older_turns
            ]
            summary_parts.append("[Earlier conversation]\n" + "\n".join(lines))

        combined = "\n\n".join(part for part in summary_parts if part).strip() or None
        if combined and len(combined) > max_summary_chars:
            combined = "[Earlier conversation summary truncated]\n" + combined[-(max_summary_chars - 41) :]

        return combined, list(recent_turns), compacted_count


memory_manager = MemoryManager()
