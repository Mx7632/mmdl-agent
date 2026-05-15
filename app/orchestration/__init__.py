from app.orchestration.context import (
    ClarificationContext,
    KnowledgeContext,
    ReportContext,
    SharedContext,
    VisionContext,
)
from app.orchestration.envelope import AgentEnvelope

__all__ = [
    "AgentEnvelope",
    "append_execution_event",
    "clear_pending_clarification",
    "ClarificationContext",
    "get_pending_context_from_mapping",
    "get_pending_context_from_state",
    "get_prompt_context",
    "KnowledgeContext",
    "ReportContext",
    "set_pending_clarification",
    "set_prompt_context",
    "SharedContext",
    "VisionContext",
]


def __getattr__(name: str):
    if name == "append_execution_event":
        from app.orchestration.events import append_execution_event

        return append_execution_event
    if name in {
        "clear_pending_clarification",
        "get_pending_context_from_mapping",
        "get_pending_context_from_state",
        "get_prompt_context",
        "set_pending_clarification",
        "set_prompt_context",
    }:
        from app.orchestration import context_store

        return getattr(context_store, name)
    raise AttributeError(name)
