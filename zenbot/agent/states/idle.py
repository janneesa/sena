"""Idle state for waiting and receiving user input.

The Idle state is the quiescent ('at rest') state of the agent state machine.
It waits for USER_MESSAGE events and transitions to Generate when a message arrives.
"""

from __future__ import annotations

from zenbot.agent.types import EventType
from zenbot.agent.states.base import State
from zenbot.agent.states.generate import Generate
from zenbot.agent.utils.logging import get_logger


logger = get_logger("zenbot")

class Idle(State):
    """State that waits for user input and transitions to Generate when a message arrives.
    
    The Idle state is the quiescent state of the agent: it processes non-USER_MESSAGE events
    by returning itself, and when a USER_MESSAGE arrives, it stores the user text and 
    transitions to Generate to produce a response.
    """
    @property
    def name(self) -> str:
        """Return the human-readable name of this state.
        
        Returns:
            str: The name 'IDLE'.
        """
        return "IDLE"

    def handle(self, agent, event):
        """Handle an event: route REMINDER_DUE to Task, USER_MESSAGE to Generate, others return self.
        
        Args:
            agent: The Agent instance.
            event: The Event to process. Routes based on event type.
        
        Returns:
            State: Task if REMINDER_DUE; Generate if USER_MESSAGE; self otherwise.
        """
        if event is None:
            logger.debug("Idle received None event; remaining in IDLE")
            return self

        if event.event_type == EventType.REMINDER_DUE:
            payload = event.payload if isinstance(event.payload, dict) else {}
            agent.turn.user_text = ""
            agent.turn.reminder_due_payload = payload
            logger.debug("Idle received REMINDER_DUE; transitioning to TASK")
            from zenbot.agent.states.task import Task
            return Task()

        if event.event_type != EventType.USER_MESSAGE:
            logger.debug(f"Idle ignoring event type: {event.event_type}")
            return self

        agent.turn.user_text = str(event.payload).strip()
        logger.debug("Idle received user message; transitioning to GENERATE")

        return Generate()

