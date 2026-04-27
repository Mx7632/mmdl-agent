"""Compatibility facade for task execution and streaming entrypoints.

The active runtime implementation lives in ``app.services``. This module
re-exports the public functions so older imports continue to work.
"""

from app.services import (
    continue_detection,
    generate_report,
    get_pending_task,
    run_chat,
    run_detection,
    stream_continue_detection,
    stream_detection,
)
from app.core.graph import build_graph

__all__ = [
    "build_graph",
    "continue_detection",
    "generate_report",
    "get_pending_task",
    "run_chat",
    "run_detection",
    "stream_continue_detection",
    "stream_detection",
]
