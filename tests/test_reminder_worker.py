import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from zenbot.agent.workers import ReminderWorker
from zenbot.agent.types import EventType
from zenbot.agent.utils.database import DatabaseHelper


class TestReminderWorker(unittest.TestCase):
    def test_poll_once_enqueues_due_and_marks_completed(self):
        # Verifies due reminders are enqueued once and marked completed.
        with tempfile.TemporaryDirectory() as tmp:
            db = DatabaseHelper(Path(tmp) / "test.db")
            due = db.add_reminder(task="drink water", when="2000-01-01T00:00:00+00:00")

            queued = []
            agent = SimpleNamespace(enqueue_event=queued.append)
            worker = ReminderWorker(agent=agent, db=db, poll_seconds=30)

            processed = worker.poll_once()

            self.assertEqual(processed, 1)
            self.assertEqual(len(queued), 1)
            self.assertEqual(queued[0].event_type, EventType.REMINDER_DUE)
            self.assertEqual(queued[0].payload["id"], due["id"])

            reminders = db.get_all_reminders(include_completed=False)
            self.assertEqual(len(reminders), 0)

    def test_poll_once_ignores_invalid_when_values(self):
        # Verifies malformed reminder times do not crash worker polling.
        with tempfile.TemporaryDirectory() as tmp:
            db = DatabaseHelper(Path(tmp) / "test.db")
            db.add_reminder(task="bad", when="not-a-date")

            queued = []
            agent = SimpleNamespace(enqueue_event=queued.append)
            worker = ReminderWorker(agent=agent, db=db, poll_seconds=30)

            processed = worker.poll_once()

            self.assertEqual(processed, 0)
            self.assertEqual(len(queued), 0)
