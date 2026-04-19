import json
import os
from typing import Any
from app.memory.config import MEMORY_STORE_PATH, MEMORY_ARCHIVE_PATH
from datetime import datetime

# ── 数据写入本地文件（持久化）───
def save_memory_to_file(filename: str, data: Any):
    """将记忆数据写入本地 JSON 文件，轻量级持久化。"""
    file_path = os.path.join(MEMORY_STORE_PATH, filename)

    def convert_time(obj):
        if isinstance(obj, datetime):
            return obj.strftime("%Y-%m-%d %H:%M:%S")
        raise TypeError(f"Object of type {obj.__class__.__name__} is not JSON serializable")

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, default=convert_time, ensure_ascii=False, indent=4)


# ── 从本地文件读取数据 ──
def load_memory_from_file(filename: str) -> Any:
    """从本地 JSON 文件读取记忆数据，无文件则返回空列表。"""
    file_path = os.path.join(MEMORY_STORE_PATH, filename)
    if not os.path.exists(file_path):
        return []
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return []


# ── 删除过期记忆文件 ──
def delete_expired_file(filename: str):
    """删除指定的过期记忆文件，释放存储空间。"""
    file_path = os.path.join(MEMORY_STORE_PATH, filename)
    if os.path.exists(file_path):
        os.remove(file_path)


# ── 压缩存档（新增）───
def save_archive(filename: str, data: Any):
    """将压缩后的记忆存档到 archive/ 目录。"""
    file_path = os.path.join(MEMORY_ARCHIVE_PATH, filename)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive_name = f"{ts}_{filename}"
    archive_path = os.path.join(MEMORY_ARCHIVE_PATH, archive_name)

    def convert_time(obj):
        if isinstance(obj, datetime):
            return obj.strftime("%Y-%m-%d %H:%M:%S")
        raise TypeError(f"Object of type {obj.__class__.__name__} is not JSON serializable")

    with open(archive_path, "w", encoding="utf-8") as f:
        json.dump(data, f, default=convert_time, ensure_ascii=False, indent=4)