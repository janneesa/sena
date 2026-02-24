"""Task state for handling background events like reminders."""

from __future__ import annotations

from zenbot.agent.types import EventType
from zenbot.agent.states.base import State
from zenbot.agent.workers.handlers import handle_due_reminder
from zenbot.agent.utils.logging import get_logger


logger = get_logger("zenbot")


class Task(State):
    """State that handles background events (e.g., REMINDER_DUE).
    
    This state processes non-user-initiated events such as due reminders.
    It generates an appropriate message and applies side effects (e.g., deleting the reminder),
    then transitions to Cleanup to finalize.
    """

    @property
    def name(self) -> str:
        """Return the human-readable name of this state.
        
        Returns:
            str: The name 'TASK'.
        """
        return "TASK"

    def handle(self, agent, event):
        """Handle a background task event."""
        if event is None or event.event_type != EventType.TICK:
            logger.debug("Task ignoring non-TICK event")
            return self

        if agent.turn.reminder_due_payload is not None:
            handle_due_reminder(agent, agent.turn.reminder_due_payload)

        from zenbot.agent.states.cleanup import Cleanup
        return Cleanup()
