from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class AgentEnvelope(BaseModel):
    """Structured message exchanged between supervisor and specialist agents."""

    agent_name: str
    status: str = "success"
    summary: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    confidence: float = 0.0
    requires_human: bool = False
    next_recommendation: str | None = None
