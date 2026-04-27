from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.memory.state import DetectionState
from app.orchestration.context import ClarificationContext, KnowledgeContext


def ensure_knowledge_context(state: DetectionState) -> KnowledgeContext:
    if state.shared_context.knowledge is None:
        state.shared_context.knowledge = KnowledgeContext()
    return state.shared_context.knowledge


def ensure_clarification_context(state: DetectionState) -> ClarificationContext:
    if state.shared_context.clarification is None:
        state.shared_context.clarification = ClarificationContext()
    return state.shared_context.clarification


def get_prompt_context(state: DetectionState) -> str | None:
    if state.shared_context.knowledge and state.shared_context.knowledge.prompt_context:
        return state.shared_context.knowledge.prompt_context
    return state.context.get("rag_context")


def set_prompt_context(state: DetectionState, prompt_context: str | None) -> None:
    knowledge_ctx = ensure_knowledge_context(state)
    knowledge_ctx.prompt_context = prompt_context
    state.context["rag_context"] = prompt_context


def set_pending_clarification(
    state: DetectionState,
    *,
    pending_clarification: str | None,
    pending_question: str | None,
    unknown_anomaly_types: list[str] | None = None,
    requires_human: bool = True,
) -> None:
    clarification_ctx = ensure_clarification_context(state)
    clarification_ctx.pending_clarification = pending_clarification
    clarification_ctx.pending_question = pending_question
    if unknown_anomaly_types is not None:
        clarification_ctx.unknown_anomaly_types = list(unknown_anomaly_types)
    clarification_ctx.requires_human = requires_human
    state.context["pending_clarification"] = pending_clarification
    state.context["pending_question"] = pending_question


def clear_pending_clarification(state: DetectionState) -> None:
    set_pending_clarification(
        state,
        pending_clarification=None,
        pending_question=None,
        requires_human=False,
    )


def get_pending_context_from_state(state: DetectionState) -> tuple[str | None, str | None]:
    clarification_ctx = state.shared_context.clarification
    if clarification_ctx and (clarification_ctx.pending_clarification or clarification_ctx.pending_question):
        return clarification_ctx.pending_clarification, clarification_ctx.pending_question
    return state.context.get("pending_clarification"), state.context.get("pending_question")


def get_pending_context_from_mapping(state_dict: Mapping[str, Any]) -> tuple[str | None, str | None]:
    ctx = state_dict.get("context", {}) or {}
    shared_context = state_dict.get("shared_context", {}) or {}
    clarification = shared_context.get("clarification", {}) if isinstance(shared_context, Mapping) else {}
    pending_clarification = clarification.get("pending_clarification") or ctx.get("pending_clarification")
    pending_question = clarification.get("pending_question") or ctx.get("pending_question")
    return pending_clarification, pending_question
