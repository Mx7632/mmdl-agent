import json
import os
from typing import Any
from app.memory.config import MEMORY_STORE_PATH
from datetime import datetime

# 数据写入本地文件（持久化）
def save_memory_to_file(filename: str, data: Any):
    """将记忆数据写入本地JSON文件，轻量级持久化"""
    file_path = os.path.join(MEMORY_STORE_PATH, filename)
    # 处理datetime数据，适配JSON序列化
    def convert_time(obj):
        if isinstance(obj, datetime):
            return obj.strftime("%Y-%m-%d %H:%M:%S")
        raise TypeError(f"Object of type {obj.__class__.__name__} is not JSON serializable")
    
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, default=convert_time, ensure_ascii=False, indent=4)

# 从本地文件读取数据
def load_memory_from_file(filename: str) -> Any:
    """从本地JSON文件读取记忆数据，无文件则返回空列表"""
    file_path = os.path.join(MEMORY_STORE_PATH, filename)
    if not os.path.exists(file_path):
        return []
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        # 适配空文件/损坏文件，避免程序崩溃
        return []

# 删除过期记忆文件
def delete_expired_file(filename: str):
    """删除指定的过期记忆文件，释放存储空间"""
    file_path = os.path.join(MEMORY_STORE_PATH, filename)
    if os.path.exists(file_path):
        os.remove(file_path)