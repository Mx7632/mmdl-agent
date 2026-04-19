# Unit test: ensure long-term history text is injected into the report prompt.

from __future__ import annotations

import uuid

from app.core.graph import get_long_term_history_text
from app.memory.config import DEFAULT_USER_ID
from app.memory.memory_manager import memory_manager
from app.memory.models import LongTermMemory
from app.prompts.image_report import IMAGE_REPORT_PROMPT


def test_prompt_includes_long_term_history():
    user_id = DEFAULT_USER_ID
    marker = f"TEST_HISTORY_MARKER_{uuid.uuid4().hex}"

    # Write a unique long-term memory entry for this test run.
    memory_manager.add_long_term_memory(
        LongTermMemory(
            user_id=user_id,
            memory_summary=marker,
            related_tasks=["test-task-history-prompt"],
        )
    )

    history_text = get_long_term_history_text(user_id, max_items=10)
    assert marker in history_text

    messages = IMAGE_REPORT_PROMPT.format_messages(
        task_id="t1",
        asset_id="a1",
        start_time="2025-01-01T00:00:00Z",
        end_time="2025-01-01T01:00:00Z",
        question="q1",
        anomalies=[],
        history=history_text,
    )

    # LangChain messages are objects; simplest assertion is to check stringified payload.
    assert marker in str(messages)

