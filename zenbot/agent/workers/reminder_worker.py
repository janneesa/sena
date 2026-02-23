"""Reminder worker for polling due reminders and enqueueing events."""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from zenbot.agent.types import Event, EventType
from zenbot.agent.utils.database import DatabaseHelper
from zenbot.agent.utils.datetime_utils import parse_iso_datetime
from zenbot.agent.utils.logging import get_logger

if TYPE_CHECKING:
    from zenbot.agent.agent import Agent


logger = get_logger("zenbot")


class ReminderWorker:
    """Background worker that enqueues due reminder events for the agent."""

    def __init__(self, agent: Agent, db: DatabaseHelper, poll_seconds: int):
        """Initialize the reminder worker.
        
        Args:
            agent: The Agent instance that receives reminder events.
            db: DatabaseHelper instance for querying reminders.
            poll_seconds: Polling interval in seconds.
        """
        self.agent = agent
        self.db = db
        self.poll_seconds = poll_seconds
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        """Start the background reminder polling thread."""
        if self._thread and self._thread.is_alive():
            return

        self._thread = threading.Thread(target=self._run, daemon=True, name="reminder-worker")
        self._thread.start()
        logger.info(f"Reminder worker started (poll={self.poll_seconds}s)")

    def stop(self) -> None:
        """Request worker stop and wait briefly for shutdown."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=1.0)

    def poll_once(self) -> int:
        """Poll database once, enqueue due reminders, and mark them completed.

        Returns:
            int: Number of reminders enqueued as due events.
        """
        now = datetime.now(timezone.utc)
        reminders = self.db.get_all_reminders(include_completed=False)
        due: list[dict[str, object]] = []

        for reminder in reminders:
            when_raw = str(reminder.get("when", "")).strip()
            due_at = self._parse_when(when_raw)
            if due_at is None:
                continue
            if due_at <= now:
                due.append(reminder)

        if due:
            logger.info(f"Found {len(due)} due reminder(s)")

        queued = 0
        for reminder in due:
            reminder_id = str(reminder.get("id", "")).strip()
            if not reminder_id:
                continue
            if not self.db.mark_completed(reminder_id):
                continue

            self.agent.enqueue_event(
                Event(
                    event_type=EventType.REMINDER_DUE,
                    payload={
                        "id": reminder_id,
                        "task": reminder.get("task", "Reminder"),
                        "when": reminder.get("when", ""),
                        "notes": reminder.get("notes"),
                    },
                )
            )
            queued += 1

        return queued

    def _run(self) -> None:
        """Worker loop that polls reminders until stopped."""
        while not self._stop_event.is_set():
            try:
                self.poll_once()
            except Exception:
                logger.exception("Reminder worker polling failed")

            if self._stop_event.wait(self.poll_seconds):
                break

    @staticmethod
    def _parse_when(value: str) -> datetime | None:
        """Parse stored reminder time as ISO datetime with timezone.
        
        Delegates to utility function for reuse.
        """
        return parse_iso_datetime(value)
