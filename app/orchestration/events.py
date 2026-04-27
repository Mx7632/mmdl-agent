from __future__ import annotations

from app.memory.state import DetectionState


def append_execution_event(state: DetectionState, event_type: str, **payload: object) -> None:
    event = {"type": event_type, **payload}
    state.execution_events.append(event)
