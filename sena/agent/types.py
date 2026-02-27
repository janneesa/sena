from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class EventType(str, Enum):
    """Events consumed by the state machine."""
    USER_MESSAGE = "user_message"
    REMINDER_DUE = "reminder_due"
    TICK = "tick"


@dataclass(frozen=True)
class Event:
    """Immutable event payload sent to states."""
    event_type: EventType
    payload: Any = None


@dataclass
class Turn:
    """Ephemeral per-turn state used by Generate/UseTools/Cleanup."""
    user_text: str = ""
    assistant_text: str = ""
    reminder_due_payload: dict[str, Any] | None = None
    assistant_streamed: bool = False
    pending_tool_calls: list[dict[str, Any]] = field(default_factory=list)
    tool_results: list[dict[str, Any]] = field(default_factory=list)
    llm_messages: list[dict[str, Any]] = field(default_factory=list)
