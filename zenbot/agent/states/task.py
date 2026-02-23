"""Task state for handling background events like reminders."""

from __future__ import annotations

from datetime import datetime

import ollama

from zenbot.agent.types import EventType
from zenbot.agent.states.base import State
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
            self._handle_due_reminder(agent, agent.turn.reminder_due_payload)

        from zenbot.agent.states.cleanup import Cleanup
        return Cleanup()

    def _handle_due_reminder(self, agent, payload: dict) -> None:
        """Generate friendly due-reminder message. Reminder is already marked completed by worker."""
        task = str(payload.get("task", "your reminder")).strip() or "your reminder"
        when_text = str(payload.get("when", "")).strip()
        notes = str(payload.get("notes", "")).strip()

        # Get current local time to help LLM generate contextually correct messages
        now_local = datetime.now().astimezone()
        current_time_context = now_local.strftime("%Y-%m-%d %H:%M:%S %Z")
        
        system_prompt = (
            "Write one short, friendly reminder notification for the user. "
            "The reminder is due now, so tell them it is time to do the task now. "
            "Focus only on this task and optional notes. "
            "Do not mention other reminders, future timing, or scheduling actions. "
            "Return plain text only."
            "The reminder will be deleted after this notification, so do not include instructions about snoozing or rescheduling."
        )
        user_prompt = (
            f"Current local date/time: {current_time_context}\n"
            f"Task: {task}\n"
            f"Due at: {when_text or 'now'}"
        )
        if notes:
            user_prompt += f"\nNotes: {notes}"

        try:
            response = ollama.chat(
                model=agent.settings.llm.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                stream=False,
                think=agent.settings.llm.think,
            )
            message = response.get("message", {}).get("content", "").strip()
        except Exception:
            logger.exception("Task failed while composing reminder_due message")
            message = "Hey, just a reminder: it's time now."

        if not message:
            message = "Hey, just a reminder: it's time now."

        agent.turn.assistant_text = message
        agent.turn.assistant_streamed = False
        agent.output.emit_text(message)
        logger.debug(f"Task notified reminder: {task}")
