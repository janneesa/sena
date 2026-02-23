from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class EventType(str, Enum):
    """Enumeration of event types used in the agent state machine.
    
    Attributes:
        USER_MESSAGE: An event triggered by user input to the agent.
        REMINDER_DUE: A due reminder event produced by the reminder worker.
        TICK: An internal event used by the state machine to drive state transitions.
    """
    USER_MESSAGE = "user_message"
    REMINDER_DUE = "reminder_due"
    TICK = "tick"


@dataclass(frozen=True)
class Event:
    """Immutable event that carries type and optional payload data.
    
    Events are the primary mechanism for communicating with the agent's state machine.
    They can represent external input (like USER_MESSAGE) or internal state transitions (like TICK).
    
    Attributes:
        event_type: The type of the event (EventType enum value).
        payload: Optional data associated with the event. For USER_MESSAGE, this is the user input string.
    """
    event_type: EventType
    payload: Any = None


@dataclass
class Turn:
    """Container for a single turn of conversation between user and assistant.
    
    Tracks the user's input and the assistant's response for the current turn.
    This data is committed to message history via Agent.commit_turn().
    
    Attributes:
        user_text: The user's input text for the current turn.
        assistant_text: The assistant's response text for the current turn.
        reminder_due_payload: Optional reminder payload for due-reminder generation turns.
        assistant_streamed: Whether assistant_text was already streamed to output.
        pending_tool_calls: Queue of tool call requests for this turn.
        tool_results: Results returned by tools during this turn.
        llm_messages: Working message list for Generate/UseTools loop in this turn.
    """
    user_text: str = ""
    assistant_text: str = ""
    reminder_due_payload: dict[str, Any] | None = None
    assistant_streamed: bool = False
    pending_tool_calls: list[dict[str, Any]] = field(default_factory=list)
    tool_results: list[dict[str, Any]] = field(default_factory=list)
    llm_messages: list[dict[str, Any]] = field(default_factory=list)
