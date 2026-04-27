from __future__ import annotations

from app.memory.memory_manager import memory_manager
from app.memory.state import DetectionState


def compact_conversation_history(
    history: list[dict[str, str]],
    *,
    existing_summary: str | None = None,
) -> tuple[str | None, list[dict[str, str]], int]:
    return memory_manager.compact_conversation_history(history, existing_summary=existing_summary)


def compact_state_conversation(state: DetectionState) -> int:
    task_runtime = state.task_runtime()
    summary, compacted_history, compacted_count = compact_conversation_history(
        task_runtime.conversation_history,
        existing_summary=task_runtime.conversation_summary,
    )
    if compacted_count == 0:
        return 0

    task_runtime.conversation_history = compacted_history
    task_runtime.conversation_summary = summary
    task_runtime.conversation_compacted_turns += compacted_count
    state.apply_task_runtime(task_runtime)
    # Keep compatibility shadows for payloads that still read from the generic context dict.
    state.context["conversation_summary"] = summary
    state.context["conversation_compacted_turns"] = task_runtime.conversation_compacted_turns
    state.logs.append(
        f"[Conversation] Compacted {compacted_count} earlier turn(s); kept {len(compacted_history)} recent turn(s)"
    )
    return compacted_count
